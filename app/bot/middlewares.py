"""Aiogram middleware: har bir yangilanish uchun DB sessiya va joriy xodimni ulash."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.db.session import session_scope
from app.services.employees import get_employee_by_telegram_id


class DbSessionMiddleware(BaseMiddleware):
    """Har bir hodisaga `session` va `employee` obyektlarini qo'shadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with session_scope() as session:
            data["session"] = session

            telegram_id = _extract_user_id(event)
            data["employee"] = (
                await get_employee_by_telegram_id(session, telegram_id) if telegram_id else None
            )
            return await handler(event, data)


def _extract_user_id(event: TelegramObject) -> int | None:
    if isinstance(event, Update):
        if event.message and event.message.from_user:
            return event.message.from_user.id
        if event.callback_query and event.callback_query.from_user:
            return event.callback_query.from_user.id
        return None
    user = getattr(event, "from_user", None)
    return user.id if user else None
