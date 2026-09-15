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

    bot: Bot = build_bot(settings)
    dp: Dispatcher = build_dispatcher()

    # Webhook o'rnatilgan bo'lsa, uni tozalaymiz — aks holda long polling
    # Telegram'dan 409 conflict bilan ishlamay qolishi mumkin.
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
