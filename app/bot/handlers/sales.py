"""Sotuvchi uchun shaxsiy menyu: natija, ogohlantirishlar, bildirishnomalar."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    BTN_MY_ALERTS,
    BTN_MY_STATUS,
    BTN_NOTIFICATIONS,
    notifications_keyboard,
)
from app.db.models import Employee
from app.services.reports import build_open_alerts_list, build_personal_dashboard

router = Router(name="sales")


@router.message(F.text == BTN_MY_STATUS)
async def my_status(message: Message, session: AsyncSession, employee: Employee | None) -> None:
    if employee is None:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return
    text = await build_personal_dashboard(session, employee)
    await message.answer(text, disable_web_page_preview=True)


@router.message(F.text == BTN_MY_ALERTS)
async def my_alerts(message: Message, session: AsyncSession, employee: Employee | None) -> None:
    if employee is None:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return
    text = await build_open_alerts_list(session, employee)
    await message.answer(text, disable_web_page_preview=True)


@router.message(F.text == BTN_NOTIFICATIONS)
async def notifications_settings(message: Message, employee: Employee | None) -> None:
    if employee is None:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return
    state = "yoqilgan ✅" if employee.notifications_enabled else "o'chirilgan ⛔️"
    await message.answer(
        f"Hozir bildirishnomalar holati: <b>{state}</b>",
        reply_markup=notifications_keyboard(employee.notifications_enabled),
    )


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery, employee: Employee | None) -> None:
    if employee is None or not callback.message:
        await callback.answer("Xatolik: foydalanuvchi topilmadi.", show_alert=True)
        return
    employee.notifications_enabled = not employee.notifications_enabled
    state = "yoqildi ✅" if employee.notifications_enabled else "o'chirildi ⛔️"
    await callback.message.edit_text(f"Bildirishnomalar {state}.")
    await callback.answer()
