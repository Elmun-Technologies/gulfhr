"""`/diag` buyrug'i testlari — bot o'z tezligini o'lchab bera olishi kerak."""

from __future__ import annotations

import pytest

from app.candidates.texts import STATS_GROUP_ONLY, UZBEK
from app.config import get_settings
from tests.test_dispatcher_flow import CHAT, FlowDriver


@pytest.mark.asyncio
async def test_diag_is_not_available_to_candidates_in_private_chat() -> None:
    """Nomzod shaxsiy chatda texnik ma'lumot ko'rmaydi."""
    get_settings.cache_clear()
    flow = FlowDriver()

    await flow.send("/diag")

    assert STATS_GROUP_ONLY in flow.last_text
    assert "DIAGNOSTIKASI" not in flow.last_text
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_diag_reports_telegram_latency_in_hr_group(monkeypatch) -> None:
    """HR guruhida /diag Telegram bilan aloqa tezligini ko'rsatadi."""
    monkeypatch.setenv("CANDIDATES_CHAT_ID", str(CHAT.id))
    get_settings.cache_clear()
    try:
        flow = FlowDriver()

        await flow.send("/diag")

        text = flow.last_text
        assert "DIAGNOSTIKASI" in text
        assert "API javob vaqti" in text
        assert "BOT DIAGNOSTIKASI" in text
        assert "@gulf_hr_bot" in text  # MockedSession shu botni qaytaradi
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_diag_does_not_break_candidate_flow(monkeypatch) -> None:
    """Suhbat o'rtasida /diag yuborilsa ham oqim davom etadi (javob o'rniga sanalmaydi)."""
    monkeypatch.setenv("CANDIDATES_CHAT_ID", str(CHAT.id))
    get_settings.cache_clear()
    try:
        flow = FlowDriver()
        await flow.send("/start")
        await flow.click("lang:uz")

        await flow.send("/diag")
        assert "DIAGNOSTIKASI" in flow.last_text

        # Suhbat davom etadi: ism javobini yuboramiz → keyingi savol (jins)
        await flow.send("Vali Karimov")
        assert flow.last_text == UZBEK.ask_gender
    finally:
        get_settings.cache_clear()
