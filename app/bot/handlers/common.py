"""Umumiy fallback handler — hech bir aniq handler ishlamaganda."""

from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router(name="common")


@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    if await state.get_state() is not None:
        # Boshqa router'ning FSM holati (nomzodlar oqimi o'z fallback'iga ega —
        # app/bot/handlers/candidates.py::on_unexpected). Bu yerga yetib kelsa,
        # nomzodga baribir yo'l ko'rsatamiz: jim qolish — eng yomon variant.
        await message.answer("Arizani davom ettirish uchun /start ni bosing 👇")
        return
    await message.answer(
        "Assalomu alaykum! Arizani boshlash uchun /start buyrug'ini yuboring 👇\n\n"
        "Здравствуйте! Чтобы начать, отправьте /start 👇"
    )
