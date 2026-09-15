"""Lead-bot ishga tushirish nuqtasi: `python -m leadbot.main`."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from leadbot.config import get_leadbot_settings
from leadbot.handlers import router
from leadbot.storage import init_db


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def run() -> None:
    settings = get_leadbot_settings()
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    if not settings.leadbot_token:
        raise SystemExit("LEADBOT_TOKEN .env faylida ko'rsatilmagan.")
    if not settings.lead_group_chat_id:
        logger.warning(
            "LEAD_GROUP_CHAT_ID ko'rsatilmagan — natijalar hech qayerga yuborilmaydi."
        )

    init_db(settings.lead_db_path)
    logger.info("Analitika bazasi tayyor: %s", settings.lead_db_path)

    bot = Bot(
        token=settings.leadbot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    logger.info("Lead-bot ishga tushdi (guruh: %s)", settings.lead_group_chat_id)
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
