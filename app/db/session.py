"""Baza ulanishi va sessiya fabrikasi."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.db.base import Base

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite fayli uchun katalogni yaratadi."""
    if not url.startswith("sqlite"):
        return
    path = url.split("///", 1)[-1]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _ensure_sqlite_dir(url)
        _engine = create_async_engine(url, echo=False, pool_pre_ping=True, future=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Tranzaksiya bilan sessiya konteksti."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Jadvallarni yaratadi (birinchi ishga tushirish)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Baza tayyor: %s", get_settings().database_url.split("://")[0])


async def dispose_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def reset_engine_cache() -> None:
    """Testlar uchun: engine keshini tozalash."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
