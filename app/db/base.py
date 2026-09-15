"""SQLAlchemy deklarativ asos va umumiy enumlar."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import UTCDateTime


class Base(DeclarativeBase):
    """Barcha modellar uchun asosiy klass."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Role(str, enum.Enum):
    """Bot ichidagi rollar."""

    SALES = "sales"       # Sotuvchi
    HEAD = "head"         # Sotuv bo'limi boshlig'i
    HR = "hr"             # HR
    ADMIN = "admin"       # Tizim administratori

    @property
    def label_uz(self) -> str:
        return {
            Role.SALES: "Sotuvchi",
            Role.HEAD: "Bo'lim boshlig'i",
            Role.HR: "HR",
            Role.ADMIN: "Administrator",
        }[self]

    @property
    def is_manager(self) -> bool:
        return self in (Role.HEAD, Role.HR, Role.ADMIN)


class MetricType(str, enum.Enum):
    """Target o'lchov birliklari."""

    REVENUE = "revenue"             # Summa (so'm)
    WON_DEALS = "won_deals"         # Yopilgan (muvaffaqiyatli) bitimlar soni
    NEW_LEADS = "new_leads"         # Yangi lidlar soni
    CONVERSION = "conversion"       # Konversiya (%)

    @property
    def label_uz(self) -> str:
        return {
            MetricType.REVENUE: "Savdo summasi",
            MetricType.WON_DEALS: "Yopilgan bitimlar",
            MetricType.NEW_LEADS: "Yangi lidlar",
            MetricType.CONVERSION: "Konversiya",
        }[self]

    @property
    def unit_uz(self) -> str:
        return {
            MetricType.REVENUE: "so'm",
            MetricType.WON_DEALS: "ta",
            MetricType.NEW_LEADS: "ta",
            MetricType.CONVERSION: "%",
        }[self]


class Severity(str, enum.Enum):
    """Ogohlantirish darajasi."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def emoji(self) -> str:
        return {Severity.INFO: "ℹ️", Severity.WARNING: "⚠️", Severity.CRITICAL: "🔴"}[self]


class TargetPeriod(str, enum.Enum):
    """Target davri."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @property
    def label_uz(self) -> str:
        return {
            TargetPeriod.DAILY: "Kunlik",
            TargetPeriod.WEEKLY: "Haftalik",
            TargetPeriod.MONTHLY: "Oylik",
        }[self]
