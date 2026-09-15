"""Pytest umumiy fixture'lari — har bir test uchun toza in-memory SQLite."""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("BOT_TOKEN", "test-token")
# Aiosqlite ":memory:" har bir ulanish uchun alohida baza yaratadi (pool bilan
# muammoli), shuning uchun testlar uchun vaqtinchalik fayl bazadan foydalanamiz.
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP_DB.name}")
os.environ.setdefault("WEB_ENABLED", "false")

import pytest_asyncio

from app.config import get_settings
from app.db import session as db_session
from app.db.base import Base


@pytest_asyncio.fixture(autouse=True)
async def _fresh_db():
    get_settings.cache_clear()
    db_session.reset_engine_cache()
    engine = db_session.get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db_session.dispose_db()
