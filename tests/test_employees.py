"""Xodim ro'yxatga olish (invite) oqimi bo'yicha testlar."""

from __future__ import annotations

import pytest

from app.db.base import Role
from app.db.session import session_scope
from app.services.employees import (
    create_invite,
    get_employee_by_invite,
    link_telegram_account,
)


@pytest.mark.asyncio
async def test_invite_and_link_flow():
    async with session_scope() as session:
        employee = await create_invite(session, "Yangi Xodim", role=Role.SALES)
        assert employee.invite_code
        assert employee.telegram_id is None

        code = employee.invite_code
        found = await get_employee_by_invite(session, code.lower())  # katta-kichik harf farqsiz
        assert found is not None
        assert found.id == employee.id

        await link_telegram_account(session, found, telegram_id=123456, username="testuser")
        assert found.telegram_id == 123456
        assert found.invite_code is None
