"""app.db.session — mavjud bazaga yetishmayotgan ustunlarni qo'shish (migratsiya).

`Base.metadata.create_all` mavjud jadvalga yangi ustun qo'shmaydi. Agar
deploy'dan keyin yangi ustun (masalan `language`) qo'shilsa-yu, migratsiya
bo'lmasa, har bir INSERT xato beradi va nomzod oqimi oxirida to'xtab qoladi.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.candidates.qualify import CandidateAnswers, Verdict
from app.candidates.service import save_application
from app.db import session as db_session

# Eski baza ko'rinishi: `language` ustuni YO'Q
OLD_SCHEMA = """
CREATE TABLE applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name VARCHAR(255) NOT NULL,
    gender VARCHAR(16) NOT NULL,
    age INTEGER NOT NULL,
    lives_in_city BOOLEAN NOT NULL,
    knows_russian BOOLEAN NOT NULL,
    phone VARCHAR(32) NOT NULL,
    experience TEXT NOT NULL,
    resume_info TEXT NOT NULL,
    resume_file_kind VARCHAR(16),
    resume_file_id VARCHAR(255),
    telegram_id BIGINT,
    telegram_username VARCHAR(64),
    is_qualified BOOLEAN NOT NULL,
    reject_codes VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL
)
"""


async def _column_names(engine: AsyncEngine, table: str) -> set[str]:
    async with engine.connect() as conn:
        rows = await conn.execute(text(f"PRAGMA table_info({table})"))
        return {row[1] for row in rows.fetchall()}


async def _index_names(engine: AsyncEngine, table: str) -> set[str]:
    async with engine.connect() as conn:
        rows = await conn.execute(text(f"PRAGMA index_list({table})"))
        return {row[1] for row in rows.fetchall()}


@pytest.mark.asyncio
async def test_missing_column_is_added_to_existing_table() -> None:
    engine = db_session.get_engine()
    async with engine.begin() as conn:
        # conftest jadvalni yangi sxema bilan yaratadi — eski ko'rinishga qaytaramiz
        await conn.execute(text("DROP TABLE IF EXISTS applications"))
        await conn.execute(text(OLD_SCHEMA))

    assert "language" not in await _column_names(engine, "applications")

    await db_session.init_db()

    assert "language" in await _column_names(engine, "applications")


@pytest.mark.asyncio
async def test_insert_works_after_migration() -> None:
    engine = db_session.get_engine()
    async with engine.begin() as conn:
        # conftest jadvalni yangi sxema bilan yaratadi — eski ko'rinishga qaytaramiz
        await conn.execute(text("DROP TABLE IF EXISTS applications"))
        await conn.execute(text(OLD_SCHEMA))

    await db_session.init_db()

    answers = CandidateAnswers(
        full_name="Vali Karimov",
        gender="male",
        age=22,
        lives_in_city=True,
        phone="+998901234567",
        knows_russian=True,
        experience="2 yil",
        language="ru",
    )
    record = await save_application(
        answers, Verdict(is_qualified=True, reasons=[], reject_codes=())
    )
    assert record.language == "ru"


@pytest.mark.asyncio
async def test_missing_indexes_are_created() -> None:
    engine = db_session.get_engine()
    async with engine.begin() as conn:
        # conftest jadvalni yangi sxema bilan yaratadi — eski ko'rinishga qaytaramiz
        await conn.execute(text("DROP TABLE IF EXISTS applications"))
        await conn.execute(text(OLD_SCHEMA))

    await db_session.init_db()

    indexes = await _index_names(engine, "applications")
    assert "ix_application_created" in indexes
    assert "ix_application_qualified" in indexes


@pytest.mark.asyncio
async def test_init_db_is_idempotent() -> None:
    await db_session.init_db()
    await db_session.init_db()  # ikkinchi marta xato bermasligi kerak
    assert "language" in await _column_names(db_session.get_engine(), "applications")
