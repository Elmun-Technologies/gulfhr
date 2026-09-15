"""Dispatcher va Bot obyektlarini yig'ish."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import admin, candidates, common, manager, sales, start
from app.bot.middlewares import DbSessionMiddleware
from app.config import Settings


def build_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.effective_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(DbSessionMiddleware())

    # Tartib muhim: aniq handlerlar oldin, umumiy fallback oxirida
    dp.include_router(start.router)
    dp.include_router(manager.router)
    dp.include_router(admin.router)
    dp.include_router(sales.router)
    dp.include_router(candidates.router)
    dp.include_router(common.router)
    return dp
