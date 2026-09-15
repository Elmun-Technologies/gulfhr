"""/start — ro'yxatdan o'tish va asosiy menyu."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.candidates import start_candidate_application
from app.bot.keyboards import main_menu
from app.config import get_settings
from app.db.base import Role
from app.db.models import Employee
from app.services.employees import get_employee_by_invite, link_telegram_account

logger = logging.getLogger(__name__)
router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    state: FSMContext,
    employee: Employee | None,
) -> None:
    if employee is not None:
        await message.answer(
            f"Xush kelibsiz, {employee.full_name}!\nRol: {employee.role.label_uz}",
            reply_markup=main_menu(employee),
        )
        return

    settings = get_settings()
    code = (command.args or "").strip()

    # Birinchi admin: hali bironta xodim yo'q va foydalanuvchi ADMIN_TELEGRAM_IDS ichida bo'lsa
    if not code and message.from_user and message.from_user.id in settings.admin_telegram_ids:
        employee = Employee(
            telegram_id=message.from_user.id,
            telegram_username=message.from_user.username,
            full_name=message.from_user.full_name,
            role=Role.ADMIN,
        )
        session.add(employee)
        await session.flush()
        await message.answer(
            "Siz administrator sifatida ro'yxatdan o'tdingiz.\n"
            "Endi /amosetup buyrug'i bilan amoCRM ulanishini tekshiring va xodimlarni qo'shing.",
            reply_markup=main_menu(employee),
        )
        return

    if not code:
        # Taklif kodi yo'q va admin ro'yxatida yo'q — vakansiya nomzodi
        # deb hisoblaymiz va ariza oqimini boshlaymiz.
        await start_candidate_application(message, state)
        return

    invited = await get_employee_by_invite(session, code)
    if invited is None:
        await message.answer("❌ Kod noto'g'ri yoki muddati o'tgan. Rahbaringizga murojaat qiling.")
        return

    if not message.from_user:
        return

    await link_telegram_account(session, invited, message.from_user.id, message.from_user.username)
    await message.answer(
        f"✅ Xush kelibsiz, {invited.full_name}!\nRol: {invited.role.label_uz}\n\n"
        "Endi menyudan foydalanishingiz mumkin.",
        reply_markup=main_menu(invited),
    )
    logger.info("Yangi xodim ulandi: %s (telegram_id=%s)", invited.full_name, message.from_user.id)


@router.message(Command("help"))
async def cmd_help(message: Message, employee: Employee | None) -> None:
    text = (
        "🤖 <b>Gulf HR bot</b>\n\n"
        "Bu bot amoCRM'dagi har bir sotuvchining jarayonini nazorat qiladi:\n"
        "• yangi lidga o'z vaqtida javob berilishi,\n"
        "• vazifalarning muddatida bajarilishi,\n"
        "• lidlarning bosqichlarda qotib qolmasligi,\n"
        "• target (reja) bajarilishi.\n\n"
        "Qoidabuzarlik aniqlansa, tegishli xodimga va (kechiksa) rahbariyatga avtomatik xabar boradi."
    )
    if employee and employee.role.is_manager:
        text += (
            "\n\n<b>Rahbar buyruqlari:</b>\n"
            "/team — jamoa holati\n"
            "/addemployee — yangi xodim uchun taklif yaratish\n"
            "/settarget — target belgilash"
        )
    await message.answer(text)
