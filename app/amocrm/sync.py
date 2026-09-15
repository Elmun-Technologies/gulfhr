"""amoCRM -> lokal baza sinxronizatsiyasi."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.amocrm.client import AmoCrmClient
from app.db.models import AmoUser, Lead, Pipeline, PipelineStatus, Task
from app.db.session import session_scope
from app.services.kv import get_value, set_value

logger = logging.getLogger(__name__)

# Kursorni biroz orqaga surib olamiz — chegaradagi yozuvlarni yo'qotmaslik uchun
CURSOR_OVERLAP = timedelta(minutes=10)
CURSOR_LEADS = "sync:leads:updated_at"
CURSOR_TASKS = "sync:tasks:updated_at"
FULL_SYNC_LOOKBACK_DAYS = 180


@dataclass
class SyncResult:
    users: int = 0
    pipelines: int = 0
    statuses: int = 0
    leads: int = 0
    tasks: int = 0
    errors: list[str] = field(default_factory=list)

    def summary_uz(self) -> str:
        parts = [
            f"foydalanuvchi: {self.users}",
            f"voronka: {self.pipelines}",
            f"bosqich: {self.statuses}",
            f"lid: {self.leads}",
            f"vazifa: {self.tasks}",
        ]
        text = ", ".join(parts)
        if self.errors:
            text += f" | xatolar: {len(self.errors)}"
        return text


def _ts_to_dt(value: Any) -> datetime | None:
    if value in (None, 0, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


async def sync_users(client: AmoCrmClient, session: AsyncSession) -> int:
    users = await client.get_users()
    now = datetime.now(UTC)
    count = 0
    for payload in users:
        user_id = int(payload["id"])
        record = await session.get(AmoUser, user_id)
        if record is None:
            record = AmoUser(id=user_id)
            session.add(record)
        record.name = payload.get("name") or ""
        record.email = payload.get("email")
        rights = payload.get("rights") or {}
        record.is_active = not bool(rights.get("is_free")) if rights else True
        record.synced_at = now
        count += 1
    return count


async def sync_pipelines(client: AmoCrmClient, session: AsyncSession) -> tuple[int, int]:
    pipelines = await client.get_pipelines()
    pipeline_count = 0
    status_count = 0
    for payload in pipelines:
        pipeline_id = int(payload["id"])
        record = await session.get(Pipeline, pipeline_id)
        if record is None:
            record = Pipeline(id=pipeline_id)
            session.add(record)
        record.name = payload.get("name") or ""
        record.sort = int(payload.get("sort") or 0)
        record.is_main = bool(payload.get("is_main"))
        pipeline_count += 1

        for status in payload.get("_embedded", {}).get("statuses", []):
            status_id = int(status["id"])
            status_record = await session.get(PipelineStatus, status_id)
            if status_record is None:
                status_record = PipelineStatus(id=status_id)
                session.add(status_record)
            status_record.pipeline_id = pipeline_id
            status_record.name = status.get("name") or ""
            status_record.sort = int(status.get("sort") or 0)
            status_record.color = status.get("color")
            status_count += 1
    return pipeline_count, status_count


async def sync_leads(client: AmoCrmClient, session: AsyncSession, full: bool = False) -> int:
    cursor = None if full else await get_value(session, CURSOR_LEADS)
    if cursor:
        updated_from = int(cursor) - int(CURSOR_OVERLAP.total_seconds())
    else:
        updated_from = int(
            (datetime.now(UTC) - timedelta(days=FULL_SYNC_LOOKBACK_DAYS)).timestamp()
        )

    now = datetime.now(UTC)
    max_updated = updated_from
    count = 0

    async for payload in client.get_leads(updated_from=updated_from):
        lead_id = int(payload["id"])
        record = await session.get(Lead, lead_id)
        is_new = record is None
        if record is None:
            record = Lead(id=lead_id)
            session.add(record)

        new_status_id = int(payload.get("status_id") or 0)
        previous_status_id = None if is_new else record.status_id
        updated_at = _ts_to_dt(payload.get("updated_at"))

        record.name = (payload.get("name") or "")[:500]
        record.price = float(payload.get("price") or 0)
        record.pipeline_id = int(payload.get("pipeline_id") or 0)
        record.responsible_user_id = payload.get("responsible_user_id")
        record.loss_reason_id = payload.get("loss_reason_id")
        record.created_at = _ts_to_dt(payload.get("created_at"))
        record.updated_at = updated_at
        record.closed_at = _ts_to_dt(payload.get("closed_at"))
        record.synced_at = now

        if is_new or previous_status_id != new_status_id:
            record.status_changed_at = updated_at or now
            # Boshlang'ich bosqichdan chiqish — sotuvchining birinchi harakati
            if not is_new and record.first_touch_at is None:
                record.first_touch_at = updated_at or now
        record.status_id = new_status_id

        max_updated = max(max_updated, int(payload.get("updated_at") or 0))
        count += 1

    if count:
        await set_value(session, CURSOR_LEADS, str(max_updated))
    return count


async def sync_tasks(client: AmoCrmClient, session: AsyncSession, full: bool = False) -> int:
    cursor = None if full else await get_value(session, CURSOR_TASKS)
    if cursor:
        updated_from = int(cursor) - int(CURSOR_OVERLAP.total_seconds())
    else:
        updated_from = int(
            (datetime.now(UTC) - timedelta(days=FULL_SYNC_LOOKBACK_DAYS)).timestamp()
        )

    now = datetime.now(UTC)
    max_updated = updated_from
    count = 0

    async for payload in client.get_tasks(updated_from=updated_from):
        task_id = int(payload["id"])
        record = await session.get(Task, task_id)
        if record is None:
            record = Task(id=task_id)
            session.add(record)
        record.entity_id = payload.get("entity_id")
        record.entity_type = payload.get("entity_type")
        record.text = payload.get("text") or ""
        record.responsible_user_id = payload.get("responsible_user_id")
        record.complete_till = _ts_to_dt(payload.get("complete_till"))
        record.is_completed = bool(payload.get("is_completed"))
        record.created_at = _ts_to_dt(payload.get("created_at"))
        record.updated_at = _ts_to_dt(payload.get("updated_at"))
        record.synced_at = now

        max_updated = max(max_updated, int(payload.get("updated_at") or 0))
        count += 1

    if count:
        await set_value(session, CURSOR_TASKS, str(max_updated))
    return count


async def refresh_lead_task_flags(session: AsyncSession) -> None:
    """Har bir lid uchun ochiq vazifa bor-yo'qligini qayta hisoblaydi."""
    await session.execute(update(Lead).values(has_open_task=False, next_task_at=None))

    result = await session.execute(
        select(Task.entity_id, Task.complete_till)
        .where(Task.entity_type == "leads", Task.is_completed.is_(False))
        .where(Task.entity_id.is_not(None))
    )
    earliest: dict[int, datetime | None] = {}
    for entity_id, complete_till in result.all():
        current = earliest.get(entity_id, "missing")  # type: ignore[assignment]
        if current == "missing":
            earliest[entity_id] = complete_till
        elif complete_till is not None and (current is None or complete_till < current):
            earliest[entity_id] = complete_till

    for lead_id, complete_till in earliest.items():
        await session.execute(
            update(Lead)
            .where(Lead.id == lead_id)
            .values(has_open_task=True, next_task_at=complete_till)
        )


