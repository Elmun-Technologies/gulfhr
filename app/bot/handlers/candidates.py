"""Nomzodlarni vakansiya talablari bo'yicha saralash — ariza oqimi.

Oqim: ism → jins (tugma) → yosh → shahar → telefon → staj (matn) →
rezume (fayl/golos) → natija. Ish grafigi savoli yo'q.

Har bir ariza bazaga saqlanadi; to'liq karta (rezume fayli bilan) HR
guruhiga yuboriladi. HR guruhida /stats bilan analitika chiqadi.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.candidates import texts
from app.candidates.keyboards import (
    CONTACT_KB,
    GENDER_KB,
    REMOVE_KB,
    RESUME_SKIP_KB,
    YES_NO_KB,
)
from app.candidates.qualify import CandidateAnswers, qualify_candidate
from app.candidates.service import (
    build_candidates_report,
    notify_hr_group,
    save_application,
)
from app.candidates.states import ApplicationStates
from app.config import get_settings

logger = logging.getLogger(__name__)
router = Router(name="candidates")

PHONE_RE = re.compile(r"^\+?\d{9,13}$")
_STATE_PREFIX = "ApplicationStates:"


def _normalize_phone(raw: str) -> str | None:
    """Telefon raqamini +998... ko'rinishiga keltiradi."""
    digits = re.sub(r"[^+\d]", "", raw)
    if not PHONE_RE.match(digits):
        return None
    if not digits.startswith("+"):
        digits = f"+{digits}" if len(digits) > 9 else f"+998{digits}"
    return digits


# ---------------------------------------------------------------------- #
# Oqimni boshlash — kodisiz /start (app/bot/handlers/start.py chaqiradi)
# ---------------------------------------------------------------------- #


async def start_candidate_application(message: Message, state: FSMContext) -> None:
    """Kodisiz /start yuborgan foydalanuvchinni ariza oqimiga tushiradi."""
    await state.clear()
    await message.answer(texts.WELCOME)
    await message.answer(texts.ASK_FULL_NAME)
    await state.set_state(ApplicationStates.full_name)


