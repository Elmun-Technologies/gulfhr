"""Ma'lumotlar bazasi modellari."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, MetricType, Role, Severity, TargetPeriod, TimestampMixin
from app.db.types import UTCDateTime

# amoCRM tizim bosqichlari
AMO_STATUS_WON = 142
AMO_STATUS_LOST = 143


class Employee(Base, TimestampMixin):
    """Xodim: sotuvchi, bo'lim boshlig'i, HR yoki admin."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    position: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.SALES, nullable=False)

    # amoCRM'dagi foydalanuvchi ID si — jarayon nazorati shu bog'lanish orqali ishlaydi
    amo_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Ro'yxatdan o'tish uchun bir martalik kod
    invite_code: Mapped[str | None] = mapped_column(String(16), unique=True, index=True)

    targets: Mapped[list[Target]] = relationship(
        back_populates="employee", foreign_keys="Target.employee_id"
    )
    alerts: Mapped[list[Alert]] = relationship(back_populates="employee")

    def __repr__(self) -> str:  # pragma: no cover - faqat debug uchun
        return f"<Employee {self.id} {self.full_name!r} role={self.role.value}>"


class Target(Base, TimestampMixin):
    """Xodimga qo'yilgan target (plan)."""

    __tablename__ = "targets"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "metric", "period_start", "period_end", name="uq_target_slot"
        ),
        Index("ix_target_period", "period_start", "period_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric: Mapped[MetricType] = mapped_column(Enum(MetricType), nullable=False)
    period: Mapped[TargetPeriod] = mapped_column(
        Enum(TargetPeriod), default=TargetPeriod.MONTHLY, nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    employee: Mapped[Employee] = relationship(
        back_populates="targets", foreign_keys=[employee_id]
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Target {self.metric.value}={self.target_value} emp={self.employee_id}>"


class Application(Base):
    """Vakansiya uchun nomzod arizasi — Telegram orqali yig'iladi."""

    __tablename__ = "applications"
    __table_args__ = (Index("ix_application_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), default="")  # "male" | "female"
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    lives_in_city: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    # Ish tajribasi (staj) — nomzod o'z so'zi bilan yozadi
    experience: Mapped[str] = mapped_column(Text, default="")
    # Rezume haqida qisqacha izoh ("📄 Fayl: ...", "🎤 Ovozli xabar yuborildi", ...)
    resume_info: Mapped[str] = mapped_column(Text, default="")
    # Yuborilgan rezume faylining Telegram file_id si (HR guruhiga forward uchun)
    resume_file_kind: Mapped[str | None] = mapped_column(String(16))  # voice|audio|document
    resume_file_id: Mapped[str | None] = mapped_column(String(255))

    telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))

    is_qualified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reject_codes: Mapped[str] = mapped_column(String(64), default="")  # "age,city"
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - faqat debug uchun
        return f"<Application {self.id} {self.full_name!r} qualified={self.is_qualified}>"


class AmoUser(Base):
    """amoCRM foydalanuvchilari (sinxron nusxa)."""

    __tablename__ = "amo_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Pipeline(Base):
    """amoCRM voronkasi."""

    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)


class PipelineStatus(Base):
    """Voronka bosqichi. `max_days` — shu bosqichda ruxsat etilgan maksimal muddat."""

    __tablename__ = "pipeline_statuses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    pipeline_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str | None] = mapped_column(String(16))
    # Bosqichga xos SLA (kun). None bo'lsa global sozlama ishlatiladi.
    max_days: Mapped[int | None] = mapped_column(Integer)


class Lead(Base):
    """amoCRM bitimi (lid) — nazorat uchun kerakli maydonlar."""

    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_lead_owner_status", "responsible_user_id", "status_id"),
        Index("ix_lead_closed", "closed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(500), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    status_id: Mapped[int] = mapped_column(BigInteger, index=True)
    pipeline_id: Mapped[int] = mapped_column(BigInteger, index=True)
    responsible_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    loss_reason_id: Mapped[int | None] = mapped_column(BigInteger)

    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Oxirgi bosqich o'zgargan vaqt (sinxronizatsiya davomida aniqlanadi)
    status_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Sotuvchi lidga birinchi marta qachon "tegingan" (bosqich o'zgardi yoki vazifa yopildi)
    first_touch_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    has_open_task: Mapped[bool] = mapped_column(Boolean, default=False)
    next_task_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    @property
    def is_won(self) -> bool:
        return self.status_id == AMO_STATUS_WON

    @property
    def is_lost(self) -> bool:
        return self.status_id == AMO_STATUS_LOST

    @property
    def is_open(self) -> bool:
        return not self.is_won and not self.is_lost


class Task(Base):
    """amoCRM vazifasi."""

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_task_owner_state", "responsible_user_id", "is_completed"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text, default="")
    responsible_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    complete_till: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Alert(Base):
    """Qoidalar dvigateli aniqlagan buzilish."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_alert_dedup"),
        Index("ix_alert_open", "resolved_at", "rule_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), default=Severity.WARNING)

    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), index=True
    )
    amo_user_id: Mapped[int | None] = mapped_column(BigInteger)
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)

    title: Mapped[str] = mapped_column(String(255), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    escalated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    employee: Mapped[Employee | None] = relationship(back_populates="alerts")


class AmoToken(Base):
    """amoCRM OAuth tokenlari."""

    __tablename__ = "amo_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class KeyValue(Base):
    """Oddiy kalit-qiymat saqlagichi (sinxronizatsiya kursorlari va h.k.)."""

    __tablename__ = "kv_store"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class DailyStat(Base):
    """Kunlik kesim — tarixiy hisobotlar uchun."""

    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("employee_id", "stat_date", name="uq_daily_stat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    stat_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    new_leads: Mapped[int] = mapped_column(Integer, default=0)
    won_deals: Mapped[int] = mapped_column(Integer, default=0)
    lost_deals: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    open_leads: Mapped[int] = mapped_column(Integer, default=0)
    overdue_tasks: Mapped[int] = mapped_column(Integer, default=0)
    alerts_count: Mapped[int] = mapped_column(Integer, default=0)
