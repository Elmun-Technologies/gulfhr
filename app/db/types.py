"""Bazalar orasida (SQLite / PostgreSQL) izchil ishlaydigan sana-vaqt turi.

SQLite (aiosqlite) `DateTime(timezone=True)` ustunidan o'qiganda tzinfo'ni
saqlamaydi — natijada "naive" datetime qaytadi va uni "aware" (UTC) qiymat
bilan solishtirishda `TypeError` chiqadi. Bu klass har doim UTC'da, naive
holda saqlaydi va o'qishda UTC tzinfo qo'shib qaytaradi — shu bilan butun
ilova doim aware-UTC datetime bilan ishlayotganiga kafolat beradi.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """UTC'da saqlanadigan, doim timezone-aware qiymat qaytaradigan DateTime."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
