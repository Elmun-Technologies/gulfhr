"""Qoidalar dvigateli bo'yicha testlar."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.db.base import Role
from app.db.models import Lead, Task
from app.db.session import session_scope
from app.services.employees import create_invite
from app.services.rules import run_all_rules


@pytest.mark.asyncio
async def test_first_response_sla_triggers_for_untouched_lead():
    async with session_scope() as session:
        await create_invite(session, "Sotuvchi A", role=Role.SALES, amo_user_id=11)
        now = datetime.now(UTC)
        session.add(
            Lead(
                id=1,
                name="Yangi lid",
                price=0,
                status_id=1,
                pipeline_id=1,
                responsible_user_id=11,
                created_at=now - timedelta(minutes=30),
                updated_at=now - timedelta(minutes=30),
                first_touch_at=None,
            )
        )
        await session.flush()

        findings = await run_all_rules(session)
        codes = [f.rule_code for f in findings]
        assert "first_response_sla" in codes


@pytest.mark.asyncio
async def test_no_alert_when_lead_freshly_created():
    async with session_scope() as session:
        await create_invite(session, "Sotuvchi B", role=Role.SALES, amo_user_id=22)
        now = datetime.now(UTC)
        session.add(
            Lead(
                id=2,
                name="Yangi lid",
                price=0,
                status_id=1,
                pipeline_id=1,
                responsible_user_id=22,
                created_at=now,
                updated_at=now,
                first_touch_at=None,
                has_open_task=True,
                status_changed_at=now,
            )
        )
        await session.flush()

        findings = await run_all_rules(session)
        assert findings == []


@pytest.mark.asyncio
async def test_overdue_task_triggers():
    async with session_scope() as session:
        await create_invite(session, "Sotuvchi C", role=Role.SALES, amo_user_id=33)
        now = datetime.now(UTC)
        session.add(
            Task(
                id=1,
                entity_id=999,
                entity_type="leads",
                text="Qo'ng'iroq qilish",
                responsible_user_id=33,
                complete_till=now - timedelta(hours=5),
                is_completed=False,
            )
        )
        await session.flush()

        findings = await run_all_rules(session)
        codes = [f.rule_code for f in findings]
        assert "overdue_task" in codes
