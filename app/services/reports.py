"""Kunlik/haftalik hisobot va shaxsiy dashboard matnlarini shakllantirish."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Role
from app.db.models import AMO_STATUS_WON, Alert, Employee, Lead, Task
from app.services.formatting import escape_html, money, number, progress_bar, status_emoji
from app.services.targets import build_progress, current_month_range, get_active_targets


async def _open_leads_count(session: AsyncSession, amo_user_id: int) -> int:
    result = await session.execute(
        select(Lead).where(Lead.responsible_user_id == amo_user_id, Lead.closed_at.is_(None))
    )
    return len(result.scalars().all())


async def _overdue_tasks_count(session: AsyncSession, amo_user_id: int, now: datetime) -> int:
    result = await session.execute(
        select(Task).where(
            Task.responsible_user_id == amo_user_id,
            Task.is_completed.is_(False),
            Task.complete_till.is_not(None),
            Task.complete_till < now,
        )
    )
    return len(result.scalars().all())


async def _today_stats(session: AsyncSession, amo_user_id: int, today: date) -> dict[str, float]:
    start = datetime(today.year, today.month, today.day, tzinfo=UTC)
    end = start + timedelta(days=1)

    new_leads_result = await session.execute(
        select(Lead).where(
            Lead.responsible_user_id == amo_user_id,
            Lead.created_at >= start,
            Lead.created_at < end,
        )
    )
    won_result = await session.execute(
        select(Lead).where(
            Lead.responsible_user_id == amo_user_id,
            Lead.status_id == AMO_STATUS_WON,
            Lead.closed_at >= start,
            Lead.closed_at < end,
        )
    )
    won_leads = won_result.scalars().all()
    return {
        "new_leads": len(new_leads_result.scalars().all()),
        "won_deals": len(won_leads),
        "revenue": sum(lead.price for lead in won_leads),
    }


async def build_personal_dashboard(session: AsyncSession, employee: Employee) -> str:
    """Sotuvchi uchun shaxsiy holat: bugungi natija, ochiq lidlar, targetlar."""
    now = datetime.now(UTC)
    today = now.date()
    name = escape_html(employee.full_name)
    lines = [f"👤 <b>{name}</b>", ""]

    if employee.amo_user_id is None:
        lines.append("⚠️ amoCRM akkauntingiz hali bog'lanmagan. Administratorga murojaat qiling.")
        return "\n".join(lines)

    stats = await _today_stats(session, employee.amo_user_id, today)
    open_leads = await _open_leads_count(session, employee.amo_user_id)
    overdue = await _overdue_tasks_count(session, employee.amo_user_id, now)

    lines.append("📅 <b>Bugun:</b>")
    lines.append(f"  • Yangi lidlar: {number(stats['new_leads'])} ta")
    lines.append(f"  • Yopilgan bitimlar: {number(stats['won_deals'])} ta")
    lines.append(f"  • Savdo: {money(stats['revenue'])} so'm")
    lines.append("")
    lines.append(f"📂 Ochiq lidlar: <b>{open_leads}</b> ta")
    if overdue:
        lines.append(f"🔴 Muddati o'tgan vazifalar: <b>{overdue}</b> ta")
    else:
        lines.append("✅ Muddati o'tgan vazifalar yo'q")

    targets = await get_active_targets(session, employee.id, today)
    if targets:
        lines.append("")
        lines.append("🎯 <b>Targetlar:</b>")
        for target in targets:
            progress = await build_progress(session, employee, target, today)
            bar = progress_bar(min(progress.ratio, 1.0))
            emoji = status_emoji(progress.ratio, progress.pace_ratio)
            lines.append(
                f"  {emoji} {target.metric.label_uz} ({target.period.label_uz.lower()}): "
                f"{bar} {round(progress.ratio * 100)}%"
            )
            lines.append(
                f"     {number(progress.achieved)} / {number(target.target_value)} "
                f"{target.metric.unit_uz}"
            )
    else:
        lines.append("")
        lines.append("ℹ️ Sizga hali target belgilanmagan.")

    return "\n".join(lines)


async def build_open_alerts_list(session: AsyncSession, employee: Employee, limit: int = 10) -> str:
    if employee.amo_user_id is None:
        return "amoCRM akkauntingiz bog'lanmagan."
    result = await session.execute(
        select(Alert)
        .where(Alert.amo_user_id == employee.amo_user_id, Alert.resolved_at.is_(None))
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    alerts = list(result.scalars())
    if not alerts:
        return "✅ Hozircha ogohlantirishlar yo'q. Ajoyib ish!"

    lines = ["📋 <b>Ochiq ogohlantirishlar:</b>", ""]
    for alert in alerts:
        lines.append(f"{alert.severity.emoji} {alert.title}")
        lines.append(f"   {alert.message}")
        if alert.url:
            lines.append(f"   🔗 <a href=\"{alert.url}\">Ochish</a>")
        lines.append("")
    return "\n".join(lines).strip()


async def build_team_overview(session: AsyncSession, now: datetime | None = None) -> str:
    """Bo'lim boshlig'i/HR uchun jamoaning umumiy holati."""
    now = now or datetime.now(UTC)
    today = now.date()

    result = await session.execute(
        select(Employee).where(Employee.role == Role.SALES, Employee.is_active.is_(True))
    )
    sales = list(result.scalars())

    open_alerts_result = await session.execute(select(Alert).where(Alert.resolved_at.is_(None)))
    open_alerts = list(open_alerts_result.scalars())
    alerts_by_employee: dict[int, int] = {}
    for alert in open_alerts:
        if alert.employee_id:
            alerts_by_employee[alert.employee_id] = alerts_by_employee.get(alert.employee_id, 0) + 1

    lines = [f"📊 <b>Jamoa holati</b> — {today.strftime('%d.%m.%Y')}", ""]
    if not sales:
        lines.append("Faol sotuvchilar ro'yxatga olinmagan.")
        return "\n".join(lines)

    total_open_leads = 0
    total_overdue = 0
    rows: list[tuple[str, int, int, str]] = []

    for employee in sales:
        if employee.amo_user_id is None:
            rows.append((employee.full_name, 0, 0, "bog'lanmagan"))
            continue
        open_leads = await _open_leads_count(session, employee.amo_user_id)
        overdue = await _overdue_tasks_count(session, employee.amo_user_id, now)
        total_open_leads += open_leads
        total_overdue += overdue

        month_start, month_end = current_month_range(today)
        targets = await get_active_targets(session, employee.id, today)
        target_note = "—"
        if targets:
            progress = await build_progress(session, employee, targets[0], today)
            target_note = f"{round(progress.ratio * 100)}%"

        alerts_count = alerts_by_employee.get(employee.id, 0)
        status = f"lid:{open_leads} muddati o'tgan:{overdue} target:{target_note} ⚠️{alerts_count}"
        rows.append((employee.full_name, open_leads, overdue, status))

    rows.sort(key=lambda r: r[2], reverse=True)  # muddati o'tganlar ko'p bo'lganlar tepada
    for full_name, _open_leads, _overdue, status in rows:
        lines.append(f"👤 <b>{escape_html(full_name)}</b> — {status}")

    lines.append("")
    lines.append(f"Jami ochiq lidlar: <b>{total_open_leads}</b>")
    lines.append(f"Jami muddati o'tgan vazifalar: <b>{total_overdue}</b>")
    lines.append(f"Jami ochiq ogohlantirishlar: <b>{len(open_alerts)}</b>")
    return "\n".join(lines)


async def build_morning_digest(session: AsyncSession, employee: Employee) -> str:
    header = "☀️ <b>Xayrli tong! Bugungi holat:</b>\n"
    body = await build_personal_dashboard(session, employee)
    return header + "\n" + body


async def build_evening_digest(session: AsyncSession, employee: Employee) -> str:
    header = "🌙 <b>Kun yakuni:</b>\n"
    body = await build_personal_dashboard(session, employee)
    alerts = await build_open_alerts_list(session, employee, limit=5)
    return header + "\n" + body + "\n\n" + alerts
