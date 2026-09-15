"""Bot va Dispatcher obyektlarini yig'ish."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import candidates, common, start
from app.config import Settings


def build_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Tartib muhim: aniq handlerlar oldin, umumiy fallback oxirida
    dp.include_router(start.router)
    dp.include_router(candidates.router)
    dp.include_router(common.router)
    return dp
