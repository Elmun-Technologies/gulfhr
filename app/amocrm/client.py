"""amoCRM API v4 mijozi: rate-limit, avto-refresh va sahifalash."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.amocrm.auth import TokenManager
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# amoCRM cheklovi — sekundiga 7 so'rov. Xavfsizlik uchun 5 tadan oshirmaymiz.
MAX_REQUESTS_PER_SECOND = 5
PAGE_LIMIT = 250


class AmoApiError(RuntimeError):
    """amoCRM API xatosi."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"amoCRM API {status_code}: {message}")
        self.status_code = status_code


class RateLimiter:
    """Sekundiga N so'rovdan oshmaslikni ta'minlaydigan oddiy oyna."""

    def __init__(self, max_per_second: int = MAX_REQUESTS_PER_SECOND) -> None:
        self.max_per_second = max_per_second
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= 1.0:
                    self._calls.popleft()
                if len(self._calls) < self.max_per_second:
                    self._calls.append(now)
                    return
                await asyncio.sleep(1.0 - (now - self._calls[0]))


class AmoCrmClient:
    """amoCRM bilan ishlash uchun yuqori darajali mijoz."""

    def __init__(
        self,
        settings: Settings | None = None,
        token_manager: TokenManager | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.tokens = token_manager or TokenManager(self.settings)
        self._client = http_client
        self._owns_client = http_client is None
        self._limiter = RateLimiter()

    async def __aenter__(self) -> AmoCrmClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.settings.amo_base_url, timeout=45)
            self._owns_client = True
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------ #
    # Past daraja
    # ------------------------------------------------------------------ #

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        retry_on_auth: bool = True,
    ) -> dict[str, Any] | None:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.settings.amo_base_url, timeout=45)
            self._owns_client = True

        token = await self.tokens.get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        for attempt in range(4):
            await self._limiter.acquire()
            try:
                response = await self._client.request(
                    method, path, params=params, json=json, headers=headers
                )
            except httpx.HTTPError as exc:
                if attempt == 3:
                    raise AmoApiError(0, f"tarmoq xatosi: {exc}") from exc
                await asyncio.sleep(2**attempt)
                continue

            if response.status_code == 401 and retry_on_auth:
                self.tokens.invalidate()
                token = await self.tokens.get_access_token()
                headers["Authorization"] = f"Bearer {token}"
                retry_on_auth = False
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 3:
                    raise AmoApiError(response.status_code, response.text[:400])
                await asyncio.sleep(2**attempt)
                continue

            if response.status_code == 204:
                return None
            if response.status_code >= 400:
                raise AmoApiError(response.status_code, response.text[:400])
            if not response.content:
                return None
            return response.json()

        raise AmoApiError(0, "so'rov qayta urinishlardan keyin ham bajarilmadi")

    async def paginate(
        self, path: str, key: str, params: dict[str, Any] | None = None, max_pages: int = 200
    ) -> AsyncIterator[dict[str, Any]]:
        """`_embedded[key]` ro'yxatini sahifama-sahifa qaytaradi."""
        page = 1
        base_params = dict(params or {})
        base_params.setdefault("limit", PAGE_LIMIT)
        while page <= max_pages:
            base_params["page"] = page
            payload = await self.request("GET", path, params=base_params)
            if not payload:
                return
            items = payload.get("_embedded", {}).get(key, [])
            if not items:
                return
            for item in items:
                yield item
            if len(items) < base_params["limit"]:
                return
            if not payload.get("_links", {}).get("next"):
                return
            page += 1

    # ------------------------------------------------------------------ #
    # Yuqori daraja
    # ------------------------------------------------------------------ #

    async def get_account(self) -> dict[str, Any] | None:
        return await self.request("GET", "/api/v4/account")

    async def get_users(self) -> list[dict[str, Any]]:
        return [item async for item in self.paginate("/api/v4/users", "users")]

    async def get_pipelines(self) -> list[dict[str, Any]]:
        payload = await self.request("GET", "/api/v4/leads/pipelines")
        if not payload:
            return []
        return payload.get("_embedded", {}).get("pipelines", [])

    async def get_leads(
        self, updated_from: int | None = None, extra_filters: dict[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        params: dict[str, Any] = {"with": "loss_reason"}
        if updated_from is not None:
            params["filter[updated_at][from]"] = updated_from
        params.update(extra_filters or {})
        async for lead in self.paginate("/api/v4/leads", "leads", params):
            yield lead

    async def get_tasks(
        self, updated_from: int | None = None, only_open: bool = False
    ) -> AsyncIterator[dict[str, Any]]:
        params: dict[str, Any] = {}
        if updated_from is not None:
            params["filter[updated_at][from]"] = updated_from
        if only_open:
            params["filter[is_completed]"] = 0
        async for task in self.paginate("/api/v4/tasks", "tasks", params):
            yield task

    async def get_lead(self, lead_id: int) -> dict[str, Any] | None:
        return await self.request("GET", f"/api/v4/leads/{lead_id}", params={"with": "loss_reason"})

    async def get_events(
        self, entity_type: str = "lead", created_from: int | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        params: dict[str, Any] = {"filter[entity]": entity_type}
        if created_from is not None:
            params["filter[created_at][from]"] = created_from
        async for event in self.paginate("/api/v4/events", "events", params):
            yield event

    def lead_url(self, lead_id: int) -> str:
        return f"{self.settings.amo_base_url}/leads/detail/{lead_id}"
