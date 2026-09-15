"""amoCRM webhook qabul qiluvchi va health-check uchun yengil FastAPI server.

amoCRM webhook'lari lid/vazifa o'zgarishi haqida real vaqtda xabar beradi.
Biz bu yerda to'liq payload'ni parse qilmaymiz — shunchaki navbatdagi
to'liq sinxronizatsiyani (job_sync_and_monitor) tezroq ishga tushirish uchun
signal sifatida ishlatamiz, chunki amoCRM to'liq bo'lmagan payload yuborishi mumkin.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from fastapi import FastAPI, Request, Response

from app.config import Settings

logger = logging.getLogger(__name__)


def build_app(bot: Bot, settings: Settings, on_webhook_kick) -> FastAPI:
    app = FastAPI(title="Gulf HR Bot", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/amocrm/webhook")
    async def amocrm_webhook(request: Request) -> Response:
        secret = request.query_params.get("secret")
        if settings.webhook_secret and secret != settings.webhook_secret:
            return Response(status_code=403)

        try:
            # amoCRM ba'zan form-urlencoded, ba'zan JSON yuboradi
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                await request.json()
            else:
                await request.form()
        except Exception:  # noqa: BLE001
            logger.debug("Webhook tanasi o'qib bo'lmadi (muhim emas)")

        asyncio.create_task(on_webhook_kick())
        return Response(status_code=200)

    return app
