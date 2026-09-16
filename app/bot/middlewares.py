"""Dispatcher middleware'lari.

Uchta vazifa:

1. **`TimingsMiddleware`** — har bir update qancha vaqtda ishlanganini o'lchaydi
   (yig'ma ko'rsatkichlar `/diag` da ko'rinadi). Sekin so'rovlar logga
   WARNING bo'lib tushadi: bot sekinlashsa, aybdor update'ni darhol ko'rish
   mumkin.
2. **`UserLockMiddleware`** — bitta foydalanuvchining update'lari **ketma-ket**
   bajariladi. aiogram update'larni parallel (task) sifatida ishlaydi, FSM esa
   "o'qi → yoz" ko'rinishida: nomzod ikki marta tez bosib yuborsa ikkala handler
   ham eski holatni o'qib, biri ikkinchisining yozuvini bosib ketishi mumkin —
   natijada suhbat "keyingi bosqichga o'tmaydi". Turli nomzodlar esa bir-birini
   kutmaydi (parallel qoladi).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.bot.stats import STATS, RequestStats

logger = logging.getLogger(__name__)

# Shu chegaradan sekin ishlagan update log'da WARNING bo'lib chiqadi
DEFAULT_SLOW_THRESHOLD = 0.5


class TimingsMiddleware(BaseMiddleware):
    """Update'larning ishlash vaqtini o'lchaydi va yig'ma statistikani yozadi."""

    def __init__(
        self, slow_threshold: float = DEFAULT_SLOW_THRESHOLD, stats: RequestStats = STATS
    ) -> None:
        self.slow_threshold = slow_threshold
        self.stats = stats

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        started = time.perf_counter()
        try:
            return await handler(event, data)
        finally:
            elapsed = time.perf_counter() - started
            label = _label(event)
            if self.stats.observe(label, elapsed, slow_threshold=self.slow_threshold):
                logger.warning("⏱ Sekin so'rov: %s — %.2fs", label, elapsed)
            else:
                logger.debug("⏱ %s — %.3fs", label, elapsed)


@dataclass
class _LockEntry:
    """Bitta foydalanuvchi uchun navbat."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    waiters: int = 0


class UserLockMiddleware(BaseMiddleware):
    """Bir foydalanuvchining update'larini tartib bilan (ketma-ket) bajaradi."""

    def __init__(self, *, wait_warning_after: float = 2.0, max_wait: float = 20.0) -> None:
        self._entries: dict[tuple[int, int], _LockEntry] = {}
        self._wait_warning_after = wait_warning_after
        self._max_wait = max_wait

    def _reserve(self, key: tuple[int, int]) -> _LockEntry:
        """Navbatga yoziladi. Bu sinxron — `await` yo'q, shuning uchun poyga yo'q."""
        entry = self._entries.get(key)
        if entry is None:
            entry = _LockEntry()
            self._entries[key] = entry
        entry.waiters += 1
        return entry

    def _release(self, key: tuple[int, int], entry: _LockEntry) -> None:
        entry.waiters -= 1
        if entry.waiters <= 0 and not entry.lock.locked():
            self._entries.pop(key, None)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        if user is None:  # kanal posti va h.k. — navbat kerak emas
            return await handler(event, data)

        key = (getattr(chat, "id", 0) or 0, user.id)
        entry = self._reserve(key)
        acquired = False
        try:
            started = time.perf_counter()
            try:
                await asyncio.wait_for(entry.lock.acquire(), timeout=self._max_wait)
                acquired = True
            except TimeoutError:
                # Kutish haddan tashqari cho'zildi (oldingi handler osilib qolgan):
                # javobni umuman bermaslikdan ko'ra tartib buzilgani ma'qul.
                logger.warning(
                    "⏳ user=%s navbatida %.0fs kutildi — update tartibdan tashqari ishlanadi",
                    user.id,
                    self._max_wait,
                )
            else:
                waited = time.perf_counter() - started
                if waited >= self._wait_warning_after:
                    logger.warning(
                        "⏳ user=%s oldingi javob tugashini kutdi: %.2fs (navbat)",
                        user.id,
                        waited,
                    )
            return await handler(event, data)
        finally:
            if acquired:
                entry.lock.release()
            self._release(key, entry)


def _label(event: TelegramObject) -> str:
    """Log uchun qisqa tavsif: `callback_query cand_gender:male` kabi."""
    if not isinstance(event, Update):
        return type(event).__name__
    inner = event.message or event.callback_query or event.edited_message
    if inner is None:
        return "update"
    if hasattr(inner, "data") and getattr(inner, "data", None):
        return f"callback_query {inner.data}"
    text = getattr(inner, "text", None) or ""
    if text:
        short = text.strip().splitlines()[0][:30]
        return f"{type(inner).__name__} «{short}»"
    return type(inner).__name__


__all__ = ["STATS", "DEFAULT_SLOW_THRESHOLD", "TimingsMiddleware", "UserLockMiddleware"]
