"""Gulf HR bot — kirish nuqtasi.

Ishga tushirish:
    python -m app.main
"""

from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.utils.backoff import BackoffConfig

from app.bot.errors import register_error_handler
from app.bot.setup import build_bot, build_dispatcher
from app.config import get_settings
from app.db.fsm_storage import build_storage
from app.db.session import init_db
from app.health import start_health_server
from app.logging_conf import install_polling_conflict_watcher, setup_logging

logger = logging.getLogger(__name__)

# Tarmoq uzilganda aiogram standart bo'yicha 1-5 sekund kutadi. Nomzod uchun bu
# "bot o'ylanib qoldi" degani, shuning uchun kutish qisqartirilgan.
FAST_BACKOFF = BackoffConfig(min_delay=0.2, max_delay=3.0, factor=1.5, jitter=0.1)

# Shu chegaradan sekin javob bersa ogohlantirish yoziladi (ms)
SLOW_API_WARNING_MS = 800


async def probe_telegram(bot: Bot) -> float:
    """Ishga tushishda Telegram bilan aloqa tezligini o'lchaydi (ms).

    "Bot sekin" degan shikoyatda birinchi savol — tarmoq qanchalik tez? Bu qator
    `fly logs` da darhol ko'rinadi: agar RTT yuzlab millisekund bo'lsa, aybdor
    kod emas, server hududi/tarmoq bo'ladi (har bir bosqichda 1-3 ta so'rov
    ketadi, ya'ni kechikish shuncha marta ko'payadi).
    """
    started = time.perf_counter()
    me = await bot.get_me()
    rtt_ms = (time.perf_counter() - started) * 1000
    logger.info("Telegram aloqasi: %.0f ms (@%s, id=%s)", rtt_ms, me.username, me.id)
    if rtt_ms > SLOW_API_WARNING_MS:
        logger.warning(
            "⚠️ Telegram API juda sekin javob bermoqda (%.0f ms). Nomzod har bir "
            "bosqichda shu vaqtni kutadi — server hududini (fly.toml: primary_region) "
            "yoki tarmoqni tekshiring.",
            rtt_ms,
        )
    return rtt_ms


async def main() -> None:
    started_at = time.perf_counter()
    settings = get_settings()
    setup_logging(settings.log_level)
    install_polling_conflict_watcher()
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
    dp: Dispatcher = build_dispatcher(storage, slow_threshold=settings.slow_request_threshold)
    # Xato bo'lsa bot jim qolmasin: nomzodga xabar yuboriladi va logga yoziladi
    register_error_handler(dp)

    # Telegram bilan aloqa long polling orqali bo'ladi, lekin Fly ilovada
    # avvaldan HTTP service qolgan bo'lishi mumkin. Liveness server shu
    # service'ni sog'lom deb ko'rsatadi va auto-stop botni to'xtatib qo'yishining
    # oldini oladi; barcha trafik faqat ichki /health endpoint'iga kerak.
    health_server = await start_health_server()
    logger.info("Health server tinglamoqda: 0.0.0.0:8080")

    try:
        try:
            await probe_telegram(bot)
        except Exception as exc:  # noqa: BLE001 - tekshiruv botni to'xtatmasin
            logger.warning("Telegram aloqasini o'lchab bo'lmadi: %s", exc)

        # Webhook o'rnatilgan bo'lsa, long polling 409 Conflict bilan ishlamaydi —
        # shuning uchun uni o'chiramiz. `drop_pending_updates` esa FAQAT sozlamada
        # yoqilgan bo'lsa: bot o'chib turganda navbatda turgan nomzod javobi
        # tashlab yuborilsa, suhbat "keyingi bosqichga o'tmaydi".
        await bot.delete_webhook(drop_pending_updates=settings.drop_pending_updates)
        if settings.drop_pending_updates:
            logger.info("Navbatda turgan eski update'lar tashlandi (DROP_PENDING_UPDATES=true)")
        else:
            logger.info("Navbatda turgan update'lar saqlanadi — nomzod javobi yo'qolmaydi")

        logger.info(
            "Polling sozlamalari: polling_timeout=%ss, so'rov timeout=%ss, "
            "sekin so'rov chegarasi=%ss",
            settings.polling_timeout,
            settings.tg_request_timeout,
            settings.slow_request_threshold,
        )
        logger.info("Ishga tushish %.1f sekundda tugadi", time.perf_counter() - started_at)
        await dp.start_polling(
            bot,
            polling_timeout=settings.polling_timeout,
            backoff_config=FAST_BACKOFF,
        )
    finally:
        health_server.close()
        await health_server.wait_closed()
        await storage.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
