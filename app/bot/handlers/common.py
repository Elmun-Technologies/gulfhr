"""Umumiy fallback handler."""

from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router(name="common")


@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    if await state.get_state() is not None:
        return  # FSM holatida bo'lsak, tegishli handler o'zi javob beradi
    await message.answer(
        "Assalomu alaykum! Arizani boshlash uchun /start buyrug'ini yuboring 👇"
    )
