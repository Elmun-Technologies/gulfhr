"""Bot ishlashining yig'ma ko'rsatkichlari.

Bot "sekin" bo'lganda aybdorni topish uchun oddiy o'lchovlar yetarli: nechta
update qayta ishlandi, qanchasi sekin bo'ldi, eng sekin so'rov qancha vaqt oldi.
Bu modul shu raqamlarni yig'adi (`TimingsMiddleware` yozadi) va `/diag`
buyrug'i nomzod/HR uchun o'qiladigan ko'rinishda chiqaradi.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RequestStats:
    """Jarayon davomida yig'iladigan ko'rsatkichlar (xotirada, o'zi yozilmaydi)."""

    started_at: float = field(default_factory=time.time)
    updates: int = 0
    slow: int = 0
    errors: int = 0
    slowest_seconds: float = 0.0
    slowest_label: str = ""
    last_slow_seconds: float | None = None
    last_slow_label: str | None = None
    last_slow_at: float | None = None

    def observe(self, label: str, seconds: float, *, slow_threshold: float) -> bool:
        """Bitta update vaqtini yozadi. `True` — sekin bo'lsa."""
        self.updates += 1
        if seconds > self.slowest_seconds:
            self.slowest_seconds = seconds
            self.slowest_label = label
        is_slow = seconds >= slow_threshold
        if is_slow:
            self.slow += 1
            self.last_slow_seconds = seconds
            self.last_slow_label = label
            self.last_slow_at = time.time()
        return is_slow

    def observe_error(self) -> None:
        self.errors += 1

    @property
    def uptime_seconds(self) -> float:
        return max(0.0, time.time() - self.started_at)

    def snapshot(self) -> dict[str, object]:
        """`/diag` uchun nusxa (thread/task xavfsiz — oddiy o'qish)."""
        return {
            "updates": self.updates,
            "slow": self.slow,
            "errors": self.errors,
            "slowest_seconds": self.slowest_seconds,
            "slowest_label": self.slowest_label,
            "last_slow_seconds": self.last_slow_seconds,
            "last_slow_label": self.last_slow_label,
            "last_slow_at": self.last_slow_at,
            "uptime_seconds": self.uptime_seconds,
        }


# Butun jarayon uchun bitta nusxa
STATS = RequestStats()


def humanize_duration(seconds: float) -> str:
    """`3725` → `1 soat 2 daqiqa`."""
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, secs = divmod(seconds, 60)
    if days:
        return f"{days} kun {hours} soat"
    if hours:
        return f"{hours} soat {minutes} daqiqa"
    if minutes:
        return f"{minutes} daqiqa {secs} sekund"
    return f"{secs} sekund"


__all__ = ["STATS", "RequestStats", "humanize_duration"]
