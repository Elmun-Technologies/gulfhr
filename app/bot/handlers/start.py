"""/start — til tanlash va ariza oqimini boshlash, /help."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.handlers.candidates import start_candidate_application

logger = logging.getLogger(__name__)
router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(
    message: Message, state: FSMContext, command: CommandObject
) -> None:
    """/start [til] — arizani boshlaydi.

    Reklama havolalarida til oldindan berilishi mumkin (`t.me/bot?start=ru`) —
    u holda til tanlash oynasi o'tkazib yuboriladi va suhbat darhol ruscha
    boshlanadi.
    """
    payload = (command.args or "").strip()
    await start_candidate_application(message, state, requested_lang=payload or None)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "🤖 <b>Gulf HR bot</b>\n\n"
        "Gulf — oziq-ovqat ingredientlari yetkazib beruvchi kompaniya. "
        "Bot <b>Sotuv menejeri / B2B menejer</b> vakansiyasi uchun "
        "nomzodlarni saralaydi:\n"
        "• avval tilni so'raydi (🇺🇿 o'zbekcha / 🇷🇺 ruscha),\n"
        "• keyin bir nechta savol beradi (ism, jins, yosh, shahar, rus tili, "
        "telefon, staj, rezume),\n"
        "• javoblarni vakansiya talablari bilan solishtiradi,\n"
        "• natijani nomzodga aytadi va to'liq kartani HR guruhiga yuboradi.\n\n"
        "Arizani boshlash: /start\n"
        "Tilni almashtirish: /lang\n"
        "Arizani bekor qilish: /cancel\n\n"
        "🇷🇺 <b>По-русски:</b> начните с /start — бот спросит язык и задаст "
        "несколько вопросов. Отменить заявку: /cancel, сменить язык: /lang."
    )
