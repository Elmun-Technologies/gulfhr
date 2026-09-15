"""Target hisob-kitobi bo'yicha testlar."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.db.base import MetricType, Role, TargetPeriod
from app.db.models import Lead, Target
from app.db.session import session_scope
from app.services.employees import create_invite
from app.services.targets import build_progress, current_month_range


@pytest.mark.asyncio
async def test_revenue_target_progress():
    async with session_scope() as session:
        employee = await create_invite(session, "Test Sotuvchi", role=Role.SALES, amo_user_id=42)

        now = datetime.now(UTC)
        won_lead = Lead(
            id=1,
            name="Yopilgan bitim",
            price=10_000_000,
            status_id=142,
            pipeline_id=1,
            responsible_user_id=42,
            created_at=now - timedelta(days=2),
            closed_at=now - timedelta(days=1),
        )
        session.add(won_lead)

        start, end = current_month_range(date.today())
        target = Target(
            employee_id=employee.id,
            metric=MetricType.REVENUE,
            period=TargetPeriod.MONTHLY,
            period_start=start,
            period_end=end,
            target_value=100_000_000,
        )
        session.add(target)
        await session.flush()

        progress = await build_progress(session, employee, target)
        assert progress.achieved == 10_000_000
        assert progress.ratio == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_new_leads_target_progress():
    async with session_scope() as session:
        employee = await create_invite(session, "Ikkinchi Sotuvchi", role=Role.SALES, amo_user_id=7)
        now = datetime.now(UTC)
        for i in range(3):
            session.add(
                Lead(
                    id=100 + i,
                    name=f"Lid {i}",
                    price=0,
                    status_id=1,
                    pipeline_id=1,
                    responsible_user_id=7,
                    created_at=now,
                )
            )

        start, end = current_month_range(date.today())
        target = Target(
            employee_id=employee.id,
            metric=MetricType.NEW_LEADS,
            period=TargetPeriod.MONTHLY,
            period_start=start,
            period_end=end,
            target_value=10,
        )
        session.add(target)
        await session.flush()

        progress = await build_progress(session, employee, target)
        assert progress.achieved == 3
