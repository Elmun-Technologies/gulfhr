"""Ma'lumotlar bazasi modellari."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime


class Application(Base):
    """Vakansiya uchun nomzod arizasi — Telegram orqali yig'iladi."""

    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_application_created", "created_at"),
        # /stats hisoboti `is_qualified` bo'yicha sanaydi — indeks bilan tezroq
        Index("ix_application_qualified", "is_qualified"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), default="")  # "male" | "female"
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    lives_in_city: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Rus tilini bilish (vakansiya uchun majburiy talab)
    knows_russian: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    # Ish tajribasi (staj) — nomzod o'z so'zi bilan yozadi
    experience: Mapped[str] = mapped_column(Text, default="")
    # Rezume haqida qisqacha izoh ("📄 Fayl: ...", "🎤 Ovozli xabar yuborildi", ...)
    resume_info: Mapped[str] = mapped_column(Text, default="")
    # Yuborilgan rezume faylining Telegram file_id si (HR guruhiga forward uchun)
    resume_file_kind: Mapped[str | None] = mapped_column(String(16))  # voice|audio|document
    resume_file_id: Mapped[str | None] = mapped_column(String(255))

    # Nomzod tanlagan suhbat tili ("uz" | "ru") — HR qaysi tilda qo'ng'iroq
    # qilishni bilishi uchun kartada ko'rsatiladi
    language: Mapped[str] = mapped_column(String(8), default="", server_default="")

    telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))

    is_qualified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reject_codes: Mapped[str] = mapped_column(String(64), default="")  # "age,city,russian"
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - faqat debug uchun
        return f"<Application {self.id} {self.full_name!r} qualified={self.is_qualified}>"
