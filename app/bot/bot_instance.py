"""Global Bot obyektiga kirish (aylanma importlardan qochish uchun)."""

from __future__ import annotations

from aiogram import Bot

_bot: Bot | None = None


def set_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


def get_bot() -> Bot:
    if _bot is None:
        raise RuntimeError("Bot hali ishga tushirilmagan.")
    return _bot
