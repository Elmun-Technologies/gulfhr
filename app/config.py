"""Sozlamalar (.env orqali)."""

from __future__ import annotations

import re
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
    # Rahbariyat/HR umumiy guruhi (ixtiyoriy) — nomzodlar guruhining
    # fallback'i sifatida ishlatiladi
    management_chat_id: int | None = Field(default=None, alias="MANAGEMENT_CHAT_ID")

    # --- Til ---
    # /start da til tanlash oynasini ko'rsatish (🇺🇿 O'zbekcha / 🇷🇺 Русский)
    language_choice: bool = Field(default=True, alias="LANGUAGE_CHOICE")
    # Til tanlash o'chirilgan bo'lsa (yoki noma'lum til kelsa) ishlatiladigan til
    default_language: str = Field(default="uz", alias="DEFAULT_LANGUAGE")

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
    lead_group_chat_id: int = Field(default=0, alias="LEAD_GROUP_CHAT_ID")

    # --- Baza ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/gulf_hr.db", alias="DATABASE_URL"
    )
    # Suhbat holati (FSM) saqlanadigan fayl — bot qayta ishga tushganda
    # nomzod yozayotgan ariza yo'qolmasligi uchun
    fsm_db_path: str = Field(default="./data/fsm.db", alias="FSM_DB_PATH")

    # --- Telegram API (tezlik va "osilib qolish"dan himoya) ---
    # Bitta Telegram so'rovi uchun kutish chegarasi (sekund). aiogram standarti
    # 60 s: tarmoq uzilsa bot bir daqiqa javob bermay "o'ylanib" qoladi.
    tg_request_timeout: float = Field(default=15.0, alias="TG_REQUEST_TIMEOUT")
    # Bir vaqtda ochiq turishi mumkin bo'lgan HTTPS ulanishlar soni
    tg_connections: int = Field(default=32, alias="TG_CONNECTIONS")
    # Long polling: Telegram so'rovni shu vaqt ushlab turadi (sekund)
    polling_timeout: int = Field(default=10, alias="POLLING_TIMEOUT")
    # Bot qayta ishga tushganda Telegram navbatida turgan update'lar tashlab
    # yuborilsinmi. `false` (default) — nomzod bot o'chib turganda bosgan
    # tugmasi yo'qolmaydi va suhbat davom etadi (FSM bazada saqlanadi).
    drop_pending_updates: bool = Field(default=False, alias="DROP_PENDING_UPDATES")
    # /diag buyrug'i shaxsiy chatda ham ishlaydigan user id'lar (vergul bilan)
    admin_user_ids: str = Field(default="", alias="ADMIN_USER_IDS")
    # Necha sekunddan sekin update logga "sekin" bo'lib yoziladi
    slow_request_threshold: float = Field(default=0.5, alias="SLOW_REQUEST_THRESHOLD")

    # --- Vaqt ---
    tz: str = Field(default="Asia/Tashkent", alias="TZ")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

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

    @field_validator("language_choice", "drop_pending_updates", mode="before")
    @classmethod
    def _parse_bool(cls, value: object) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "ha"}
        return bool(value)

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @property
    def admin_user_id_set(self) -> frozenset[int]:
        """`ADMIN_USER_IDS` ("123, 456") ni to'plamga aylantiradi."""
        parts = re.split(r"[,\s]+", self.admin_user_ids.strip())
        ids: set[int] = set()
        for part in parts:
            if part.lstrip("-").isdigit():
                ids.add(int(part))
        return frozenset(ids)

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
