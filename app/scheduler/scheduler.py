"""APScheduler bilan davriy vazifalarni ro'yxatga olish."""

from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import Settings
from app.scheduler.jobs import (
    job_evening_digest,
    job_morning_digest,
    job_sync_and_monitor,
    job_weekly_report,
)

logger = logging.getLogger(__name__)


def build_scheduler(bot: Bot, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)

    scheduler.add_job(
        job_sync_and_monitor,
        trigger=IntervalTrigger(minutes=settings.sync_interval_minutes),
        args=[bot],
        id="sync_and_monitor",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    scheduler.add_job(
        job_morning_digest,
        trigger=CronTrigger.from_crontab(settings.morning_digest_cron, timezone=settings.tz),
        args=[bot],
        id="morning_digest",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        job_evening_digest,
        trigger=CronTrigger.from_crontab(settings.evening_digest_cron, timezone=settings.tz),
        args=[bot],
        id="evening_digest",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        job_weekly_report,
        trigger=CronTrigger.from_crontab(settings.weekly_report_cron, timezone=settings.tz),
        args=[bot],
        id="weekly_report",
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        "Rejalashtiruvchi sozlandi: sync har %s daqiqada, tong=%s, kech=%s, hafta=%s",
        settings.sync_interval_minutes,
        settings.morning_digest_cron,
        settings.evening_digest_cron,
        settings.weekly_report_cron,
    )
    return scheduler
