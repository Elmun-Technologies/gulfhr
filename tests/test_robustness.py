"""Bardoshlilik testlari — bot sekinlashishi yoki "jim qolish"iga yo'l qo'ymaslik.

Bu yerda uch narsa tekshiriladi:

1. **Navbat middleware** — bitta nomzodning update'lari ketma-ket bajariladi
   (FSM "o'qi→yoz" poygasi suhbatni buzmasligi uchun), turli nomzodlar esa
   bir-birini kutmaydi.
2. **Vaqt statistikasi** — sekin so'rovlar `/diag` uchun sanaladi.
3. **Xato handleri** — handler yiqilsa nomzodga xabar boradi (bot "o'ylanib"
   qolmaydi).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from aiogram import Bot, Dispatcher, Router
from aiogram.methods import AnswerCallbackQuery, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from app.bot.errors import USER_ERROR_MESSAGE, register_error_handler
from app.bot.middlewares import TimingsMiddleware, UserLockMiddleware
from app.bot.setup import build_bot, build_dispatcher
from app.bot.stats import RequestStats
from app.config import Settings
from tests.test_dispatcher_flow import CHAT, USER, MockedSession, _free_routers


def _user_data(user_id: int) -> dict:
    return {
        "event_from_user": User(id=user_id, is_bot=False, first_name=f"u{user_id}"),
        "event_chat": Chat(id=user_id, type="private"),
    }


@pytest.mark.asyncio
async def test_same_user_updates_are_processed_strictly_in_order() -> None:
    """Bir nomzod ikki marta tez bosib yuborsa — javoblar tartib bilan ishlanadi."""
    middleware = UserLockMiddleware()
    log: list[str] = []

    async def handler(event, data):  # noqa: ANN001
        log.append(f"start-{event}")
        await asyncio.sleep(0.02)
        log.append(f"end-{event}")
        return event

    data = _user_data(7)
    await asyncio.gather(
        middleware(handler, "birinchi", data),
        middleware(handler, "ikkinchi", data),
    )

    assert log == ["start-birinchi", "end-birinchi", "start-ikkinchi", "end-ikkinchi"]
    # Navbat yozuvlari tozalanadi (xotira cheksiz o'smasin)
    assert middleware._entries == {}


@pytest.mark.asyncio
async def test_different_users_are_not_blocked_by_each_other() -> None:
    """Ikki nomzod bir vaqtda yozsa, biri ikkinchisini kutmaydi."""
    middleware = UserLockMiddleware()
    log: list[str] = []

    async def handler(event, data):  # noqa: ANN001
        log.append(f"start-{event}")
        await asyncio.sleep(0.02)
        log.append(f"end-{event}")

    left = asyncio.create_task(middleware(handler, "a", _user_data(1)))
    right = asyncio.create_task(middleware(handler, "b", _user_data(2)))
    await asyncio.gather(left, right)

    assert log[:2] == ["start-a", "start-b"], "ikkala update ham parallel boshlanishi kerak"


@pytest.mark.asyncio
async def test_timings_middleware_collects_stats() -> None:
    """Sekin so'rovlar statistikaga yoziladi (/diag shuni ko'rsatadi)."""
    stats = RequestStats()
    middleware = TimingsMiddleware(slow_threshold=0.01, stats=stats)

    async def slow(event, data):  # noqa: ANN001
        await asyncio.sleep(0.02)
        return "ok"

    await middleware(slow, Update(update_id=1), {})

    snapshot = stats.snapshot()
    assert snapshot["updates"] == 1
    assert snapshot["slow"] == 1
    assert float(snapshot["slowest_seconds"]) >= 0.02


@pytest.mark.asyncio
async def test_error_handler_replies_to_candidate() -> None:
    """Handler yiqilsa nomzod jim qolmaydi — xabar oladi."""
    session = MockedSession()
    bot = Bot(token="123456:TEST", session=session)
    dp = Dispatcher()
    router = Router(name="boom")

    @router.message()
    async def boom(message: Message) -> None:
        raise RuntimeError("kutilmagan xato")

    dp.include_router(router)
    register_error_handler(dp)

    message = Message(
        message_id=1, date=datetime.now(UTC), chat=CHAT, from_user=USER, text="Salom"
    )
    handled = await dp.feed_update(bot, Update(update_id=1, message=message))

    assert handled is True, "xato handleri update'ni 'ishlangan' deb belgilashi kerak"
    texts = [call.text for call in session.calls if isinstance(call, SendMessage)]
    assert USER_ERROR_MESSAGE in texts


@pytest.mark.asyncio
async def test_error_handler_clears_button_spinner() -> None:
    """Tugma bosilganda xato bo'lsa ham 'soat' belgisi o'chiriladi."""
    session = MockedSession()
    bot = Bot(token="123456:TEST", session=session)
    dp = Dispatcher()
    router = Router(name="boom")

    @router.callback_query()
    async def boom(callback: CallbackQuery) -> None:
        raise RuntimeError("kutilmagan xato")

    dp.include_router(router)
    register_error_handler(dp)

    message = Message(message_id=5, date=datetime.now(UTC), chat=CHAT, from_user=USER, text="savol")
    callback = CallbackQuery(
        id="cb1", from_user=USER, chat_instance="ci", data="cand_yes", message=message
    )
    await dp.feed_update(bot, Update(update_id=1, callback_query=callback))

    assert any(isinstance(call, AnswerCallbackQuery) for call in session.calls)
    assert any(isinstance(call, SendMessage) for call in session.calls)


def test_dispatcher_ships_with_latency_and_order_middlewares() -> None:
    """Yig'ilgan dispatcher'da navbat va vaqt middleware'lari bo'lishi shart."""
    _free_routers()  # modul routerlari boshqa dispatcher'ga ulangan bo'lishi mumkin
    dp = build_dispatcher()

    assert any(isinstance(item, UserLockMiddleware) for item in dp.update.middleware)
    assert any(isinstance(item, TimingsMiddleware) for item in dp.update.outer_middleware)


def test_build_bot_uses_configured_timeout() -> None:
    """Bot sessiyasi `TG_REQUEST_TIMEOUT` bilan cheklangan bo'lishi kerak."""
    settings = Settings(BOT_TOKEN="123456:TEST", TG_REQUEST_TIMEOUT="9")
    bot = build_bot(settings)

    assert bot.session.timeout == 9.0


def test_settings_defaults_keep_pending_updates() -> None:
    """Default: bot qayta ishga tushganda nomzod javobi tashlanmaydi."""
    settings = Settings(BOT_TOKEN="123456:TEST")

    assert settings.drop_pending_updates is False
    assert settings.polling_timeout == 10
    assert settings.tg_request_timeout == 15.0
    assert settings.slow_request_threshold == 0.5


def test_settings_parse_admin_ids_and_flags() -> None:
    settings = Settings(BOT_TOKEN="123456:TEST", ADMIN_USER_IDS="111, 222  333", DROP_PENDING_UPDATES="true")

    assert settings.admin_user_id_set == frozenset({111, 222, 333})
    assert settings.drop_pending_updates is True
