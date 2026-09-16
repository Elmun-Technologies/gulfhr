"""SQLite'da saqlanadigan FSM storage.

Nima uchun kerak: standart `MemoryStorage` holatni faqat jarayon xotirasida
saqlaydi. Bot qayta ishga tushsa (deploy, restart, xato) nomzod yozayotgan ariza
**yo'qoladi** va suhbat o'rtada uzilib qoladi — nomzod "davom etmayapti" deb
o'ylaydi. Bu storage holatni diskka yozadi, shuning uchun bot qayta ishga tushgach
suhbat aynan to'xtagan joyidan davom etadi.

Bitta SQLite fayl (`FSM_DB_PATH`, default `./data/fsm.db`) — alohida Redis
kerak emas. Yozuvlar autocommit rejimida, har biri ~1 ms dan kam.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import aiosqlite
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS fsm_states (
    bot_id     INTEGER NOT NULL,
    chat_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    state      TEXT,
    data       TEXT NOT NULL DEFAULT '{}',
    updated_at REAL NOT NULL,
    PRIMARY KEY (bot_id, chat_id, user_id)
)
"""

_SET_STATE = """
INSERT INTO fsm_states (bot_id, chat_id, user_id, state, data, updated_at)
VALUES (?, ?, ?, ?, '{}', ?)
ON CONFLICT (bot_id, chat_id, user_id)
DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at
"""

_SET_DATA = """
INSERT INTO fsm_states (bot_id, chat_id, user_id, state, data, updated_at)
VALUES (?, ?, ?, NULL, ?, ?)
ON CONFLICT (bot_id, chat_id, user_id)
DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
"""

_SELECT = "SELECT state, data FROM fsm_states WHERE bot_id = ? AND chat_id = ? AND user_id = ?"

# Yarim oydan eski (tashlab ketilgan) suhbatlar avtomatik tozalanadi
DEFAULT_MAX_AGE_DAYS = 14


def _as_state_str(state: StateType) -> str | None:
    """Holat obyektini satrga aylantiradi.

    `FSMContext.set_state` storage'ga `State` obyektining o'zini beradi
    (`MemoryStorage` uni o'zi satrga aylantiradi) — shuning uchun bu yerda ham
    normallashtiramiz, aks holda sqlite "type 'State' is not supported" deydi.
    """
    if state is None or isinstance(state, str):
        return state
    if isinstance(state, State):
        return state.state
    return str(state)


class SqliteStorage(BaseStorage):
    """`aiogram.fsm.storage.base.BaseStorage` ning SQLite implementatsiyasi."""

    def __init__(self, path: str, *, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> None:
        self._path = path
        self._max_age_days = max_age_days
        self._db: aiosqlite.Connection | None = None

    # -- ulanish --------------------------------------------------------- #

    async def setup(self) -> None:
        """Baza faylini/jadvalni tayyorlaydi (bot ishga tushishida chaqiriladi)."""
        await self._connect()
        purged = await self.purge_old()
        if purged:
            logger.info("FSM: %s ta eski (tashlab ketilgan) suhbat tozalandi", purged)

    async def _connect(self) -> aiosqlite.Connection:
        if self._db is None:
            directory = os.path.dirname(os.path.abspath(self._path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            # isolation_level=None → autocommit: har bir yozuv darhol diskka tushadi
            # va parallel nomzodlar suhbatlari bir-birini bloklamaydi.
            db = await aiosqlite.connect(self._path, isolation_level=None)
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute(_CREATE_TABLE)
            self._db = db
        return self._db

    # -- BaseStorage interfeysi ------------------------------------------- #

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        db = await self._connect()
        await db.execute(
            _SET_STATE, (key.bot_id, key.chat_id, key.user_id, _as_state_str(state), time.time())
        )

    async def get_state(self, key: StorageKey) -> str | None:
        row = await self._fetch(key)
        return row[0] if row else None

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        db = await self._connect()
        await db.execute(
            _SET_DATA,
            (key.bot_id, key.chat_id, key.user_id, json.dumps(data, ensure_ascii=False), time.time()),
        )

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        row = await self._fetch(key)
        if not row:
            return {}
        try:
            data = json.loads(row[1])
        except (TypeError, ValueError):  # pragma: no cover - buzilgan yozuv
            logger.warning("FSM ma'lumoti o'qilmadi (chat=%s user=%s)", key.chat_id, key.user_id)
            return {}
        return data if isinstance(data, dict) else {}

    async def update_data(self, key: StorageKey, data: dict[str, Any]) -> dict[str, Any]:
        """Asosiy sinf get+set qiladi; bu yerda bitta tranzaksiyada bajariladi."""
        current = await self.get_data(key)
        current.update(data)
        await self.set_data(key, current)
        return current

    async def _fetch(self, key: StorageKey) -> tuple[str | None, str] | None:
        db = await self._connect()
        async with db.execute(
            _SELECT, (key.bot_id, key.chat_id, key.user_id)
        ) as cursor:
            return await cursor.fetchone()

    # -- xizmat funksiyalari ---------------------------------------------- #

    async def purge_old(self, *, max_age_days: int | None = None) -> int:
        """Eski suhbat yozuvlarini o'chiradi (baza cheksiz o'smasligi uchun)."""
        days = max_age_days if max_age_days is not None else self._max_age_days
        if days <= 0:
            return 0
        db = await self._connect()
        cutoff = time.time() - days * 86400
        cursor = await db.execute("DELETE FROM fsm_states WHERE updated_at < ?", (cutoff,))
        try:
            return cursor.rowcount or 0
        finally:
            await cursor.close()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None


async def build_storage(path: str) -> SqliteStorage:
    """Storage yaratib, bazani tayyorlab beradi."""
    storage = SqliteStorage(path)
    await storage.setup()
    return storage


__all__ = ["SqliteStorage", "build_storage"]