async def mark_first_touch_from_tasks(session: AsyncSession) -> None:
    """Yopilgan vazifa ham "birinchi kontakt" hisoblanadi."""
    result = await session.execute(
        select(Task.entity_id, Task.updated_at)
        .where(Task.entity_type == "leads", Task.is_completed.is_(True))
        .where(Task.entity_id.is_not(None))
    )
    touches: dict[int, datetime] = {}
    for entity_id, updated_at in result.all():
        if updated_at is None:
            continue
        if entity_id not in touches or updated_at < touches[entity_id]:
            touches[entity_id] = updated_at

    if not touches:
        return

    leads = await session.execute(
        select(Lead).where(Lead.id.in_(list(touches)), Lead.first_touch_at.is_(None))
    )
    for lead in leads.scalars():
        lead.first_touch_at = touches[lead.id]


async def run_sync(full: bool = False, client: AmoCrmClient | None = None) -> SyncResult:
    """To'liq sinxronizatsiya sikli."""
    result = SyncResult()
    owns_client = client is None
    client = client or AmoCrmClient()
    try:
        async with session_scope() as session:
            try:
                result.users = await sync_users(client, session)
                result.pipelines, result.statuses = await sync_pipelines(client, session)
            except Exception as exc:  # noqa: BLE001 - qismiy muvaffaqiyatga ruxsat
                logger.exception("Ma'lumotnomalarni sinxronlashda xato")
                result.errors.append(f"spravochnik: {exc}")

            result.leads = await sync_leads(client, session, full=full)
            result.tasks = await sync_tasks(client, session, full=full)
            await refresh_lead_task_flags(session)
            await mark_first_touch_from_tasks(session)
    finally:
        if owns_client:
            await client.aclose()

    logger.info("Sinxronizatsiya yakunlandi: %s", result.summary_uz())
    return result
