"""Dispatcher middleware'lari — tezlikni kuzatish uchun.

`TimingsMiddleware` har bir update qancha vaqtda ishlanganini o'lchaydi.
Sekin (standart: 0.5 s dan ortiq) so'rovlar WARNING darajasida logga yoziladi —
bot sekinlashsa, muammo aynan qaysi bosqichda ekanini logdan ko'rish mumkin.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

logger = logging.getLogger(__name__)

# Shu chegaradan sekin ishlagan update log'da WARNING bo'lib chiqadi
DEFAULT_SLOW_THRESHOLD = 0.5


class TimingsMiddleware(BaseMiddleware):
    """Update'larning ishlash vaqtini o'lchaydi."""

    def __init__(self, slow_threshold: float = DEFAULT_SLOW_THRESHOLD) -> None:
        self.slow_threshold = slow_threshold

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
            if elapsed >= self.slow_threshold:
                logger.warning("⏱ Sekin so'rov: %s — %.2fs", label, elapsed)
            else:
                logger.debug("⏱ %s — %.3fs", label, elapsed)


def _label(event: TelegramObject) -> str:
    """Log uchun qisqa tavsif: `message #123 (text)` kabi."""
    if isinstance(event, Update):
        inner = event.message or event.callback_query or event.edited_message
        if inner is not None:
            return f"update → {type(inner).__name__}"
        return "update"
    return type(event).__name__
