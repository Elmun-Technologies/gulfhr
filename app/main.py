"""Gulf HR bot — kirish nuqtasi.

Ishga tushirish:
    python -m app.main
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.bot.setup import build_bot, build_dispatcher
from app.config import get_settings
from app.db.fsm_storage import build_storage
from app.db.session import init_db
from app.logging_conf import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Gulf HR bot ishga tushmoqda...")

    if not settings.bot_token:
        raise SystemExit(
            "BOT_TOKEN sozlanmagan. .env faylini to'ldiring (.env.example'ga qarang)."
        )

    await init_db()

    # Suhbat holati diskka yoziladi — bot qayta ishga tushsa (deploy/restart)
    # nomzod yozayotgan ariza yo'qolmaydi va suhbat o'rtada uzilmaydi.
    storage = await build_storage(settings.fsm_db_path)
    logger.info(
        "FSM bazasi tayyor: %s (til tanlash: %s)",
        settings.fsm_db_path,
        "yoqilgan" if settings.language_choice else f"o'chirilgan ({settings.default_language})",
    )

    bot: Bot = build_bot(settings)
    dp: Dispatcher = build_dispatcher(storage)

    # Webhook o'rnatilgan bo'lsa, uni tozalaymiz — aks holda long polling
    # Telegram'dan 409 conflict bilan ishlamay qolishi mumkin.
    # drop_pending_updates — bot o'chib turganda yig'ilib qolgan eski xabarlarni
    # qayta ishlamaydi (ishga tushish tezligi va "eskirgan" savol-javoblar oldini oladi).
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await storage.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
