"""Jarayon nazorati qoidalar dvigateli.

Har bir funksiya bitta qoidani tekshiradi va topilgan buzilishlarni
`Alert` sifatida bazaga yozadi (dedup_key orqali takrorlanishning oldi olinadi).
Yangi qoida qo'shish: shu fayldagi patternga ergashib funksiya yozib,
`ALL_RULES` ro'yxatiga qo'shish kifoya.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.base import Severity
from app.db.models import Employee, Lead, PipelineStatus, Task
from app.services.targets import build_progress, get_active_targets

logger = logging.getLogger(__name__)


@dataclass
class RuleContext:
    session: AsyncSession
    settings: Settings
    amo_base_url: str
    now: datetime


@dataclass
class RuleFinding:
    dedup_key: str
    rule_code: str
    severity: Severity
    title: str
    message: str
    employee_id: int | None
    amo_user_id: int | None
    entity_type: str | None = None
    entity_id: int | None = None
    url: str | None = None


RuleFunc = Callable[[RuleContext], Awaitable[list[RuleFinding]]]


async def _employees_by_amo_id(ctx: RuleContext) -> dict[int, Employee]:
    result = await ctx.session.execute(
        select(Employee).where(Employee.amo_user_id.is_not(None), Employee.is_active.is_(True))
    )
    return {emp.amo_user_id: emp for emp in result.scalars() if emp.amo_user_id is not None}


def _lead_url(ctx: RuleContext, lead_id: int) -> str:
    return f"{ctx.amo_base_url}/leads/detail/{lead_id}"


# ---------------------------------------------------------------------- #
# Qoida 1: Yangi lidga birinchi javob SLA
# ---------------------------------------------------------------------- #

async def rule_first_response_sla(ctx: RuleContext) -> list[RuleFinding]:
    threshold = ctx.now - timedelta(minutes=ctx.settings.rule_first_response_minutes)
    result = await ctx.session.execute(
        select(Lead).where(
            Lead.first_touch_at.is_(None),
            Lead.created_at.is_not(None),
            Lead.created_at <= threshold,
            Lead.closed_at.is_(None),
        )
    )
    employees = await _employees_by_amo_id(ctx)
    findings: list[RuleFinding] = []
    for lead in result.scalars():
        employee = employees.get(lead.responsible_user_id) if lead.responsible_user_id else None
        waited = ctx.now - lead.created_at
        findings.append(
            RuleFinding(
                dedup_key=f"first_response:{lead.id}",
                rule_code="first_response_sla",
                severity=Severity.WARNING if waited < timedelta(hours=2) else Severity.CRITICAL,
                title="Yangi lidga javob berilmagan",
                message=(
                    f"«{lead.name or lead.id}» lidi {ctx.settings.rule_first_response_minutes} "
                    f"daqiqadan beri javobsiz turibdi."
                ),
                employee_id=employee.id if employee else None,
                amo_user_id=lead.responsible_user_id,
                entity_type="lead",
                entity_id=lead.id,
                url=_lead_url(ctx, lead.id),
            )
        )
    return findings


# ---------------------------------------------------------------------- #
# Qoida 2: Ochiq lidda vazifa yo'q
# ---------------------------------------------------------------------- #

async def rule_lead_without_task(ctx: RuleContext) -> list[RuleFinding]:
    threshold = ctx.now - timedelta(hours=ctx.settings.rule_lead_without_task_hours)
    result = await ctx.session.execute(
        select(Lead).where(
            Lead.closed_at.is_(None),
            Lead.has_open_task.is_(False),
            Lead.created_at.is_not(None),
            Lead.created_at <= threshold,
        )
    )
    employees = await _employees_by_amo_id(ctx)
    findings = []
    for lead in result.scalars():
        employee = employees.get(lead.responsible_user_id) if lead.responsible_user_id else None
        findings.append(
            RuleFinding(
                dedup_key=f"no_task:{lead.id}",
                rule_code="lead_without_task",
                severity=Severity.WARNING,
                title="Lidda faol vazifa yo'q",
                message=(
                    f"«{lead.name or lead.id}» lidida keyingi qadam bo'yicha vazifa qo'yilmagan."
                ),
                employee_id=employee.id if employee else None,
                amo_user_id=lead.responsible_user_id,
                entity_type="lead",
                entity_id=lead.id,
                url=_lead_url(ctx, lead.id),
            )
        )
    return findings


# ---------------------------------------------------------------------- #
# Qoida 3: Muddati o'tgan vazifalar
# ---------------------------------------------------------------------- #

async def rule_overdue_tasks(ctx: RuleContext) -> list[RuleFinding]:
    result = await ctx.session.execute(
        select(Task).where(
            Task.is_completed.is_(False),
            Task.complete_till.is_not(None),
            Task.complete_till < ctx.now,
        )
    )
    employees = await _employees_by_amo_id(ctx)
    findings = []
    for task in result.scalars():
        employee = (
            employees.get(task.responsible_user_id) if task.responsible_user_id else None
        )
        overdue = ctx.now - task.complete_till
        findings.append(
            RuleFinding(
                dedup_key=f"overdue_task:{task.id}",
                rule_code="overdue_task",
                severity=Severity.CRITICAL if overdue > timedelta(days=1) else Severity.WARNING,
                title="Vazifa muddati o'tgan",
                message=f"«{task.text[:120] or 'Vazifa'}» muddati o'tib ketgan.",
                employee_id=employee.id if employee else None,
                amo_user_id=task.responsible_user_id,
                entity_type=task.entity_type,
                entity_id=task.entity_id,
                url=_lead_url(ctx, task.entity_id)
                if task.entity_type == "leads" and task.entity_id
                else None,
            )
        )
    return findings


# ---------------------------------------------------------------------- #
# Qoida 4: Lid bosqichda qotib qolgan
# ---------------------------------------------------------------------- #

async def rule_status_stuck(ctx: RuleContext) -> list[RuleFinding]:
    threshold = ctx.now - timedelta(days=ctx.settings.rule_status_stuck_days)
    result = await ctx.session.execute(
        select(Lead).where(
            Lead.closed_at.is_(None),
            Lead.status_changed_at.is_not(None),
            Lead.status_changed_at <= threshold,
        )
    )
    employees = await _employees_by_amo_id(ctx)
    statuses = {
        row.id: row for row in (await ctx.session.execute(select(PipelineStatus))).scalars()
    }
    findings = []
    for lead in result.scalars():
        status = statuses.get(lead.status_id)
        default_days = ctx.settings.rule_status_stuck_days
        max_days = status.max_days if status and status.max_days else default_days
        stuck_days = (ctx.now - lead.status_changed_at).days
        if stuck_days < max_days:
            continue
        employee = employees.get(lead.responsible_user_id) if lead.responsible_user_id else None
        status_name = status.name if status else str(lead.status_id)
        findings.append(
            RuleFinding(
                dedup_key=f"status_stuck:{lead.id}:{lead.status_id}",
                rule_code="status_stuck",
                severity=Severity.WARNING if stuck_days < max_days * 2 else Severity.CRITICAL,
                title="Lid bosqichda qotib qolgan",
                message=(
                    f"«{lead.name or lead.id}» lidi «{status_name}» bosqichida "
                    f"{stuck_days} kundan beri turibdi."
                ),
                employee_id=employee.id if employee else None,
                amo_user_id=lead.responsible_user_id,
                entity_type="lead",
                entity_id=lead.id,
                url=_lead_url(ctx, lead.id),
            )
        )
    return findings


# ---------------------------------------------------------------------- #
# Qoida 5: Lidda umuman harakat yo'q
# ---------------------------------------------------------------------- #

async def rule_no_activity(ctx: RuleContext) -> list[RuleFinding]:
    threshold = ctx.now - timedelta(days=ctx.settings.rule_no_activity_days)
    result = await ctx.session.execute(
        select(Lead).where(
            Lead.closed_at.is_(None),
            Lead.updated_at.is_not(None),
            Lead.updated_at <= threshold,
        )
    )
    employees = await _employees_by_amo_id(ctx)
    findings = []
    for lead in result.scalars():
        employee = employees.get(lead.responsible_user_id) if lead.responsible_user_id else None
        idle_days = (ctx.now - lead.updated_at).days
        findings.append(
            RuleFinding(
                dedup_key=f"no_activity:{lead.id}",
                rule_code="no_activity",
                severity=Severity.CRITICAL,
                title="Lidda uzoq vaqt harakat yo'q",
                message=(
                    f"«{lead.name or lead.id}» lidida {idle_days} kundan beri "
                    "hech qanday o'zgarish yo'q."
                ),
                employee_id=employee.id if employee else None,
                amo_user_id=lead.responsible_user_id,
                entity_type="lead",
                entity_id=lead.id,
                url=_lead_url(ctx, lead.id),
            )
        )
    return findings


# ---------------------------------------------------------------------- #
# Qoida 6: Sotuvchida ochiq lidlar soni me'yordan oshgan
# ---------------------------------------------------------------------- #

async def rule_overloaded_sales(ctx: RuleContext) -> list[RuleFinding]:
    result = await ctx.session.execute(select(Lead).where(Lead.closed_at.is_(None)))
    counts: dict[int, int] = {}
    for lead in result.scalars():
        if lead.responsible_user_id:
            counts[lead.responsible_user_id] = counts.get(lead.responsible_user_id, 0) + 1

    employees = await _employees_by_amo_id(ctx)
    findings = []
    for amo_user_id, count in counts.items():
        if count <= ctx.settings.rule_max_open_leads:
            continue
        employee = employees.get(amo_user_id)
        findings.append(
            RuleFinding(
                dedup_key=f"overloaded:{amo_user_id}",
                rule_code="overloaded_sales",
                severity=Severity.WARNING,
                title="Sotuvchida ochiq lidlar soni ko'p",
                message=(
                    f"Hozirda {count} ta ochiq lid mavjud "
                    f"(limit: {ctx.settings.rule_max_open_leads})."
                ),
                employee_id=employee.id if employee else None,
                amo_user_id=amo_user_id,
                entity_type="employee",
                entity_id=employee.id if employee else None,
            )
        )
    return findings


# ---------------------------------------------------------------------- #
# Qoida 7: Target sur'atidan orqada qolish
# ---------------------------------------------------------------------- #

async def rule_target_lagging(ctx: RuleContext) -> list[RuleFinding]:
    today = ctx.now.date()
    result = await ctx.session.execute(select(Employee).where(Employee.is_active.is_(True)))
    findings = []
    for employee in result.scalars():
        targets = await get_active_targets(ctx.session, employee.id, today)
        for target in targets:
            progress = await build_progress(ctx.session, employee, target, today)
            if not progress.is_lagging:
                continue
            lag_percent = round((1 - progress.relative_ratio) * 100)
            if lag_percent < ctx.settings.rule_target_lag_percent:
                continue
            findings.append(
                RuleFinding(
                    dedup_key=f"target_lag:{target.id}:{today.isocalendar()[1]}",
                    rule_code="target_lagging",
                    severity=Severity.WARNING if lag_percent < 30 else Severity.CRITICAL,
                    title="Target bo'yicha orqada qolish",
                    message=(
                        f"{target.metric.label_uz}: {target.period.label_uz.lower()} rejadan "
                        f"~{lag_percent}% orqada (bajarildi: {round(progress.achieved)} / "
                        f"{round(target.target_value)} {target.metric.unit_uz})."
                    ),
                    employee_id=employee.id,
                    amo_user_id=employee.amo_user_id,
                    entity_type="target",
                    entity_id=target.id,
                )
            )
    return findings


ALL_RULES: list[RuleFunc] = [
    rule_first_response_sla,
    rule_lead_without_task,
    rule_overdue_tasks,
    rule_status_stuck,
    rule_no_activity,
    rule_overloaded_sales,
    rule_target_lagging,
]


async def run_all_rules(
    session: AsyncSession, settings: Settings | None = None
) -> list[RuleFinding]:
    settings = settings or get_settings()
    ctx = RuleContext(
        session=session,
        settings=settings,
        amo_base_url=(
            f"https://{settings.amo_subdomain}.amocrm.ru" if settings.amo_subdomain else ""
        ),
        now=datetime.now(UTC),
    )
    findings: list[RuleFinding] = []
    for rule in ALL_RULES:
        try:
            findings.extend(await rule(ctx))
        except Exception:  # noqa: BLE001 - bitta qoida ishlamasa, qolganlari ishlashda davom etsin
            logger.exception("Qoida bajarilishida xato: %s", rule.__name__)
    return findings
