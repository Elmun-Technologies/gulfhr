"""Suhbat oqimi: savol-javob, tekshiruv, guruhga yuborish."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from leadbot import texts
from leadbot.config import LeadBotSettings, get_leadbot_settings
from leadbot.keyboards import CONTACT_KB, GENDER_KB, REMOVE_KB, RESUME_SKIP_KB, YES_NO_KB
from leadbot.qualify import Answers, Verdict, qualify
from leadbot.states import Application
from leadbot.storage import add_application, build_report, build_search_report

logger = logging.getLogger(__name__)

router = Router(name="leadbot")

PHONE_RE = re.compile(r"^\+?\d{9,13}$")
MIN_FULL_NAME_LENGTH = 3
MAX_FULL_NAME_LENGTH = 80
MIN_EXPERIENCE_LENGTH = 1
MAX_EXPERIENCE_LENGTH = 500


def _normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"[^\d+]", "", raw)
    if not PHONE_RE.match(digits):
        return None
    if not digits.startswith("+"):
        digits = f"+{digits}" if len(digits) > 9 else f"+998{digits}"
    return digits


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    settings = get_leadbot_settings()
    if not settings.is_configured:
        await message.answer(texts.NOT_CONFIGURED)
        return

    await state.clear()
    await message.answer(texts.WELCOME, reply_markup=REMOVE_KB)
    await message.answer(texts.ASK_FULL_NAME)
    await state.set_state(Application.full_name)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=REMOVE_KB)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Analitika hisoboti — faqat guruh chatida ishlaydi."""
    settings = get_leadbot_settings()
    if message.chat.id != settings.lead_group_chat_id:
        await message.answer(texts.STATS_GROUP_ONLY)
        return
    try:
        report = build_report(settings.lead_db_path, settings.timezone)
        await message.answer(report, parse_mode="HTML")
    except Exception:  # noqa: BLE001
        logger.exception("Analitika hisobotini tuzish yoki yuborishda xato")
        await message.answer(texts.STATS_ERROR)


@router.message(Command("qidir"))
async def cmd_search(message: Message, command: CommandObject) -> None:
    """Staj matnida kalit so'z bo'yicha qidirish — faqat guruh chatida ishlaydi."""
    settings = get_leadbot_settings()
    if message.chat.id != settings.lead_group_chat_id:
        await message.answer(texts.SEARCH_GROUP_ONLY)
        return
    keyword = (command.args or "").strip()
    if not keyword:
        await message.answer(texts.SEARCH_USAGE, parse_mode="HTML")
        return
    try:
        report = build_search_report(settings.lead_db_path, keyword)
        await message.answer(report, parse_mode="HTML")
    except Exception:  # noqa: BLE001
        logger.exception("Qidiruvda xato (so'z=%r)", keyword)
        await message.answer(texts.SEARCH_ERROR)


# ─── 1. Ism ──────────────────────────────────────────────────────────


