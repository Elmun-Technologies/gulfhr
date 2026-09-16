"""Baza ulanishi, sessiya fabrikasi va yengil migratsiya.

Ikkita muhim narsa:

1. **SQLite tezligi** — ulanish ochilganda `journal_mode=WAL` va
   `synchronous=NORMAL` o'rnatiladi. Bu yozuvlarni bir necha barobar tezlashtiradi
   va bir vaqtda bir nechta nomzod suhbatlashganda `database is locked` xatosining
   oldini oladi.
2. **Yengil migratsiya** — `Base.metadata.create_all` mavjud jadvalga yangi ustun
   QO'SHMAYDI (jadval bor bo'lsa butunlay o'tkazib yuboriladi). Shuning uchun
   `init_db()` yetishmayotgan ustun va indekslarni o'zi qo'shadi: aks holda
   deploy'dan keyin har bir INSERT xato beradi va oqim to'xtab qoladi.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import String, event, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import Column
from sqlalchemy.sql.elements import TextClause

from app.config import get_settings
from app.db.base import Base

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# SQLite uchun ulanish darajasidagi sozlamalar (tezlik + bloklashga bardoshlilik)
_SQLITE_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
)


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite fayli uchun katalogni yaratadi."""
    if not url.startswith("sqlite"):
        return
    path = url.split("///", 1)[-1]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def _register_sqlite_pragmas(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            for pragma in _SQLITE_PRAGMAS:
                cursor.execute(pragma)
        finally:
            cursor.close()


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _ensure_sqlite_dir(url)
        _engine = create_async_engine(url, echo=False, pool_pre_ping=True, future=True)
        if url.startswith("sqlite"):
            _register_sqlite_pragmas(_engine)
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


# ---------------------------------------------------------------------- #
# Yengil migratsiya (create_all yetishmayotgan ustunlarni qo'shmaydi)
# ---------------------------------------------------------------------- #


def _sql_literal(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int | float):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _add_column_ddl(table_name: str, column: Column, connection: Connection) -> str:
    col_type = column.type.compile(dialect=connection.dialect)
    default = column.default.arg if column.default is not None else None
    if callable(default):
        default = None
    if default is None and column.server_default is not None:
        arg = column.server_default.arg
        default = arg.text if isinstance(arg, TextClause) else arg
    if callable(default):
        default = None

    ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type}'
    if not column.nullable:
        # NOT NULL ustun qo'shilganda standart qiymat majburiy (SQLite talabi)
        ddl += " NOT NULL"
        if default is None:
            default = "" if isinstance(column.type, String) else 0
    if default is not None:
        ddl += f" DEFAULT {_sql_literal(default)}"
    return ddl


def _apply_missing_schema(connection: Connection) -> None:
    """Mavjud jadvallarga yetishmayotgan ustun va indekslarni qo'shadi."""
    inspector = inspect(connection)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            ddl = _add_column_ddl(table.name, column, connection)
            connection.execute(text(ddl))
            logger.warning("Migratsiya: %s", ddl)
        # Indekslar ham mavjud jadvalga create_all orqali qo'shilmaydi
        for index in table.indexes:
            index.create(connection, checkfirst=True)


async def init_db() -> None:
    """Jadvallarni yaratadi va yetishmayotgan ustunlarni qo'shadi."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_missing_schema)
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
