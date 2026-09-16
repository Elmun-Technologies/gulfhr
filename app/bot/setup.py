"""Bot va Dispatcher obyektlarini yig'ish."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import candidates, common, start
from app.bot.middlewares import TimingsMiddleware
from app.config import Settings


def build_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher(storage: BaseStorage | None = None) -> Dispatcher:
    """Dispatcher yig'adi.

    `storage` berilmasa `MemoryStorage` ishlatiladi (testlar uchun qulay).
    Ishlash muhitida `app.db.fsm_storage.SqliteStorage` beriladi — bot qayta
    ishga tushganda nomzod yozayotgan ariza yo'qolmasligi uchun.
    """
    dp = Dispatcher(storage=storage or MemoryStorage())

    # Tezlikni kuzatish: sekin handlerlar logga WARNING bo'lib tushadi
    dp.update.outer_middleware(TimingsMiddleware())

    # Tartib muhim: aniq handlerlar oldin, umumiy fallback oxirida
    dp.include_router(start.router)
    dp.include_router(candidates.router)
    dp.include_router(common.router)
    return dp
