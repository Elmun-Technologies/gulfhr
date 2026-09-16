"""Bot va Dispatcher obyektlarini yig'ish."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import candidates, common, diagnostics, start
from app.bot.middlewares import DEFAULT_SLOW_THRESHOLD, TimingsMiddleware, UserLockMiddleware
from app.bot.session import build_session
from app.config import Settings

# Dispatcher'ga ulanadigan routerlar (tartib muhim!). Ro'yxat shu yerda —
# testlar ham routerlarni qayta ulashda aynan shu to'plamdan foydalanadi.
ROUTERS = (
    start.router,       # /start, /help
    diagnostics.router, # /diag — suhbat o'rtasida ham ishlashi uchun nomzodlardan OLDIN
    candidates.router,  # ariza oqimi
    common.router,      # fallback (eng oxirida)
)


def build_bot(settings: Settings) -> Bot:
    """Botni sessiya bilan birga yaratadi.

    Sessiya `TG_REQUEST_TIMEOUT` bilan cheklangan: osilib qolgan so'rov botni
    daqiqalab ("o'ylanib") ushlab turmasligi uchun (`app/bot/session.py`).
    """
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=build_session(
            timeout=settings.tg_request_timeout,
            limit=settings.tg_connections,
        ),
    )


def build_dispatcher(
    storage: BaseStorage | None = None, *, slow_threshold: float | None = None
) -> Dispatcher:
    """Dispatcher yig'adi.

    `storage` berilmasa `MemoryStorage` ishlatiladi (testlar uchun qulay).
    Ishlash muhitida `app.db.fsm_storage.SqliteStorage` beriladi — bot qayta
    ishga tushganda nomzod yozayotgan ariza yo'qolmasligi uchun.
    """
    dp = Dispatcher(storage=storage or MemoryStorage())

    # 1) Tezlikni kuzatish: sekin handlerlar logga WARNING bo'lib tushadi
    #    va /diag buyrug'ida raqamlar ko'rinadi.
    dp.update.outer_middleware(TimingsMiddleware(slow_threshold=slow_threshold or DEFAULT_SLOW_THRESHOLD))
    # 2) Bir foydalanuvchi update'lari ketma-ket (FSM "o'qi→yoz" poygasini oldini oladi)
    dp.update.middleware(UserLockMiddleware())

    # Tartib muhim: aniq handlerlar oldin, umumiy fallback oxirida (ROUTERS).
    for router in ROUTERS:
        dp.include_router(router)
    return dp
