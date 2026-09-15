"""Target (plan) hisob-kitob xizmati."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import MetricType
from app.db.models import AMO_STATUS_LOST, AMO_STATUS_WON, Employee, Lead, Target


@dataclass
class TargetProgress:
    target: Target
    achieved: float
    ratio: float          # achieved / target_value
    pace_ratio: float      # davr necha % o'tgani (kunlar bo'yicha)
    relative_ratio: float  # ratio / pace_ratio — sur'atga nisbatan bajarilish

    @property
    def is_lagging(self) -> bool:
        return self.pace_ratio > 0.1 and self.relative_ratio < 0.85

    @property
    def is_on_track(self) -> bool:
        return not self.is_lagging


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def compute_achieved(
    session: AsyncSession, employee: Employee, metric: MetricType, start: date, end: date
) -> float:
    """Berilgan davr uchun sotuvchining amoCRM ko'rsatkichini hisoblaydi."""
    if employee.amo_user_id is None:
        return 0.0

    start_dt = datetime(start.year, start.month, start.day, tzinfo=UTC)
    end_dt = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)

    if metric == MetricType.NEW_LEADS:
        result = await session.execute(
            select(Lead).where(
                Lead.responsible_user_id == employee.amo_user_id,
                Lead.created_at >= start_dt,
                Lead.created_at < end_dt,
            )
        )
        return float(len(result.scalars().all()))

    if metric == MetricType.WON_DEALS:
        result = await session.execute(
            select(Lead).where(
                Lead.responsible_user_id == employee.amo_user_id,
                Lead.status_id == AMO_STATUS_WON,
                Lead.closed_at >= start_dt,
                Lead.closed_at < end_dt,
            )
        )
        return float(len(result.scalars().all()))

    if metric == MetricType.REVENUE:
        result = await session.execute(
            select(Lead).where(
                Lead.responsible_user_id == employee.amo_user_id,
                Lead.status_id == AMO_STATUS_WON,
                Lead.closed_at >= start_dt,
                Lead.closed_at < end_dt,
            )
        )
        return float(sum(lead.price for lead in result.scalars().all()))

    if metric == MetricType.CONVERSION:
        total_result = await session.execute(
            select(Lead).where(
                Lead.responsible_user_id == employee.amo_user_id,
                Lead.created_at >= start_dt,
                Lead.created_at < end_dt,
                Lead.status_id.in_([AMO_STATUS_WON, AMO_STATUS_LOST]),
            )
        )
        closed_leads = total_result.scalars().all()
        if not closed_leads:
            return 0.0
        won = sum(1 for lead in closed_leads if lead.status_id == AMO_STATUS_WON)
        return round(won / len(closed_leads) * 100, 1)

    return 0.0


def _pace_ratio(start: date, end: date, today: date) -> float:
    total_days = (end - start).days + 1
    if total_days <= 0:
        return 1.0
    elapsed_days = (min(today, end) - start).days + 1
    elapsed_days = max(0, min(elapsed_days, total_days))
    return elapsed_days / total_days


async def get_active_targets(
    session: AsyncSession, employee_id: int, on_date: date
) -> list[Target]:
    result = await session.execute(
        select(Target).where(
            Target.employee_id == employee_id,
            Target.is_active.is_(True),
            Target.period_start <= on_date,
            Target.period_end >= on_date,
        )
    )
    return list(result.scalars().all())


async def build_progress(
    session: AsyncSession, employee: Employee, target: Target, today: date | None = None
) -> TargetProgress:
    today = today or datetime.now(UTC).date()
    achieved = await compute_achieved(
        session, employee, target.metric, target.period_start, target.period_end
    )
    ratio = achieved / target.target_value if target.target_value else 0.0
    pace_ratio = _pace_ratio(target.period_start, target.period_end, today)
    relative_ratio = ratio / pace_ratio if pace_ratio > 0 else ratio
    return TargetProgress(
        target=target,
        achieved=achieved,
        ratio=ratio,
        pace_ratio=pace_ratio,
        relative_ratio=relative_ratio,
    )


def current_month_range(today: date | None = None) -> tuple[date, date]:
    today = today or datetime.now(UTC).date()
    start = today.replace(day=1)
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    end = next_month - timedelta(days=1)
    return start, end


def current_week_range(today: date | None = None) -> tuple[date, date]:
    today = today or datetime.now(UTC).date()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end