@router.message(Application.full_name, F.text)
async def on_full_name(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    if not (MIN_FULL_NAME_LENGTH <= len(full_name) <= MAX_FULL_NAME_LENGTH):
        await message.answer(texts.ASK_FULL_NAME_INVALID)
        return
    await state.update_data(full_name=full_name)
    await message.answer(texts.ASK_GENDER, reply_markup=GENDER_KB)
    await state.set_state(Application.gender)


# ─── 2. Jins ─────────────────────────────────────────────────────────


@router.callback_query(Application.gender, F.data.startswith("gender:"))
async def on_gender(callback: CallbackQuery, state: FSMContext) -> None:
    gender = callback.data.split(":", 1)[1]
    if gender not in ("male", "female"):
        await callback.answer()
        return
    await state.update_data(gender=gender)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(texts.ASK_AGE)
    await state.set_state(Application.age)
    await callback.answer()


# ─── 3. Yosh ─────────────────────────────────────────────────────────


@router.message(Application.age, F.text)
async def on_age(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit() or not (10 <= int(text) <= 80):
        await message.answer(texts.ASK_AGE_INVALID)
        return
    await state.update_data(age=int(text))
    await message.answer(texts.ASK_CITY, reply_markup=YES_NO_KB)
    await state.set_state(Application.city)


# ─── 4. Shahar ───────────────────────────────────────────────────────


@router.callback_query(Application.city, F.data.in_({"yes", "no"}))
async def on_city(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(lives_in_city=callback.data == "yes")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(texts.ASK_PHONE, reply_markup=CONTACT_KB)
    await state.set_state(Application.phone)
    await callback.answer()


# ─── 5. Telefon ──────────────────────────────────────────────────────


@router.message(Application.phone, F.contact)
async def on_phone_contact(message: Message, state: FSMContext) -> None:
    phone = _normalize_phone(message.contact.phone_number)
    if phone is None:
        await message.answer(texts.ASK_PHONE_INVALID, reply_markup=CONTACT_KB)
        return
    await state.update_data(phone=phone)
    await _ask_experience(message, state)


@router.message(Application.phone, F.text)
async def on_phone_text(message: Message, state: FSMContext) -> None:
    phone = _normalize_phone(message.text)
    if phone is None:
        await message.answer(texts.ASK_PHONE_INVALID, reply_markup=CONTACT_KB)
        return
    await state.update_data(phone=phone)
    await _ask_experience(message, state)


async def _ask_experience(message: Message, state: FSMContext) -> None:
    # Avval "Raqamni yuborish" doimiy tugmasini ekrandan tozalaymiz — aks holda
    # keyingi bosqichlarda ham osti panelida osilib qolib, nomzodlarni chalg'itadi.
    await message.answer(texts.PHONE_RECEIVED, reply_markup=REMOVE_KB)
    await message.answer(texts.ASK_EXPERIENCE, reply_markup=RESUME_SKIP_KB)
    await state.set_state(Application.experience)


# ─── 6. Ish tajribasi: golos / rezyume / matn ────────────────────────


@router.callback_query(Application.experience, F.data == "skip_resume")
async def on_experience_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(experience="", resume_info="")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await _finish_application(callback, state)


@router.message(Application.experience, F.voice)
async def on_experience_voice(message: Message, state: FSMContext) -> None:
    await state.update_data(experience="🎤 Ovozli xabar orqali tushuntirildi", resume_info="")
    # Ovozli xabarni guruhga ham forward qilish uchun file_id saqlaymiz
    await state.update_data(voice_file_id=message.voice.file_id)
    await _finish_application_msg(message, state)


@router.message(Application.experience, F.audio)
async def on_experience_audio(message: Message, state: FSMContext) -> None:
    filename = message.audio.file_name or "audio"
    await state.update_data(experience=f"🎵 Audio fayl orqali tushuntirildi: {filename}", resume_info="")
    await state.update_data(voice_file_id=message.audio.file_id)
    await _finish_application_msg(message, state)


@router.message(Application.experience, F.document)
async def on_experience_document(message: Message, state: FSMContext) -> None:
    filename = message.document.file_name or "document"
    await state.update_data(experience="", resume_info=f"📄 Rezyume fayli: {filename}")
    await state.update_data(document_file_id=message.document.file_id)
    await _finish_application_msg(message, state)


@router.message(Application.experience, F.text)
async def on_experience_text(message: Message, state: FSMContext) -> None:
    experience = message.text.strip()
    if not (MIN_EXPERIENCE_LENGTH <= len(experience) <= MAX_EXPERIENCE_LENGTH):
        await message.answer(texts.ASK_EXPERIENCE_INVALID)
        return
    await state.update_data(experience=experience, resume_info="")
    await _finish_application_msg(message, state)


# ─── Yakunlash ───────────────────────────────────────────────────────


async def _finish_application_msg(message: Message, state: FSMContext) -> None:
    """Xabar (message) orqali yakunlash (voice/document/text)."""
    data = await state.get_data()
    settings = get_leadbot_settings()
    answers = Answers(
        full_name=data["full_name"],
        gender=data.get("gender", ""),
        age=data["age"],
        lives_in_city=data["lives_in_city"],
        phone=data["phone"],
        experience=data.get("experience", ""),
        resume_info=data.get("resume_info", ""),
    )
    verdict = qualify(
        answers,
        min_age=settings.lead_min_age,
        max_age=settings.lead_max_age,
        required_city=settings.lead_required_city,
    )

    if verdict.is_qualified:
        await message.answer(
            texts.RESULT_QUALIFIED.format(name=answers.full_name), reply_markup=REMOVE_KB
        )
    else:
        reasons = "\n".join(f"• {reason}" for reason in verdict.reasons)
        await message.answer(
            texts.RESULT_NOT_QUALIFIED.format(name=answers.full_name, reasons=reasons),
            reply_markup=REMOVE_KB,
        )

    # Arizani analitika bazasiga saqlash
    try:
        add_application(settings.lead_db_path, answers, verdict)
    except Exception:  # noqa: BLE001
        logger.exception("Arizani bazaga saqlashda xato")

    await _notify_group_from_msg(message, answers, verdict, settings, data)
    await state.clear()


async def _finish_application(callback: CallbackQuery, state: FSMContext) -> None:
    """Callback orqali yakunlash (skip_resume tugmasi)."""
    data = await state.get_data()
    settings = get_leadbot_settings()
    answers = Answers(
        full_name=data["full_name"],
        gender=data.get("gender", ""),
        age=data["age"],
        lives_in_city=data["lives_in_city"],
        phone=data["phone"],
        experience=data.get("experience", ""),
        resume_info=data.get("resume_info", ""),
    )
    verdict = qualify(
        answers,
        min_age=settings.lead_min_age,
        max_age=settings.lead_max_age,
        required_city=settings.lead_required_city,
    )

    if verdict.is_qualified:
        await callback.message.answer(
            texts.RESULT_QUALIFIED.format(name=answers.full_name), reply_markup=REMOVE_KB
        )
    else:
        reasons = "\n".join(f"• {reason}" for reason in verdict.reasons)
        await callback.message.answer(
            texts.RESULT_NOT_QUALIFIED.format(name=answers.full_name, reasons=reasons),
            reply_markup=REMOVE_KB,
        )

    # Arizani analitika bazasiga saqlash
    try:
        add_application(settings.lead_db_path, answers, verdict)
    except Exception:  # noqa: BLE001
        logger.exception("Arizani bazaga saqlashda xato")

    await _notify_group(callback, answers, verdict, settings, data)
    await state.clear()


async def _notify_group_from_msg(
    message: Message,
    answers: Answers,
    verdict: Verdict,
    settings: LeadBotSettings,
    data: dict,
) -> None:
    """Message orqali kelganda guruhga xabar yuborish."""
    if not settings.lead_group_chat_id:
        return

    user = message.from_user
    if not user:
        return

    username = f"@{user.username}" if user.username else "—"
    header = texts.GROUP_HEADER_QUALIFIED if verdict.is_qualified else texts.GROUP_HEADER_NOT_QUALIFIED
    now = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    lives_label = "Ha" if answers.lives_in_city else "Yo'q"
    gender_label = texts.GENDER_LABELS.get(answers.gender, "—")
    resume_label = answers.resume_info if answers.resume_info else "Yuborilmagan"

    lines = [
        header,
        "",
        f"👤 Ism: {answers.full_name}",
        f"⚧ Jins: {gender_label}",
        f"🎂 Yosh: {answers.age}",
        f"🏙 Toshkentda yashaydi: {lives_label}",
        f"📞 Telefon: {answers.phone}",
        f"💼 Staj: {answers.experience}",
        f"📎 Rezume: {resume_label}",
        f"💬 Telegram: {username} (id: <code>{user.id}</code>)",
        f"🕓 Vaqt: {now}",
    ]
    if verdict.reasons:
        lines.append("")
        lines.append("Sabab(lar):")
        lines.extend(f"• {reason}" for reason in verdict.reasons)

    try:
        await message.bot.send_message(
            settings.lead_group_chat_id, "\n".join(lines), parse_mode="HTML"
        )
        # Rezume faylni ham guruhga yuborish
        voice_id = data.get("voice_file_id")
        document_id = data.get("document_file_id")
        if voice_id:
            await message.bot.send_voice(settings.lead_group_chat_id, voice_id)
        elif document_id:
            await message.bot.send_document(settings.lead_group_chat_id, document_id)
    except Exception:  # noqa: BLE001
        logger.exception("Guruhga xabar yuborib bo'lmadi (chat_id=%s)", settings.lead_group_chat_id)


async def _notify_group(
    callback: CallbackQuery,
    answers: Answers,
    verdict: Verdict,
    settings: LeadBotSettings,
    data: dict,
) -> None:
    """Callback orqali kelganda guruhga xabar yuborish."""
    if not settings.lead_group_chat_id:
        return

    user = callback.from_user
    username = f"@{user.username}" if user.username else "—"
    header = texts.GROUP_HEADER_QUALIFIED if verdict.is_qualified else texts.GROUP_HEADER_NOT_QUALIFIED
    now = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    lives_label = "Ha" if answers.lives_in_city else "Yo'q"
    gender_label = texts.GENDER_LABELS.get(answers.gender, "—")
    resume_label = answers.resume_info if answers.resume_info else "Yuborilmagan"

    lines = [
        header,
        "",
        f"👤 Ism: {answers.full_name}",
        f"⚧ Jins: {gender_label}",
        f"🎂 Yosh: {answers.age}",
        f"🏙 Toshkentda yashaydi: {lives_label}",
        f"📞 Telefon: {answers.phone}",
        f"💼 Staj: {answers.experience}",
        f"📎 Rezume: {resume_label}",
        f"💬 Telegram: {username} (id: <code>{user.id}</code>)",
        f"🕓 Vaqt: {now}",
    ]
    if verdict.reasons:
        lines.append("")
        lines.append("Sabab(lar):")
        lines.extend(f"• {reason}" for reason in verdict.reasons)

    try:
        await callback.bot.send_message(
            settings.lead_group_chat_id, "\n".join(lines), parse_mode="HTML"
        )
    except Exception:  # noqa: BLE001
        logger.exception("Guruhga xabar yuborib bo'lmadi (chat_id=%s)", settings.lead_group_chat_id)
