"""Umumiy fallback handlerlar."""

from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards import main_menu
from app.db.models import Employee

router = Router(name="common")


@router.message()
async def fallback(message: Message, state: FSMContext, employee: Employee | None) -> None:
    current_state = await state.get_state()
    if current_state is not None:
        return  # FSM holatida bo'lsak, tegishli handler o'zi javob beradi
    if employee is None:
        await message.answer(
            "Iltimos, /start orqali ro'yxatdan o'ting yoki taklif kodingizni yuboring."
        )
        return
    await message.answer("Menyudan birini tanlang 👇", reply_markup=main_menu(employee))
