"""Tezlik nazorati — nomzod sezadigan kechikish kamayishini test bilan ushlash.

Bu yerda ikki narsa qotiriladi:
1. **Byudjet**: bir ariza oqimida nechta Telegram API chaqiruvi bo'ladi.
   Ortiqcha chaqiruv qo'shilsa (masalan salomlashuv va savolni yana ikkita
   xabarga bo'lib yuborish) test yiqiladi — har bir chaqiruv ~100-300 ms.
2. **Tartib**: tugma bosilganda `callback.answer` ENG AVVAL yuboriladi,
   aks holda tugma 1 soniyagacha "yuklanmoqda" holatida turadi.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, SendMessage
from aiogram.types import Update

from app.bot.middlewares import TimingsMiddleware
from app.config import get_settings
from tests.test_dispatcher_flow import FlowDriver

GROUP_ID = -1001234567890


@pytest.fixture(autouse=True)
def _candidate_group(monkeypatch):
    """HR guruhi sozlangan holat — karta ham yuboriladi."""
    monkeypatch.setenv("CANDIDATES_CHAT_ID", str(GROUP_ID))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

# Til tanlash qadamini hisoblagan holda butun oqim byudjeti:
EXPECTED_SENDS = 11  # 10 ta nomzodga + 1 ta HR guruhiga
EXPECTED_EDITS = 5  # har bir tugmali qadamda klaviatura o'chiriladi
EXPECTED_CALLBACK_ANSWERS = 5  # 5 ta tugmali qadam


async def _full_flow() -> FlowDriver:
    flow = FlowDriver()
    await flow.send("/start")
    await flow.click("lang:uz")
    await flow.send("Vali Karimov")
    await flow.click("cand_gender:male")
    await flow.send("22")
    await flow.click("cand_yes")  # shahar
    await flow.click("cand_yes")  # rus tili
    await flow.send("+998901234567")
    await flow.send("2 yil sotuv menejeri")
    await flow.click("cand_skip_resume")
    return flow


@pytest.mark.asyncio
async def test_api_call_budget_for_whole_application() -> None:
    flow = await _full_flow()

    calls = flow.session.calls
    sends = [c for c in calls if isinstance(c, SendMessage)]
    edits = [c for c in calls if isinstance(c, EditMessageReplyMarkup)]
    answers = [c for c in calls if isinstance(c, AnswerCallbackQuery)]

    assert len(sends) == EXPECTED_SENDS, [c.text[:40] for c in sends]
    assert len(edits) == EXPECTED_EDITS
    assert len(answers) == EXPECTED_CALLBACK_ANSWERS
    # Nomzodga 10 ta xabar, HR guruhiga 1 ta karta
    assert len([s for s in sends if s.chat_id == 42]) == EXPECTED_SENDS - 1


@pytest.mark.asyncio
async def test_welcome_and_first_question_are_a_single_message() -> None:
    """Til tanlangach salomlashuv va birinchi savol BITTA xabarda ketadi."""
    flow = FlowDriver()
    await flow.send("/start")

    calls = await flow.click("lang:uz")

    assert len([c for c in calls if isinstance(c, SendMessage)]) == 1
    assert "Assalomu alaykum" in flow.last_text
    assert "Ism va familiyangizni" in flow.last_text


@pytest.mark.asyncio
async def test_deep_link_start_is_a_single_message() -> None:
    """`/start ru` — til tanlash oynasisiz, bitta xabar."""
    flow = FlowDriver()

    calls = await flow.send("/start ru")

    assert len([c for c in calls if isinstance(c, SendMessage)]) == 1
    assert "Здравствуйте" in flow.last_text


@pytest.mark.asyncio
async def test_button_spinner_is_answered_before_anything_else() -> None:
    flow = FlowDriver()
    await flow.send("/start")
    await flow.click("lang:uz")
    await flow.send("Vali Karimov")

    calls = await flow.click("cand_gender:male")

    assert isinstance(calls[0], AnswerCallbackQuery), "avval tugma javobi ketishi kerak"
    assert isinstance(calls[1], EditMessageReplyMarkup)
    assert isinstance(calls[2], SendMessage)


@pytest.mark.asyncio
async def test_timings_middleware_warns_about_slow_updates(caplog) -> None:
    """Sekin so'rovlar logda ko'rinadi (bot tezligini kuzatish uchun)."""
    middleware = TimingsMiddleware(slow_threshold=0.01)

    async def handler(event, data):  # noqa: ANN001
        await asyncio.sleep(0.03)
        return "ok"

    with caplog.at_level(logging.WARNING):
        assert await middleware(handler, Update(update_id=1), {}) == "ok"

    assert "Sekin so'rov" in caplog.text


@pytest.mark.asyncio
async def test_timings_middleware_is_silent_for_fast_updates(caplog) -> None:
    middleware = TimingsMiddleware(slow_threshold=5.0)

    async def handler(event, data):  # noqa: ANN001
        return "ok"

    with caplog.at_level(logging.WARNING):
        await middleware(handler, Update(update_id=1), {})

    assert "Sekin so'rov" not in caplog.text
