"""Nomzodlarni vakansiya talablari bo'yicha saralash — ariza oqimi.

Oqim: **til tanlash** → ism → jins → yosh → shahar → rus tili (majburiy) →
telefon → staj (matn) → rezume (fayl/golos) → natija. Ish grafigi savoli yo'q.

Uchta muhim qoida (suhbat hech qachon to'xtab qolmasligi uchun):

1. Har bir bosqichda tugma BOSILMASA ham (nomzod yozib yuborsa) javob qabul
   qilinadi — `on_*_text` handlerlari.
2. Kutilmagan xabar (rasm, stiker, bo'sh matn...) kelganda savolni qayta
   so'raymiz (`on_unexpected`) — bot jim qolmaydi.
3. Telegram xatolari (tugma allaqachon bosilgan, xabar o'chirilgan, callback
   eskirgan...) oqimni uzmaydi — `_answer_callback` / `_drop_inline_keyboard`
   ularni yutadi, keyingi savol baribir yuboriladi.

Har bir ariza bazaga saqlanadi; to'liq karta (rezume fayli bilan) HR guruhiga
yuboriladi. HR guruhida /stats bilan analitika chiqadi.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
)

from app.candidates import texts
from app.candidates.keyboards import (
    LANG_KB,
    REMOVE_KB,
    contact_kb,
    gender_kb,
    resume_skip_kb,
    yes_no_kb,
)
from app.candidates.qualify import CandidateAnswers, qualify_candidate
from app.candidates.service import (
    build_candidates_export,
    build_candidates_report,
    notify_hr_group,
    save_application,
)
from app.candidates.states import ApplicationStates
from app.candidates.texts import (
    CHOOSE_LANGUAGE,
    DEFAULT_LANGUAGE,
    Lang,
    get_texts,
    normalize_language,
)
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = Router(name="candidates")

PHONE_RE = re.compile(r"^\+?\d{9,13}$")
_STATE_PREFIX = "ApplicationStates:"

MIN_FULL_NAME_LENGTH = 3
MAX_FULL_NAME_LENGTH = 80
MAX_EXPERIENCE_LENGTH = 500

# Tugma o'rniga yozib yuborilgan javoblar (nomzodlar ko'pincha tugmani
# bosmaydi — shunda ham oqim davom etishi kerak)
_YES_TOKENS = {"ha", "xa", "haa", "xа", "yes", "да", "ага", "ok", "ок", "✅ha", "✅"}
_NO_TOKENS = {"yo'q", "yoq", "yo‘q", "yo", "no", "нет", "не", "❌yo'q", "❌"}
_MALE_TOKENS = {"erkak", "erkakman", "m", "male", "мужской", "мужчина", "м", "👨erkak"}
_FEMALE_TOKENS = {"ayol", "ayolman", "f", "female", "женский", "женщина", "ж", "👩ayol"}
_UZ_TOKENS = {"uz", "o'zbek", "o'zbekcha", "ozbek", "ozbekcha", "uzbek", "uzbekcha", "o‘zbekcha"}
_RU_TOKENS = {"ru", "rus", "ruscha", "русский", "рус", "russian", "🇷🇺русский"}
_TOKEN_CLEAN_RE = re.compile(r"[^\w'’]+")


def _token(raw: str) -> str:
    """Matnni taqqoslash uchun normallashtiradi: "✅ Ha" → "ha"."""
    return _TOKEN_CLEAN_RE.sub("", (raw or "").strip().lower()).replace("’", "'")


def _parse_yes_no(raw: str) -> bool | None:
    token = _token(raw)
    if token in _YES_TOKENS:
        return True
    if token in _NO_TOKENS:
        return False
    return None


def _parse_gender(raw: str) -> str | None:
    token = _token(raw)
    if token in _MALE_TOKENS:
        return "male"
    if token in _FEMALE_TOKENS:
        return "female"
    return None


def _parse_language(raw: str) -> str | None:
    token = _token(raw)
    if token in _UZ_TOKENS:
        return texts.UZ
    if token in _RU_TOKENS:
        return texts.RU
    return normalize_language(raw)


def _normalize_phone(raw: str) -> str | None:
    """Telefon raqamini +998... ko'rinishiga keltiradi."""
    digits = re.sub(r"[^\+\d]", "", raw)
    if not PHONE_RE.match(digits):
        return None
    if not digits.startswith("+"):
        digits = f"+{digits}" if len(digits) > 9 else f"+998{digits}"
    return digits


