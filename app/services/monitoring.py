"""Qoidalar natijalarini bazaga yozish va Telegram orqali yuborish."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import Alert, Employee
from app.services.rules import RuleFinding, run_all_rules

logger = logging.getLogger(__name__)

# Shu vaqtdan ko'p ochiq turgan alert avtomatik boshliqqa eskalatsiya qilinadi
ESCALATE_AFTER = timedelta(hours=2)
# Shu vaqt davomida qayta ko'rilmagan (ya'ni endi buzilmagan) alertlar yopiladi
STALE_TIMEOUT = timedelta(hours=6)


async def upsert_findings(session: AsyncSession, findings: list[RuleFinding]) -> list[Alert]:
    """Topilgan buzilishlarni saqlaydi. Yangi bo'lganlarini qaytaradi (bildirishnoma uchun)."""
    now = datetime.now(UTC)
    seen_keys = {f.dedup_key for f in findings}
    new_alerts: list[Alert] = []

    existing_result = await session.execute(
        select(Alert).where(Alert.dedup_key.in_(seen_keys)) if seen_keys else select(Alert).where(False)
    )
    existing = {alert.dedup_key: alert for alert in existing_result.scalars()}

    for finding in findings:
        alert = existing.get(finding.dedup_key)
        if alert is None:
            alert = Alert(
                dedup_key=finding.dedup_key,
                rule_code=finding.rule_code,
                severity=finding.severity,
                employee_id=finding.employee_id,
                amo_user_id=finding.amo_user_id,
                entity_type=finding.entity_type,
                entity_id=finding.entity_id,
                title=finding.title,
                message=finding.message,
                url=finding.url,
                created_at=now,
                last_seen_at=now,
            )
            session.add(alert)
            new_alerts.append(alert)
        else:
            alert.last_seen_at = now
            alert.message = finding.message
            alert.severity = finding.severity
            if alert.resolved_at is not None:
                # Muammo qayta paydo bo'ldi
                alert.resolved_at = None
                alert.created_at = now
                alert.notified_at = None
                alert.escalated_at = None
                new_alerts.append(alert)

    # Endi buzilmagan (ro'yxatda yo'q) ochiq alertlarni yopamiz
    open_result = await session.execute(select(Alert).where(Alert.resolved_at.is_(None)))
    for alert in open_result.scalars():
        if alert.dedup_key in seen_keys:
            continue
        if alert.last_seen_at and now - alert.last_seen_at < STALE_TIMEOUT:
            continue
        alert.resolved_at = now

    await session.flush()
    return new_alerts


async def notify_new_alerts(bot: Bot, session: AsyncSession, alerts: list[Alert]) -> None:
    """Yangi alertlarni tegishli sotuvchiga yuboradi."""
    for alert in alerts:
        if alert.employee_id is None:
            continue
        employee = await session.get(Employee, alert.employee_id)
        if not employee or not employee.telegram_id or not employee.notifications_enabled:
            continue
        text = (
            f"{alert.severity.emoji} <b>{alert.title}</b>\n\n"
            f"{alert.message}"
        )
        if alert.url:
            text += f"\n\n🔗 <a href=\"{alert.url}\">amoCRM'da ochish</a>"
        try:
            await bot.send_message(employee.telegram_id, text, disable_web_page_preview=True)
            alert.notified_at = datetime.now(UTC)
        except TelegramAPIError:
            logger.warning("Xabar yuborilmadi: employee_id=%s", employee.id, exc_info=True)


async def escalate_stale_alerts(bot: Bot, session: AsyncSession, settings: Settings | None = None) -> None:
    """Uzoq vaqt hal qilinmagan alertlarni boshqaruv guruhiga yuboradi."""
    settings = settings or get_settings()
    if not settings.management_chat_id:
        return

    now = datetime.now(UTC)
    threshold = now - ESCALATE_AFTER
    result = await session.execute(
        select(Alert).where(
            Alert.resolved_at.is_(None),
            Alert.escalated_at.is_(None),
            Alert.notified_at.is_not(None),
            Alert.notified_at <= threshold,
        )
    )
    for alert in result.scalars():
        employee = await session.get(Employee, alert.employee_id) if alert.employee_id else None
        who = employee.full_name if employee else "Noma'lum xodim"
        text = (
            f"{alert.severity.emoji} <b>Eskalatsiya:</b> {alert.title}\n"
            f"👤 {who}\n\n{alert.message}"
        )
        if alert.url:
            text += f"\n\n🔗 <a href=\"{alert.url}\">amoCRM'da ochish</a>"
        try:
            await bot.send_message(settings.management_chat_id, text, disable_web_page_preview=True)
            alert.escalated_at = now
        except TelegramAPIError:
            logger.warning("Eskalatsiya xabari yuborilmadi: alert_id=%s", alert.id, exc_info=True)


async def run_monitoring_cycle(
    bot: Bot, session: AsyncSession, settings: Settings | None = None
) -> int:
    """To'liq nazorat sikli: qoidalarni tekshirish -> saqlash -> xabar berish -> eskalatsiya."""
    settings = settings or get_settings()
    findings = await run_all_rules(session, settings)
    new_alerts = await upsert_findings(session, findings)
    await notify_new_alerts(bot, session, new_alerts)
    await escalate_stale_alerts(bot, session, settings)
    return len(new_alerts)
