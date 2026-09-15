"""Muhit sozlamalari (.env orqali)."""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Telegram ---
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    admin_telegram_ids: list[int] = Field(default_factory=list, alias="ADMIN_TELEGRAM_IDS")
    management_chat_id: int | None = Field(default=None, alias="MANAGEMENT_CHAT_ID")

    # --- Nomzodlarni saralash (vakansiya filteri) ---
    # Yosh chegarasi (default 18-30)
    candidate_min_age: int = Field(default=18, alias="CANDIDATE_MIN_AGE")
    candidate_max_age: int = Field(default=30, alias="CANDIDATE_MAX_AGE")
    # Nomzod doimiy istiqomat qilishi shart bo'lgan shahar
    candidate_city: str = Field(default="Toshkent", alias="CANDIDATE_CITY")
    # Rus tilini bilish majburiy talabmi (default: ha)
    candidate_russian_required: bool = Field(
        default=True, alias="CANDIDATE_RUSSIAN_REQUIRED"
    )
    # Nomzod kartasi yuboriladigan HR guruh. Bo'sh bo'lsa MANAGEMENT_CHAT_ID,
    # undan keyin LEAD_GROUP_CHAT_ID (eski Fly sozlamalari) ishlatiladi.
    candidates_chat_id: int | None = Field(default=None, alias="CANDIDATES_CHAT_ID")

    # --- Fly iloji (eski mustaqil lead-bot muhit o'zgaruvchilari) ---
    # BOT_TOKEN to'ldirilmagan bo'lsa LEADBOT_TOKEN ishlatiladi — Gulf HR
    # boti nomzodlar bilan ham, xodimlar bilan ham shu token orqali ishlaydi.
    leadbot_token: str = Field(default="", alias="LEADBOT_TOKEN")
    lead_group_chat_id: int = Field(default=0, alias="LEAD_GROUP_CHAT_ID")

    # --- Baza ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/gulf_hr.db", alias="DATABASE_URL"
    )

    # --- amoCRM ---
    amo_subdomain: str = Field(default="", alias="AMO_SUBDOMAIN")
    amo_client_id: str = Field(default="", alias="AMO_CLIENT_ID")
    amo_client_secret: str = Field(default="", alias="AMO_CLIENT_SECRET")
    amo_redirect_uri: str = Field(default="", alias="AMO_REDIRECT_URI")
    amo_auth_code: str = Field(default="", alias="AMO_AUTH_CODE")
    amo_long_token: str = Field(default="", alias="AMO_LONG_TOKEN")
    amo_first_status_id: int | None = Field(default=None, alias="AMO_FIRST_STATUS_ID")

    # --- Vaqt ---
    tz: str = Field(default="Asia/Tashkent", alias="TZ")

    # --- Web ---
    web_enabled: bool = Field(default=True, alias="WEB_ENABLED")
    web_host: str = Field(default="0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(default=8080, alias="WEB_PORT")
    webhook_secret: str = Field(default="change-me", alias="WEBHOOK_SECRET")

    # --- Qoidalar ---
    rule_first_response_minutes: int = Field(default=15, alias="RULE_FIRST_RESPONSE_MINUTES")
    rule_lead_without_task_hours: int = Field(default=4, alias="RULE_LEAD_WITHOUT_TASK_HOURS")
    rule_status_stuck_days: int = Field(default=3, alias="RULE_STATUS_STUCK_DAYS")
    rule_no_activity_days: int = Field(default=5, alias="RULE_NO_ACTIVITY_DAYS")
    rule_max_open_leads: int = Field(default=60, alias="RULE_MAX_OPEN_LEADS")
    rule_target_lag_percent: int = Field(default=15, alias="RULE_TARGET_LAG_PERCENT")

    # --- Jadval ---
    sync_interval_minutes: int = Field(default=5, alias="SYNC_INTERVAL_MINUTES")
    morning_digest_cron: str = Field(default="0 9 * * *", alias="MORNING_DIGEST_CRON")
    evening_digest_cron: str = Field(default="30 18 * * *", alias="EVENING_DIGEST_CRON")
    weekly_report_cron: str = Field(default="0 10 * * mon", alias="WEEKLY_REPORT_CRON")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        return [int(part.strip()) for part in str(value).split(",") if part.strip()]

    @field_validator("management_chat_id", mode="before")
    @classmethod
    def _parse_chat_id(cls, value: object) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    @field_validator("candidates_chat_id", mode="before")
    @classmethod
    def _parse_candidates_chat_id(cls, value: object) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    @field_validator("lead_group_chat_id", mode="before")
    @classmethod
    def _parse_lead_group_chat_id(cls, value: object) -> int:
        if value is None or value == "":
            return 0
        return int(value)

    @field_validator("amo_first_status_id", mode="before")
    @classmethod
    def _parse_status_id(cls, value: object) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @property
    def amo_base_url(self) -> str:
        return f"https://{self.amo_subdomain}.amocrm.ru"

    @property
    def amo_configured(self) -> bool:
        if not self.amo_subdomain:
            return False
        return bool(self.amo_long_token or (self.amo_client_id and self.amo_client_secret))

    @property
    def effective_bot_token(self) -> str:
        """Asosiy token; BOT_TOKEN bo'sh bo'lsa eski LEADBOT_TOKEN ishlatiladi."""
        return self.bot_token or self.leadbot_token

    @property
    def candidates_group_chat_id(self) -> int | None:
        """Nomzod kartalari yuboriladigan HR guruh ID si (fallback zanjiri bilan)."""
        if self.candidates_chat_id:
            return self.candidates_chat_id
        if self.management_chat_id:
            return self.management_chat_id
        if self.lead_group_chat_id:
            return self.lead_group_chat_id
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