# ---------------------------------------------------------------------- #
# Yordamchilar: til va Telegram xatolariga bardoshlilik
# ---------------------------------------------------------------------- #


async def _lang(state: FSMContext) -> str:
    """FSM'da saqlangan til (tanlanmagan bo'lsa — sozlamadagi standart til)."""
    return (await state.get_data()).get("lang") or get_settings().default_language


async def _t(state: FSMContext) -> Lang:
    """Joriy til matnlari."""
    return get_texts(await _lang(state))


def _fire(coro) -> asyncio.Task:  # noqa: ANN001 - tur aniq, izoh pastda
    """Korutinani FONDA ishga tushiradi (kutmasdan).

    Kerak: bir nechta Telegram so'rovini ketma-ket emas, bir vaqtda yuborish.
    Xato bo'lsa faqat logga yoziladi — oqim to'xtamaydi.
    """
    task = asyncio.create_task(coro)
    task.add_done_callback(_log_background_failure)
    return task


def _log_background_failure(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning("Fon vazifasi xato bilan tugadi: %r", exc)


@asynccontextmanager
async def _fast_step(callback: CallbackQuery, *, drop_keyboard: bool = True) -> AsyncIterator[None]:
    """Tugma bosilganda nomzod kutadigan vaqtni qisqartiradi.

    Muammo: har bir tugma bosishda uchta Telegram so'rovi KETMA-KET ketardi —
    `answerCallbackQuery` (soat belgisini o'chirish) → `editMessageReplyMarkup`
    (klaviaturani olish) → yangi savol (`sendMessage`). Har biri bitta tarmoq
    kechikishi (RTT) qo'shardi: Fly/ams ↔ Telegram ~80 ms bo'lsa ham qadam
    ~250 ms, sekin tarmoqda esa bir necha sekund.

    Yechim: uchtasi ham PARALLEL yuboriladi. Kritik yo'l — 1 RTT. Blok
    oxirida (`finally`) ularning tugashi kutiladi, shuning uchun fon vazifalari
    "yo'qolmaydi" va testlarda ham hammasi hisobga olinadi.
    """
    tasks = [_fire(_answer_callback(callback))]
    if drop_keyboard:
        tasks.append(_fire(_drop_inline_keyboard(callback)))
    # Bitta tick: yuqoridagi so'rovlar (ayniqsa `callback.answer`) haqiqatan
    # yo'lga chiqib ulgursin, keyin keyingi savol yuboriladi — shu bilan
    # tugma "soat" belgisi savoldan kechikmaydi, lekin ular parallel ketadi.
    await asyncio.sleep(0)
    try:
        yield
    finally:
        await asyncio.gather(*tasks)


async def _answer_callback(callback: CallbackQuery) -> None:
    """Tugma ustidagi "soat" belgisini darhol o'chiradi.

    Boshqa so'rovlar bilan PARALLEL yuboriladi (`_fast_step`) — aks holda
    nomzod tugmani bosgach 1-2 soniya "yuklanmoqda" belgisini ko'rardi.
    Callback eskirgan bo'lsa (Telegram "query is too old" qaytaradi) oqim
    baribir davom etadi.
    """
    try:
        await callback.answer()
    except TelegramBadRequest as exc:
        logger.debug("callback.answer bajarilmadi: %s", exc)


async def _drop_inline_keyboard(callback: CallbackQuery) -> None:
    """Bosilgan tugmalarni ekrandan oladi — xato bo'lsa ham oqim to'xtamaydi."""
    message = callback.message
    if message is None or isinstance(message, InaccessibleMessage):
        # Xabar o'chirilgan/48 soatdan eski — tahrirlab bo'lmaydi
        return
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest as exc:
        # "message is not modified", "message can't be edited", ...
        logger.debug("Klaviaturani o'chirib bo'lmadi: %s", exc)


async def _say(target: Message, text: str, reply_markup=None) -> None:
    """Xabar yuboradi.

    `InaccessibleMessage.answer()` xabar YUBORMAYDI (u faqat method obyektini
    qaytaradi), shuning uchun eski/o'chirilgan xabar bo'lsa javobni foydalanuvchi
    chatiga yangi xabar sifatida yuboramiz — aks holda nomzod savolni ko'rmaydi.
    """
    if isinstance(target, InaccessibleMessage):
        await target.bot.send_message(target.chat.id, text, reply_markup=reply_markup)
        return
    await target.answer(text, reply_markup=reply_markup)


# ---------------------------------------------------------------------- #
# Oqimni boshlash — kodisiz /start (app/bot/handlers/start.py chaqiradi)
# ---------------------------------------------------------------------- #


async def start_candidate_application(
    message: Message, state: FSMContext, *, requested_lang: str | None = None
) -> None:
    """Kodisiz /start yuborgan foydalanuvchini ariza oqimiga tushiradi.

    `requested_lang` — `/start ru` kabi deep-link orqali kelgan til (reklama
    havolalari uchun qulay): u bo'lsa til tanlash oynasi o'tkazib yuboriladi.
    """
    settings = get_settings()
    await state.clear()

    lang = normalize_language(requested_lang)
    if lang is None and settings.language_choice:
        # 1-qadam: til tanlash (🇺🇿 O'zbekcha / 🇷🇺 Русский)
        await message.answer(CHOOSE_LANGUAGE, reply_markup=LANG_KB)
        await state.set_state(ApplicationStates.language)
        return

    await _begin_flow(
        message, state, lang or normalize_language(settings.default_language) or DEFAULT_LANGUAGE
    )


async def _begin_flow(target: Message, state: FSMContext, lang: str) -> None:
    """Salomlashuv + birinchi savol — BITTA xabarda (tezlik uchun)."""
    t = get_texts(lang)
    await state.update_data(lang=t.code)
    # REMOVE_KB — oldingi arizadan qolgan "Raqamni yuborish" klaviaturasini tozalaydi
    await _say(target, f"{t.welcome}\n\n{t.ask_full_name}", reply_markup=REMOVE_KB)
    await state.set_state(ApplicationStates.full_name)


def _prompt_for(state_name: str | None, t: Lang) -> tuple[str, object] | None:
    """Berilgan holat uchun savol matni va klaviaturasini qaytaradi."""
    city = get_settings().candidate_city
    prompts: dict[str, tuple[str, InlineKeyboardMarkup | ReplyKeyboardMarkup | None]] = {
        ApplicationStates.language.state: (CHOOSE_LANGUAGE, LANG_KB),
        ApplicationStates.full_name.state: (t.ask_full_name, None),
        ApplicationStates.gender.state: (t.ask_gender, gender_kb(t)),
        ApplicationStates.age.state: (t.ask_age, None),
        ApplicationStates.city.state: (t.ask_city.format(city=city), yes_no_kb(t)),
        ApplicationStates.russian.state: (t.ask_russian, yes_no_kb(t)),
        ApplicationStates.phone.state: (t.ask_phone, contact_kb(t)),
        ApplicationStates.experience.state: (t.ask_experience, None),
        ApplicationStates.resume.state: (t.ask_resume, resume_skip_kb(t)),
    }
    return prompts.get(state_name or "")


async def _reask(message: Message, state: FSMContext) -> None:
    """Nomzod kutilmagan narsa yubordi — joriy savolni qayta so'raymiz."""
    t = await _t(state)
    current = await state.get_state()
    prompt = _prompt_for(current, t)
    if prompt is None:  # pragma: no cover - himoya tarmog'i
        logger.warning("Noma'lum FSM holati: %s", current)
        await _say(message, f"{t.try_again_hint}\n/start", reply_markup=REMOVE_KB)
        return
    text, markup = prompt
    if current == ApplicationStates.language.state:
        # Til hali tanlanmagan — ikki tilli so'rovni o'zini takrorlaymiz
        await _say(message, text, reply_markup=markup)
        return
    await _say(message, f"{t.try_again_hint}\n\n{text}", reply_markup=markup)


# ---------------------------------------------------------------------- #
# Buyruqlar
# ---------------------------------------------------------------------- #


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None or not current.startswith(_STATE_PREFIX):
        # Ariza oqimida emasmiz — boshqa handlerlarga (fallback) qoldiramiz
        raise SkipHandler
    t = await _t(state)
    await state.clear()
    await message.answer(t.cancelled, reply_markup=REMOVE_KB)


@router.message(Command("lang"))
async def cmd_lang(message: Message, state: FSMContext) -> None:
    """Tilni almashtirish — suhbat boshidan boshlanadi."""
    await state.clear()
    await message.answer(CHOOSE_LANGUAGE, reply_markup=LANG_KB)
    await state.set_state(ApplicationStates.language)


def _is_hr_group(message: Message, settings: Settings) -> bool:
    """Buyruq yuborilgan chat sozlangan HR guruhi ekanini tekshiradi.

    ID bo'yicha tekshirish muhim: guruhga qo'shilgan har qanday odam umumiy
    statistikani ko'rishi mumkin, lekin bot boshqa guruhlarga ma'lumot chiqarib
    yubormasligi kerak.
    """
    return (
        settings.candidates_group_chat_id is not None
        and message.chat.id == settings.candidates_group_chat_id
    )


@router.message(Command("stats", "stat"))
async def cmd_stats(message: Message) -> None:
    """Analitika hisoboti — HR guruhida `/stats` yoki qisqa `/stat`."""
    settings = get_settings()
    if not _is_hr_group(message, settings):
        await message.answer(texts.STATS_GROUP_ONLY)
        return
    try:
        report = await build_candidates_report(settings)
    except Exception:  # noqa: BLE001
        logger.exception("Nomzodlar analitika hisobotini tuzishda xato")
        await message.answer(texts.STATS_ERROR)
        return
    await message.answer(report, parse_mode="HTML")


@router.message(Command("export", "csv"))
async def cmd_export(message: Message) -> None:
    """Barcha nomzodlarni CSV fayl qilib HR guruhiga yuboradi."""
    settings = get_settings()
    if not _is_hr_group(message, settings):
        await message.answer(texts.STATS_GROUP_ONLY)
        return

    try:
        content, count = await build_candidates_export(settings)
    except Exception:  # noqa: BLE001
        logger.exception("Nomzodlar eksportini tayyorlashda xato")
        await message.answer(texts.STATS_ERROR)
        return

    timestamp = datetime.now(settings.timezone).strftime("%Y%m%d_%H%M")
    document = BufferedInputFile(content, filename=f"gulf_hr_nomzodlar_{timestamp}.csv")
    await message.bot.send_document(
        chat_id=message.chat.id,
        document=document,
        caption=f"📁 Nomzodlar eksporti: {count} ta ariza.",
    )


# ---------------------------------------------------------------------- #
# 0. Til tanlash
# ---------------------------------------------------------------------- #


@router.callback_query(ApplicationStates.language, F.data.startswith("lang:"))
async def on_language(callback: CallbackQuery, state: FSMContext) -> None:
    lang = normalize_language(callback.data.split(":", 1)[1] if callback.data else "")
    async with _fast_step(callback, drop_keyboard=lang is not None):
        if lang is None:
            await _reask(callback.message, state)
            return
        await _begin_flow(callback.message, state, lang)


@router.message(ApplicationStates.language, F.text)
async def on_language_text(message: Message, state: FSMContext) -> None:
    """Tugma o'rniga "o'zbekcha"/"русский" deb yozib yuborgan nomzod uchun."""
    lang = _parse_language(message.text or "")
    if lang is None:
        await _reask(message, state)
        return
    await _begin_flow(message, state, lang)


# ---------------------------------------------------------------------- #
# 1. Ism
# ---------------------------------------------------------------------- #


@router.message(ApplicationStates.full_name, F.text)
async def on_full_name(message: Message, state: FSMContext) -> None:
    t = await _t(state)
    full_name = (message.text or "").strip()
    if not (MIN_FULL_NAME_LENGTH <= len(full_name) <= MAX_FULL_NAME_LENGTH):
        await message.answer(t.ask_full_name_invalid)
        return
    await state.update_data(full_name=full_name)
    await message.answer(t.ask_gender, reply_markup=gender_kb(t))
    await state.set_state(ApplicationStates.gender)


# ---------------------------------------------------------------------- #
# 2. Jins (tugma yoki yozma javob)
# ---------------------------------------------------------------------- #


async def _set_gender(target: Message, state: FSMContext, gender: str) -> None:
    t = await _t(state)
    await state.update_data(gender=gender)
    await _say(target, t.ask_age)
    await state.set_state(ApplicationStates.age)


@router.callback_query(ApplicationStates.gender, F.data.startswith("cand_gender:"))
async def on_gender(callback: CallbackQuery, state: FSMContext) -> None:
    gender = callback.data.split(":", 1)[1] if callback.data else ""
    valid = gender in ("male", "female")
    async with _fast_step(callback, drop_keyboard=valid):
        if not valid:
            await _reask(callback.message, state)
            return
        await _set_gender(callback.message, state, gender)


@router.message(ApplicationStates.gender, F.text)
async def on_gender_text(message: Message, state: FSMContext) -> None:
    gender = _parse_gender(message.text or "")
    if gender is None:
        await _reask(message, state)
        return
    await _set_gender(message, state, gender)


# ---------------------------------------------------------------------- #
# 3. Yosh
# ---------------------------------------------------------------------- #


@router.message(ApplicationStates.age, F.text)
async def on_age(message: Message, state: FSMContext) -> None:
    t = await _t(state)
    text_value = (message.text or "").strip()
    if not text_value.isdigit() or not (10 <= int(text_value) <= 80):
        await message.answer(t.ask_age_invalid)
        return
    await state.update_data(age=int(text_value))
    await message.answer(
        t.ask_city.format(city=get_settings().candidate_city), reply_markup=yes_no_kb(t)
    )
    await state.set_state(ApplicationStates.city)


# ---------------------------------------------------------------------- #
# 4. Shahar
# ---------------------------------------------------------------------- #


async def _set_city(target: Message, state: FSMContext, lives_in_city: bool) -> None:
    t = await _t(state)
    await state.update_data(lives_in_city=lives_in_city)
    await _say(target, t.ask_russian, reply_markup=yes_no_kb(t))
    await state.set_state(ApplicationStates.russian)


@router.callback_query(ApplicationStates.city, F.data.in_({"cand_yes", "cand_no"}))
async def on_city(callback: CallbackQuery, state: FSMContext) -> None:
    async with _fast_step(callback):
        await _set_city(callback.message, state, callback.data == "cand_yes")


@router.message(ApplicationStates.city, F.text)
async def on_city_text(message: Message, state: FSMContext) -> None:
    value = _parse_yes_no(message.text or "")
    if value is None:
        await _reask(message, state)
        return
    await _set_city(message, state, value)


# ---------------------------------------------------------------------- #
# 5. Rus tili (majburiy talab)
# ---------------------------------------------------------------------- #


async def _set_russian(target: Message, state: FSMContext, knows_russian: bool) -> None:
    t = await _t(state)
    await state.update_data(knows_russian=knows_russian)
    await _say(target, t.ask_phone, reply_markup=contact_kb(t))
    await state.set_state(ApplicationStates.phone)


@router.callback_query(ApplicationStates.russian, F.data.in_({"cand_yes", "cand_no"}))
async def on_russian(callback: CallbackQuery, state: FSMContext) -> None:
    async with _fast_step(callback):
        await _set_russian(callback.message, state, callback.data == "cand_yes")


@router.message(ApplicationStates.russian, F.text)
async def on_russian_text(message: Message, state: FSMContext) -> None:
    value = _parse_yes_no(message.text or "")
    if value is None:
        await _reask(message, state)
        return
    await _set_russian(message, state, value)


# ---------------------------------------------------------------------- #
# 6. Telefon
# ---------------------------------------------------------------------- #


async def _on_phone(message: Message, state: FSMContext, phone_raw: str) -> None:
    t = await _t(state)
    await state.update_data(phone=phone_raw)
    # Ortib qolgan "Raqamni yuborish" klaviaturasini tozalaymiz
    await message.answer(t.ask_experience, reply_markup=REMOVE_KB)
    await state.set_state(ApplicationStates.experience)


@router.message(ApplicationStates.phone, F.contact)
async def on_phone_contact(message: Message, state: FSMContext) -> None:
    t = await _t(state)
    phone = _normalize_phone(message.contact.phone_number or "")
    if phone is None:
        await message.answer(t.ask_phone_invalid, reply_markup=contact_kb(t))
        return
    await _on_phone(message, state, phone)


@router.message(ApplicationStates.phone, F.text)
async def on_phone_text(message: Message, state: FSMContext) -> None:
    t = await _t(state)
    phone = _normalize_phone(message.text or "")
    if phone is None:
        await message.answer(t.ask_phone_invalid, reply_markup=contact_kb(t))
        return
    await _on_phone(message, state, phone)


# ---------------------------------------------------------------------- #
# 7. Ish tajribasi (staj) — yozadigan
# ---------------------------------------------------------------------- #


@router.message(ApplicationStates.experience, F.text)
async def on_experience(message: Message, state: FSMContext) -> None:
    t = await _t(state)
    experience = (message.text or "").strip()
    if not experience or len(experience) > MAX_EXPERIENCE_LENGTH:
        await message.answer(t.ask_experience)
        return
    await state.update_data(experience=experience)
    await message.answer(t.ask_resume, reply_markup=resume_skip_kb(t))
    await state.set_state(ApplicationStates.resume)


# ---------------------------------------------------------------------- #
# 8. Rezume — fayl (PDF/DOC) yoki golos (ovozli xabar)
# ---------------------------------------------------------------------- #


@router.callback_query(ApplicationStates.resume, F.data == "cand_skip_resume")
async def on_resume_skip(callback: CallbackQuery, state: FSMContext) -> None:
    async with _fast_step(callback):
        await state.update_data(resume_info="")
        await _finish(message=callback.message, state=state)


@router.message(ApplicationStates.resume, F.voice)
async def on_resume_voice(message: Message, state: FSMContext) -> None:
    await state.update_data(
        resume_info="🎤 Ovozli xabar yuborildi",
        resume_file_kind="voice",
        resume_file_id=message.voice.file_id,
    )
    await _finish(message=message, state=state)


@router.message(ApplicationStates.resume, F.audio)
async def on_resume_audio(message: Message, state: FSMContext) -> None:
    filename = message.audio.file_name or "audio"
    await state.update_data(
        resume_info=f"🎵 Audio fayl: {filename}",
        resume_file_kind="audio",
        resume_file_id=message.audio.file_id,
    )
    await _finish(message=message, state=state)


@router.message(ApplicationStates.resume, F.document)
async def on_resume_document(message: Message, state: FSMContext) -> None:
    filename = message.document.file_name or "document"
    await state.update_data(
        resume_info=f"📄 Fayl: {filename}",
        resume_file_kind="document",
        resume_file_id=message.document.file_id,
    )
    await _finish(message=message, state=state)


@router.message(ApplicationStates.resume, F.text)
async def on_resume_text(message: Message, state: FSMContext) -> None:
    # Matn yuborsa — skip deb hisoblaymiz
    await state.update_data(resume_info="")
    await _finish(message=message, state=state)


# ---------------------------------------------------------------------- #
# Kutilmagan xabar — hech bir bosqichda jim qolmaslik
# ---------------------------------------------------------------------- #


@router.message(StateFilter(ApplicationStates))
async def on_unexpected(message: Message, state: FSMContext) -> None:
    """Rasm/stiker/video yoki mos kelmagan javob kelsa savolni qayta so'raydi.

    Bu handler router'ning ENG OXIRIDA turishi shart — aks holda aniq
    handlerlarni to'sib qo'yadi.
    """
    await _reask(message, state)


# ---------------------------------------------------------------------- #
# Yakunlash
# ---------------------------------------------------------------------- #


async def _finish(message: Message, state: FSMContext) -> None:
    """Arizani baholaydi, bazaga saqlaydi va HR guruhiga yuboradi."""
    data = await state.get_data()
    settings = get_settings()
    t = get_texts(data.get("lang"))
    user = message.from_user

    answers = CandidateAnswers(
        full_name=data.get("full_name", ""),
        gender=data.get("gender", ""),
        age=data.get("age", 0),
        lives_in_city=data.get("lives_in_city", False),
        phone=data.get("phone", ""),
        knows_russian=data.get("knows_russian", False),
        experience=data.get("experience", ""),
        resume_info=data.get("resume_info", ""),
        language=t.code,
    )
    verdict = qualify_candidate(
        answers,
        min_age=settings.candidate_min_age,
        max_age=settings.candidate_max_age,
        required_city=settings.candidate_city,
        russian_required=settings.candidate_russian_required,
    )

    if verdict.is_qualified:
        await _say(message, t.result_qualified.format(name=answers.full_name), reply_markup=REMOVE_KB)
    else:
        reasons = t.localized_reasons(
            verdict.reject_codes,
            age=answers.age,
            min_age=settings.candidate_min_age,
            max_age=settings.candidate_max_age,
            city=settings.candidate_city,
        ) or list(verdict.reasons)
        await _say(
            message,
            t.result_not_qualified.format(
                name=answers.full_name,
                reasons="\n".join(f"• {reason}" for reason in reasons),
            ),
            reply_markup=REMOVE_KB,
        )

    telegram_id = user.id if user else None
    telegram_username = user.username if user else None

    # Baza va HR guruhi bir-biriga bog'liq emas — parallel bajariladi
    # (nomzod javobini allaqachon olgan, lekin handler tezroq tugaydi).
    results = await asyncio.gather(
        save_application(
            answers,
            verdict,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            resume_file_kind=data.get("resume_file_kind"),
            resume_file_id=data.get("resume_file_id"),
        ),
        notify_hr_group(
            message.bot,
            settings,
            answers,
            verdict,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            resume_file_kind=data.get("resume_file_kind"),
            resume_file_id=data.get("resume_file_id"),
            now=datetime.now(UTC).astimezone(settings.timezone),
        ),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            logger.error(
                "Arizani saqlash yoki HR guruhiga yuborishda xato", exc_info=result
            )

    await state.clear()
