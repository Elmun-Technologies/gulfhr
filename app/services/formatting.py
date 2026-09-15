"""Matn formatlash yordamchilari (o'zbek tilida)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

MONTHS_UZ = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]
WEEKDAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


def money(value: float) -> str:
    """1234567 -> '1 234 567'."""
    return f"{int(round(value)):,}".replace(",", " ")


def number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def percent(value: float) -> str:
    return f"{value:.0f}%"


def format_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    return f"{value.day} {MONTHS_UZ[value.month - 1]} {value.year}"


def format_datetime(value: datetime | None, tz=UTC) -> str:
    if value is None:
        return "—"
    local = value.astimezone(tz) if value.tzinfo else value.replace(tzinfo=UTC).astimezone(tz)
    return local.strftime("%d.%m.%Y %H:%M")


def humanize_delta(delta: timedelta) -> str:
    """timedelta -> "3 kun 4 soat" ko'rinishi."""
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 1:
        return "1 daqiqadan kam"
    days, rem = divmod(total_minutes, 1440)
    hours, minutes = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} kun")
    if hours:
        parts.append(f"{hours} soat")
    if not days and minutes:
        parts.append(f"{minutes} daqiqa")
    return " ".join(parts) or "1 daqiqadan kam"


def progress_bar(ratio: float, width: int = 10) -> str:
    """0..1 -> '▓▓▓▓▓░░░░░'."""
    ratio = max(0.0, min(1.0, ratio))
    filled = int(round(ratio * width))
    return "▓" * filled + "░" * (width - filled)


def status_emoji(ratio: float, pace_ratio: float = 1.0) -> str:
    """Reja bajarilishiga qarab belgi tanlaydi."""
    if ratio >= 1.0:
        return "🏆"
    if pace_ratio <= 0:
        return "⚪️"
    relative = ratio / pace_ratio
    if relative >= 0.95:
        return "🟢"
    if relative >= 0.8:
        return "🟡"
    return "🔴"


def escape_html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
