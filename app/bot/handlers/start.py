"""/start — ariza oqimini boshlash va yordam."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.handlers.candidates import start_candidate_application

logger = logging.getLogger(__name__)
router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await start_candidate_application(message, state)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "🤖 <b>Gulf HR bot</b>\n\n"
        "Gulf — oziq-ovqat ingredientlari yetkazib beruvchi kompaniya. "
        "Bot <b>Sotuv menejeri / B2B menejer</b> vakansiyasi uchun "
        "nomzodlarni saralaydi:\n"
        "• bir nechta savol beradi (ism, yosh, shahar, rus tili, telefon, "
        "staj, rezume),\n"
        "• javoblarni vakansiya talablari bilan solishtiradi,\n"
        "• natijani nomzodga aytadi va to'liq kartani HR guruhiga yuboradi.\n\n"
        "Arizani boshlash uchun: /start\n"
        "Arizani bekor qilish uchun: /cancel"
    )
