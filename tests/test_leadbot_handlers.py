"""leadbot.handlers — telefon normalizatsiyasi va suhbat uzilmasligi testlari.

Eski lead-bot noyob (README'ga qarang), lekin unda ham xuddi shu "suhbat davom
etmayapti" xatolari bor edi — shuning uchun tuzatishlar bu yerda ham tekshiriladi.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from leadbot import texts
from leadbot.handlers import (
    Application,
    _normalize_phone,
    _parse_gender,
    _parse_yes_no,
    on_city_text,
    on_full_name,
    on_gender_text,
    on_unexpected,
)


def test_normalizes_plain_uzbek_number() -> None:
    assert _normalize_phone("901234567") == "+998901234567"


def test_keeps_already_full_international_number() -> None:
    assert _normalize_phone("+998901234567") == "+998901234567"


def test_strips_spaces_and_dashes() -> None:
    assert _normalize_phone("+998 90 123-45-67") == "+998901234567"


def test_rejects_too_short_number() -> None:
    assert _normalize_phone("12345") is None


def test_rejects_non_numeric_garbage() -> None:
    assert _normalize_phone("abc") is None


class FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=7, username="vali")
        self.answered: list[tuple] = []

    async def answer(self, text, **kwargs) -> None:
        self.answered.append((text, kwargs))


def make_state() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))


# ---------------------------------------------------------------------- #
# Tugma o'rniga yozib yuborish — suhbat davom etadi
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_gender_typed_as_text_continues() -> None:
    state = make_state()
    await state.set_state(Application.gender)

    msg = FakeMessage("erkak")
    await on_gender_text(msg, state)

    assert (await state.get_state()) == "Application:age"
    assert msg.answered[0][0] == texts.ASK_AGE


@pytest.mark.asyncio
async def test_city_typed_as_text_continues() -> None:
    state = make_state()
    await state.set_state(Application.city)

    msg = FakeMessage("ha")
    await on_city_text(msg, state)

    assert (await state.get_state()) == "Application:phone"
    assert msg.answered[0][0] == texts.ASK_PHONE


@pytest.mark.asyncio
async def test_name_is_validated() -> None:
    state = make_state()
    await state.set_state(Application.full_name)

    msg = FakeMessage("Va")
    await on_full_name(msg, state)

    assert (await state.get_state()) == "Application:full_name"
    assert msg.answered[0][0] == texts.ASK_FULL_NAME_INVALID


# ---------------------------------------------------------------------- #
# Kutilmagan xabar — savol qayta so'raladi
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state_name", "expected"),
    [
        ("Application:full_name", texts.ASK_FULL_NAME),
        ("Application:gender", texts.ASK_GENDER),
        ("Application:age", texts.ASK_AGE),
        ("Application:city", texts.ASK_CITY),
        ("Application:phone", texts.ASK_PHONE),
        ("Application:experience", texts.ASK_EXPERIENCE),
    ],
)
async def test_every_state_reasks(state_name: str, expected: str) -> None:
    state = make_state()
    await state.set_state(state_name)

    msg = FakeMessage("🤷")
    await on_unexpected(msg, state)

    assert msg.answered[0][0] == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("✅ Ha", True), ("да", True), ("❌ Yo'q", False), ("нет", False), ("?", None)],
)
def test_parse_yes_no(raw: str, expected: bool | None) -> None:
    assert _parse_yes_no(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("👨 Erkak", "male"), ("женский", "female"), ("nima", None)],
)
def test_parse_gender(raw: str, expected: str | None) -> None:
    assert _parse_gender(raw) == expected
