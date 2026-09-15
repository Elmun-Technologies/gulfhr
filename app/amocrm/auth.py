"""amoCRM OAuth 2.0 token boshqaruvi."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app.config import Settings, get_settings
from app.db.models import AmoToken
from app.db.session import session_scope

logger = logging.getLogger(__name__)

# Tokenni muddati tugashidan shuncha vaqt oldin yangilaymiz
REFRESH_MARGIN = timedelta(minutes=5)


class AmoAuthError(RuntimeError):
    """amoCRM avtorizatsiyasi bilan bog'liq xato."""


class TokenManager:
    """Access tokenni oladi, yangilaydi va bazada saqlaydi.

    Ikki rejim qo'llab-quvvatlanadi:
      * `AMO_LONG_TOKEN` — uzoq muddatli token (yangilash talab qilinmaydi);
      * OAuth 2.0 — `authorization_code` -> `refresh_token` aylanishi.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._lock = asyncio.Lock()
        self._cached: tuple[str, datetime] | None = None

    @property
    def _token_url(self) -> str:
        return f"{self.settings.amo_base_url}/oauth2/access_token"

    async def get_access_token(self) -> str:
        if self.settings.amo_long_token:
            return self.settings.amo_long_token

        if self._cached:
            token, expires_at = self._cached
            if datetime.now(UTC) + REFRESH_MARGIN < expires_at:
                return token

        async with self._lock:
            # Lock kutilayotgan vaqtda boshqa korutina yangilagan bo'lishi mumkin
            if self._cached:
                token, expires_at = self._cached
                if datetime.now(UTC) + REFRESH_MARGIN < expires_at:
                    return token

            record = await self._load_record()
            if record is None:
                record = await self._exchange_auth_code()
            elif self._expires_soon(record.expires_at):
                record = await self._refresh(record.refresh_token)

            self._cached = (record.access_token, _as_utc(record.expires_at))
            return record.access_token

    # ------------------------------------------------------------------ #

    @staticmethod
    def _expires_soon(expires_at: datetime) -> bool:
        return datetime.now(UTC) + REFRESH_MARGIN >= _as_utc(expires_at)

    async def _load_record(self) -> AmoToken | None:
        async with session_scope() as session:
            result = await session.execute(select(AmoToken).order_by(AmoToken.id.desc()).limit(1))
            return result.scalar_one_or_none()

    async def _exchange_auth_code(self) -> AmoToken:
        if not self.settings.amo_auth_code:
            raise AmoAuthError(
                "amoCRM tokeni topilmadi. .env faylida AMO_AUTH_CODE yoki AMO_LONG_TOKEN ni to'ldiring."
            )
        payload = {
            "client_id": self.settings.amo_client_id,
            "client_secret": self.settings.amo_client_secret,
            "grant_type": "authorization_code",
            "code": self.settings.amo_auth_code,
            "redirect_uri": self.settings.amo_redirect_uri,
        }
        logger.info("amoCRM: authorization_code almashtirilmoqda")
        return await self._request_token(payload)

    async def _refresh(self, refresh_token: str) -> AmoToken:
        if not refresh_token:
            raise AmoAuthError("refresh_token saqlanmagan — qayta avtorizatsiya kerak.")
        payload = {
            "client_id": self.settings.amo_client_id,
            "client_secret": self.settings.amo_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": self.settings.amo_redirect_uri,
        }
        logger.info("amoCRM: access token yangilanmoqda")
        return await self._request_token(payload)

    async def _request_token(self, payload: dict[str, str]) -> AmoToken:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self._token_url, json=payload)
        if response.status_code >= 400:
            raise AmoAuthError(
                f"amoCRM token so'rovi muvaffaqiyatsiz ({response.status_code}): {response.text}"
            )
        data = response.json()
        expires_at = datetime.now(UTC) + timedelta(seconds=int(data.get("expires_in", 86400)))
        return await self._store(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            expires_at=expires_at,
        )

    async def _store(self, access_token: str, refresh_token: str, expires_at: datetime) -> AmoToken:
        async with session_scope() as session:
            result = await session.execute(select(AmoToken).order_by(AmoToken.id.desc()).limit(1))
            record = result.scalar_one_or_none()
            if record is None:
                record = AmoToken(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    updated_at=datetime.now(UTC),
                )
                session.add(record)
            else:
                record.access_token = access_token
                if refresh_token:
                    record.refresh_token = refresh_token
                record.expires_at = expires_at
                record.updated_at = datetime.now(UTC)
            await session.flush()
            session.expunge(record)
        return record

    def invalidate(self) -> None:
        """Keshni tozalaydi (401 javobidan keyin)."""
        self._cached = None


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
