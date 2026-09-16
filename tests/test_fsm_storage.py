"""app.db.fsm_storage — suhbat holatini diskda saqlash testlari."""

from __future__ import annotations

import time

import pytest
from aiogram.fsm.storage.base import StorageKey

from app.db.fsm_storage import SqliteStorage

KEY = StorageKey(bot_id=123456, chat_id=42, user_id=42)


def _db(tmp_path) -> SqliteStorage:
    return SqliteStorage(str(tmp_path / "fsm.db"))


@pytest.mark.asyncio
async def test_state_and_data_round_trip(tmp_path) -> None:
    storage = _db(tmp_path)
    await storage.setup()

    await storage.set_state(KEY, "ApplicationStates:gender")
    await storage.set_data(KEY, {"lang": "ru", "full_name": "Vali"})

    assert await storage.get_state(KEY) == "ApplicationStates:gender"
    assert await storage.get_data(KEY) == {"lang": "ru", "full_name": "Vali"}
    await storage.close()


@pytest.mark.asyncio
async def test_update_data_merges_instead_of_replacing(tmp_path) -> None:
    storage = _db(tmp_path)
    await storage.setup()

    await storage.set_data(KEY, {"lang": "uz"})
    merged = await storage.update_data(KEY, {"age": 22})

    assert merged == {"lang": "uz", "age": 22}
    assert await storage.get_data(KEY) == {"lang": "uz", "age": 22}
    await storage.close()


@pytest.mark.asyncio
async def test_state_survives_restart(tmp_path) -> None:
    """Bot qayta ishga tushsa ham suhbat to'xtagan joyidan davom etadi."""
    first = _db(tmp_path)
    await first.setup()
    await first.set_state(KEY, "ApplicationStates:city")
    await first.set_data(KEY, {"lang": "ru", "full_name": "Vali", "age": 22})
    await first.close()

    second = _db(tmp_path)  # yangi jarayon, shu fayl
    await second.setup()
    assert await second.get_state(KEY) == "ApplicationStates:city"
    assert (await second.get_data(KEY))["age"] == 22
    await second.close()


@pytest.mark.asyncio
async def test_set_state_none_clears_state_but_keeps_data(tmp_path) -> None:
    storage = _db(tmp_path)
    await storage.setup()

    await storage.set_state(KEY, "ApplicationStates:age")
    await storage.set_data(KEY, {"lang": "uz"})
    await storage.set_state(KEY, None)

    assert await storage.get_state(KEY) is None
    assert await storage.get_data(KEY) == {"lang": "uz"}
    await storage.close()


@pytest.mark.asyncio
async def test_unknown_key_returns_empty(tmp_path) -> None:
    storage = _db(tmp_path)
    await storage.setup()

    other = StorageKey(bot_id=1, chat_id=9, user_id=9)
    assert await storage.get_state(other) is None
    assert await storage.get_data(other) == {}
    await storage.close()


@pytest.mark.asyncio
async def test_purge_old_removes_stale_conversations(tmp_path) -> None:
    storage = _db(tmp_path)
    await storage.setup()

    await storage.set_state(KEY, "ApplicationStates:age")
    # Yozuvni sun'iy ravishda 30 kun oldinga suramiz
    db = await storage._connect()
    await db.execute(
        "UPDATE fsm_states SET updated_at = ? WHERE user_id = ?",
        (time.time() - 30 * 86400, KEY.user_id),
    )

    assert await storage.purge_old() == 1
    assert await storage.get_state(KEY) is None
    await storage.close()


@pytest.mark.asyncio
async def test_corrupted_data_is_ignored(tmp_path) -> None:
    storage = _db(tmp_path)
    await storage.setup()

    db = await storage._connect()
    await db.execute(
        "INSERT INTO fsm_states (bot_id, chat_id, user_id, state, data, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (KEY.bot_id, KEY.chat_id, KEY.user_id, "ApplicationStates:age", "{buzilgan", time.time()),
    )

    assert await storage.get_data(KEY) == {}
    assert await storage.get_state(KEY) == "ApplicationStates:age"
    await storage.close()
