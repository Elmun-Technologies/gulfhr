"""Kalit-qiymat saqlagichi (sinxronizatsiya kursorlari, bayroqlar)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KeyValue


async def get_value(session: AsyncSession, key: str) -> str | None:
    record = await session.get(KeyValue, key)
    return record.value if record else None


async def set_value(session: AsyncSession, key: str, value: str) -> None:
    record = await session.get(KeyValue, key)
    if record is None:
        record = KeyValue(key=key)
        session.add(record)
    record.value = value
    record.updated_at = datetime.now(UTC)
