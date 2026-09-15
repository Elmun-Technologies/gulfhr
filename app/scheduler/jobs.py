"""Rejalashtiriladigan vazifalar."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select

from app.amocrm.auth import AmoAuthError
from app.amocrm.client import AmoApiError
from app.amocrm.sync import run_sync
from app.config import get_settings
from app.db.base import Role
from app.db.models import Employee
from app.db.session import session_scope
from app.services.monitoring import run_monitoring_cycle
from app.services.reports import build_evening_digest, build_morning_digest, build_team_overview

logger = logging.getLogger(__name__)


async def job_sync_and_monitor(bot: Bot) -> None:
    """amoCRM bilan sinxronlash + qoidalarni tekshirish + xabar berish."""
    settings = get_settings()
    if not settings.amo_configured:
        logger.debug("amoCRM sozlanmagan — sinxronizatsiya o'tkazib yuborildi")
        return
    try:
        await run_sync()
    except (AmoAuthError, AmoApiError):
        logger.exception("Rejalashtirilgan sinxronizatsiya muvaffaqiyatsiz tugadi")
        return

    async with session_scope() as session:
        new_count = await run_monitoring_cycle(bot, session)
        if new_count:
            logger.info("Nazorat sikli: %s ta yangi ogohlantirish", new_count)


async def job_morning_digest(bot: Bot) -> None:
    async with session_scope() as session:
        result = await session.execute(
            select(Employee).where(
                Employee.role == Role.SALES,
                Employee.is_active.is_(True),
                Employee.telegram_id.is_not(None),
                Employee.notifications_enabled.is_(True),
            )
        )
        for employee in result.scalars():
            try:
                text = await build_morning_digest(session, employee)
                await bot.send_message(employee.telegram_id, text)
            except TelegramAPIError:
                logger.warning("Tong xabari yuborilmadi: %s", employee.id, exc_info=True)


async def job_evening_digest(bot: Bot) -> None:
    async with session_scope() as session:
        result = await session.execute(
            select(Employee).where(
                Employee.role == Role.SALES,
                Employee.is_active.is_(True),
                Employee.telegram_id.is_not(None),
                Employee.notifications_enabled.is_(True),
            )
        )
        for employee in result.scalars():
            try:
                text = await build_evening_digest(session, employee)
                await bot.send_message(employee.telegram_id, text)
            except TelegramAPIError:
                logger.warning("Kechki xabar yuborilmadi: %s", employee.id, exc_info=True)


async def job_weekly_report(bot: Bot) -> None:
    settings = get_settings()
    async with session_scope() as session:
        text = "🗓 <b>Haftalik hisobot</b>\n\n" + await build_team_overview(session)

        managers_result = await session.execute(
            select(Employee).where(
                Employee.role.in_([Role.HEAD, Role.HR, Role.ADMIN]),
                Employee.is_active.is_(True),
                Employee.telegram_id.is_not(None),
            )
        )
        for manager in managers_result.scalars():
            try:
                await bot.send_message(manager.telegram_id, text)
            except TelegramAPIError:
                logger.warning("Haftalik hisobot yuborilmadi: %s", manager.id, exc_info=True)

        if settings.management_chat_id:
            try:
                await bot.send_message(settings.management_chat_id, text)
            except TelegramAPIError:
                logger.warning("Haftalik hisobot guruhga yuborilmadi", exc_info=True)
