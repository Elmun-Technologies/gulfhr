"""Xodimlarni ro'yxatga olish va rol boshqaruvi."""

from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Role
from app.db.models import AmoUser, Employee


def generate_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


async def create_invite(
    session: AsyncSession,
    full_name: str,
    role: Role = Role.SALES,
    amo_user_id: int | None = None,
    position: str | None = None,
) -> Employee:
    """Yangi xodim uchun taklif (invite) yaratadi — u botga /start <kod> bilan qo'shiladi."""
    code = generate_invite_code()
    while await get_employee_by_invite(session, code):
        code = generate_invite_code()

    employee = Employee(
        full_name=full_name,
        role=role,
        amo_user_id=amo_user_id,
        position=position,
        invite_code=code,
        is_active=True,
    )
    session.add(employee)
    await session.flush()
    return employee


async def get_employee_by_invite(session: AsyncSession, code: str) -> Employee | None:
    result = await session.execute(select(Employee).where(Employee.invite_code == code.strip().upper()))
    return result.scalar_one_or_none()


async def get_employee_by_telegram_id(session: AsyncSession, telegram_id: int) -> Employee | None:
    result = await session.execute(select(Employee).where(Employee.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def link_telegram_account(
    session: AsyncSession, employee: Employee, telegram_id: int, username: str | None
) -> None:
    employee.telegram_id = telegram_id
    employee.telegram_username = username
    employee.invite_code = None  # kod bir martalik


async def list_active_employees(session: AsyncSession, role: Role | None = None) -> list[Employee]:
    stmt = select(Employee).where(Employee.is_active.is_(True))
    if role:
        stmt = stmt.where(Employee.role == role)
    result = await session.execute(stmt.order_by(Employee.full_name))
    return list(result.scalars().all())


async def list_unlinked_amo_users(session: AsyncSession) -> list[AmoUser]:
    """amoCRM'da bor, lekin hali botga bog'lanmagan foydalanuvchilar."""
    linked_ids_result = await session.execute(
        select(Employee.amo_user_id).where(Employee.amo_user_id.is_not(None))
    )
    linked_ids = {row[0] for row in linked_ids_result.all()}
    result = await session.execute(select(AmoUser).where(AmoUser.is_active.is_(True)))
    return [u for u in result.scalars() if u.id not in linked_ids]
