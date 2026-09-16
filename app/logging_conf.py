"""Loglash sozlamasi."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    for noisy in ("aiosqlite",):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# 409 Conflict — eng ko'p uchraydigan "bot sekin / bosqichdan o'tmayapti" sababi:
# shu token bilan ikkinchi jarayon ham long polling qiladi (eski deploy, ikkinchi
# machine, lokal kompyuter). Telegram update'larni ular o'rtasida bo'lib tashlaydi.
POLLING_CONFLICT_HINT = (
    "⚠️ Telegram 409 Conflict: shu bot tokenini BOSHQA jarayon ham so'ramoqda.\n"
    "   Telegram update'larni ikki jarayon o'rtasida bo'lib tashlaydi — bot sekin "
    "ishlaydi yoki bosqichdan o'tmaydi.\n"
    "   Tekshiring: (1) `fly scale count 1` — ikkita machine bo'lmasin; "
    "(2) eski server yoki lokal kompyuterda `python -m app.main` ishlab turmasin; "
    "(3) Vercel/Railway'dagi eski deploy butunlay o'chirilgan bo'lsin."
)


class _ConflictWatcher(logging.Handler):
    """aiogram polling loglarida 409 Conflict bo'lsa bir marta aniq ko'rsatma beradi."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self._warned = False

    def emit(self, record: logging.LogRecord) -> None:
        if self._warned:
            return
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - log yozuvi buzilgan bo'lishi mumkin
            return
        if "onflict" not in message:
            return
        self._warned = True
        logger.error(POLLING_CONFLICT_HINT)


def install_polling_conflict_watcher() -> None:
    """Polling loglarini kuzatuvchi handler'ni ulaydi (app.main chaqiradi)."""
    dispatcher_logger = logging.getLogger("aiogram.dispatcher")
    if any(isinstance(handler, _ConflictWatcher) for handler in dispatcher_logger.handlers):
        return
    dispatcher_logger.addHandler(_ConflictWatcher())