# ---------------------------------------------------------------------- #
# Buyruqlar
# ---------------------------------------------------------------------- #


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None or not current.startswith(_STATE_PREFIX):
        # Ariza oqimida emasmiz — boshqa handlerlarga (fallback) qoldiramiz
        raise SkipHandler
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=REMOVE_KB)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Analitika hisoboti — faqat HR guruhida ishlaydi."""
    settings = get_settings()
    group_id = settings.candidates_group_chat_id
    if group_id is None or message.chat.id != group_id:
        await message.answer(texts.STATS_GROUP_ONLY)
        return
    try:
        report = await build_candidates_report(settings)
    except Exception:  # noqa: BLE001
        logger.exception("Nomzodlar analitika hisobotini tuzishda xato")
        await message.answer(texts.STATS_ERROR)
        return
    await message.answer(report, parse_mode="HTML")


# ---------------------------------------------------------------------- #
# 1. Ism
# ---------------------------------------------------------------------- #


@router.message(ApplicationStates.full_name, F.text)
async def on_full_name(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer(texts.ASK_FULL_NAME)
        return
    await state.update_data(full_name=full_name)
    await message.answer(texts.ASK_GENDER, reply_markup=GENDER_KB)
    await state.set_state(ApplicationStates.gender)


# ---------------------------------------------------------------------- #
# 2. Jins (Ayol/Erkak — tanlanadigan)
# ---------------------------------------------------------------------- #


@router.callback_query(ApplicationStates.gender, F.data.startswith("cand_gender:"))
async def on_gender(callback: CallbackQuery, state: FSMContext) -> None:
    gender = callback.data.split(":", 1)[1]
    if gender not in ("male", "female"):
        await callback.answer()
        return
    await state.update_data(gender=gender)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(texts.ASK_AGE)
    await state.set_state(ApplicationStates.age)
    await callback.answer()


# ---------------------------------------------------------------------- #
# 3. Yosh
# ---------------------------------------------------------------------- #


@router.message(ApplicationStates.age, F.text)
async def on_age(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text.isdigit() or not (10 <= int(text) <= 80):
        await message.answer(texts.ASK_AGE_INVALID)
        return
    await state.update_data(age=int(text))
    settings = get_settings()
    await message.answer(
        texts.ASK_CITY.format(city=settings.candidate_city), reply_markup=YES_NO_KB
    )
    await state.set_state(ApplicationStates.city)


# ---------------------------------------------------------------------- #
# 4. Shahar
# ---------------------------------------------------------------------- #


@router.callback_query(ApplicationStates.city, F.data.in_({"cand_yes", "cand_no"}))
async def on_city(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(lives_in_city=callback.data == "cand_yes")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(texts.ASK_PHONE, reply_markup=CONTACT_KB)
    await state.set_state(ApplicationStates.phone)
    await callback.answer()


# ---------------------------------------------------------------------- #
# 5. Telefon
# ---------------------------------------------------------------------- #


async def _on_phone(message: Message, state: FSMContext, phone_raw: str) -> None:
    await state.update_data(phone=phone_raw)
    await message.answer(texts.ASK_EXPERIENCE)
    await state.set_state(ApplicationStates.experience)


@router.message(ApplicationStates.phone, F.contact)
async def on_phone_contact(message: Message, state: FSMContext) -> None:
    phone = _normalize_phone(message.contact.phone_number or "")
    if phone is None:
        await message.answer(texts.ASK_PHONE_INVALID, reply_markup=CONTACT_KB)
        return
    await _on_phone(message, state, phone)


@router.message(ApplicationStates.phone, F.text)
async def on_phone_text(message: Message, state: FSMContext) -> None:
    phone = _normalize_phone(message.text or "")
    if phone is None:
        await message.answer(texts.ASK_PHONE_INVALID, reply_markup=CONTACT_KB)
        return
    await _on_phone(message, state, phone)


# ---------------------------------------------------------------------- #
# 6. Ish tajribasi (staj) — yozadigan
# ---------------------------------------------------------------------- #


@router.message(ApplicationStates.experience, F.text)
async def on_experience(message: Message, state: FSMContext) -> None:
    experience = message.text.strip()
    if not experience:
        await message.answer(texts.ASK_EXPERIENCE)
        return
    await state.update_data(experience=experience)
    await message.answer(texts.ASK_RESUME, reply_markup=RESUME_SKIP_KB)
    await state.set_state(ApplicationStates.resume)


# ---------------------------------------------------------------------- #
# 7. Rezume — fayl (PDF/DOC) yoki golos (ovozli xabar)
# ---------------------------------------------------------------------- #


@router.callback_query(ApplicationStates.resume, F.data == "cand_skip_resume")
async def on_resume_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(resume_info="")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
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
# Yakunlash
# ---------------------------------------------------------------------- #


async def _finish(message: Message, state: FSMContext) -> None:
    """Arizani baholaydi, bazaga saqlaydi va HR guruhiga yuboradi."""
    data = await state.get_data()
    settings = get_settings()
    user = message.from_user

    answers = CandidateAnswers(
        full_name=data.get("full_name", ""),
        gender=data.get("gender", ""),
        age=data.get("age", 0),
        lives_in_city=data.get("lives_in_city", False),
        phone=data.get("phone", ""),
        experience=data.get("experience", ""),
        resume_info=data.get("resume_info", ""),
    )
    verdict = qualify_candidate(
        answers,
        min_age=settings.candidate_min_age,
        max_age=settings.candidate_max_age,
        required_city=settings.candidate_city,
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

    telegram_id = user.id if user else None
    telegram_username = user.username if user else None
    try:
        await save_application(
            answers,
            verdict,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            resume_file_kind=data.get("resume_file_kind"),
            resume_file_id=data.get("resume_file_id"),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Arizani bazaga saqlashda xato")

    await notify_hr_group(
        message.bot,
        settings,
        answers,
        verdict,
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        resume_file_kind=data.get("resume_file_kind"),
        resume_file_id=data.get("resume_file_id"),
        now=datetime.now(UTC).astimezone(settings.timezone),
    )
    await state.clear()
