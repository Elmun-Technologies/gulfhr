"""Telegram HTTP sessiyasi — tezlik va "osilib qolish"dan himoya.

Muammo: aiogram standart `AiohttpSession` da bitta so'rov uchun kutish chegarasi
**60 sekund**. Tarmoq uzilib qolsa (yoki Telegram javob bermay qolsa) handler shu
60 soniya davomida hech narsa qilmaydi — nomzod ekranida bot "o'ylanib" turadi.
Bu modul shu kutishni qisqartiradi va ulanishlarni qayta ishlatadi:

- **Qisqa timeout** (`TG_REQUEST_TIMEOUT`, default 15 s) — so'rov osilib qolsa
  bot tez xato beradi va keyingi update'ni ishlashda davom etadi;
- **Ulanishlarni qayta ishlatish** (`keepalive_timeout`) — har bir xabar uchun
  yangi TLS handshake qilinmaydi (har biri qo'shimcha ~1 RTT);
- **`enable_cleanup_closed`** — uzoq ishlaganda SSL ulanishlar to'planib,
  pool to'lib qolishining oldini oladi (aks holda yangi so'rovlar navbatda
  kutib qoladi — bot "sekinlashadi").
"""

from __future__ import annotations

from aiogram.client.session.aiohttp import AiohttpSession


class GulfAiohttpSession(AiohttpSession):
    """Botning kunlab uzluksiz ishlashiga moslangan aiohttp sessiyasi."""

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        limit: int = 32,
        keepalive_timeout: float = 45.0,
    ) -> None:
        super().__init__(timeout=timeout, limit=limit)
        # `_connector_init` — aiogram shu lug'atni `TCPConnector` ga beradi.
        self._connector_init.update(
            {
                "keepalive_timeout": keepalive_timeout,
                "enable_cleanup_closed": True,
            }
        )


def build_session(
    *, timeout: float = 15.0, limit: int = 32, keepalive_timeout: float = 45.0
) -> GulfAiohttpSession:
    """Sozlamalarga moslashtirilgan sessiya yaratadi."""
    return GulfAiohttpSession(
        timeout=timeout,
        limit=limit,
        keepalive_timeout=keepalive_timeout,
    )


__all__ = ["GulfAiohttpSession", "build_session"]
