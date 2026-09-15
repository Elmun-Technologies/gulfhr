"""Gulf HR bot — kirish nuqtasi.

Ishga tushirish:
    python -m app.main
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher

from app.bot.bot_instance import set_bot
from app.bot.setup import build_bot, build_dispatcher
from app.config import get_settings
from app.db.session import init_db
from app.logging_conf import setup_logging
from app.scheduler.jobs import job_sync_and_monitor
from app.scheduler.scheduler import build_scheduler
from app.web.server import build_app

logger = logging.getLogger(__name__)


class WebhookDebouncer:
    """amoCRM webhooklaridan kelgan ko'p signalni bitta sinxronizatsiyaga birlashtiradi."""

    def __init__(self, bot: Bot, delay_seconds: float = 5.0) -> None:
        self._bot = bot
        self._delay = delay_seconds
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def kick(self) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                return
            self._task = asyncio.create_task(self._run_after_delay())

    async def _run_after_delay(self) -> None:
        await asyncio.sleep(self._delay)
        try:
            await job_sync_and_monitor(self._bot)
        except Exception:  # noqa: BLE001
            logger.exception("Webhook orqali chaqirilgan sinxronizatsiya xato berdi")


async def run_web_server(bot: Bot, settings, debouncer: WebhookDebouncer) -> None:
    app = build_app(bot, settings, debouncer.kick)
    config = uvicorn.Config(
        app, host=settings.web_host, port=settings.web_port, log_level="warning"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Gulf HR bot ishga tushmoqda...")

    if not settings.effective_bot_token:
        raise SystemExit(
            "BOT_TOKEN sozlanmagan. .env faylini to'ldiring (.env.example'ga qarang)."
        )
    if not settings.bot_token and settings.leadbot_token:
        logger.warning(
            "BOT_TOKEN bo'sh — LEADBOT_TOKEN ishlatilmoqda (eski Fly sozlamalari iloji)."
        )

    await init_db()

    bot = build_bot(settings)
    set_bot(bot)
    dp: Dispatcher = build_dispatcher()

    # Webhook o'rnatilgan bo'lsa, uni tozalaymiz — aks holda long polling
    # Telegram'dan 409 conflict bilan ishlamay qolishi mumkin.
    await bot.delete_webhook(drop_pending_updates=True)

    scheduler = build_scheduler(bot, settings)
    scheduler.start()

    tasks = [asyncio.create_task(dp.start_polling(bot))]

    if settings.web_enabled:
        debouncer = WebhookDebouncer(bot)
        tasks.append(asyncio.create_task(run_web_server(bot, settings, debouncer)))

    try:
        await asyncio.gather(*tasks)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
