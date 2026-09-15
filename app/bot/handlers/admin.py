"""Administrator buyruqlari: amoCRM ulanishi va qo'lda sinxronizatsiya."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.amocrm.auth import AmoAuthError
from app.amocrm.client import AmoApiError, AmoCrmClient
from app.amocrm.sync import run_sync
from app.bot.keyboards import BTN_SYNC_NOW
from app.config import get_settings
from app.db.base import Role
from app.db.models import Employee
from app.services.monitoring import run_monitoring_cycle

router = Router(name="admin")


def _require_admin(employee: Employee | None) -> bool:
    return employee is not None and employee.role == Role.ADMIN


@router.message(Command("amosetup"))
async def amo_setup_check(message: Message, employee: Employee | None) -> None:
    if not _require_admin(employee):
        await message.answer("Bu buyruq faqat administrator uchun.")
        return
    settings = get_settings()
    if not settings.amo_configured:
        await message.answer(
            "❌ amoCRM sozlanmagan. .env faylida AMO_SUBDOMAIN va "
            "(AMO_LONG_TOKEN yoki AMO_CLIENT_ID/SECRET + AMO_AUTH_CODE) ni to'ldiring."
        )
        return
    try:
        async with AmoCrmClient(settings) as client:
            account = await client.get_account()
    except (AmoAuthError, AmoApiError) as exc:
        await message.answer(f"❌ Ulanishda xato: {exc}")
        return
    name = account.get("name") if account else "?"
    await message.answer(f"✅ amoCRM'ga ulanish muvaffaqiyatli.\nAkkaunt: <b>{name}</b>")


@router.message(F.text == BTN_SYNC_NOW)
@router.message(Command("sync"))
async def manual_sync(message: Message, session: AsyncSession, employee: Employee | None) -> None:
    if not _require_admin(employee):
        await message.answer("Bu buyruq faqat administrator uchun.")
        return
    settings = get_settings()
    if not settings.amo_configured:
        await message.answer("❌ amoCRM sozlanmagan.")
        return

    await message.answer("⏳ Sinxronizatsiya boshlandi...")
    try:
        result = await run_sync()
    except (AmoAuthError, AmoApiError) as exc:
        await message.answer(f"❌ Sinxronizatsiya xatosi: {exc}")
        return

    from app.bot.bot_instance import get_bot  # aylanma importdan qochish uchun

    bot = get_bot()
    new_alerts_count = await run_monitoring_cycle(bot, session)
    await message.answer(
        f"✅ Sinxronizatsiya tugadi: {result.summary_uz()}\n"
        f"🆕 Yangi ogohlantirishlar: {new_alerts_count}"
    )
