"""Kutilmagan xatolar handleri — bot hech qachon "jim o'ylanib" qolmasligi uchun.

Nima uchun kerak: aiogram xatoni faqat **log'ga** yozadi (`Cause exception while
process update...`), nomzodga esa hech narsa yuborilmaydi. Nomzod uchun bu
"bot o'ylanib qoldi, keyingi savolga o'tmayapti" degani — aslida esa handler
xato bilan to'xtagan bo'ladi.

Bu handler:
1. xatoni to'liq kontekst bilan (update turi, user, chat, FSM holati) logga yozadi;
2. nomzodga qisqa ikki tilli xabar yuboradi va `/start` ni taklif qiladi;
3. tugma bosilgan bo'lsa, "soat" belgisini o'chiradi (`callback.answer`).
"""

from __future__ import annotations

import logging

from aiogram import Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ErrorEvent, InaccessibleMessage, Message

from app.bot.stats import STATS

logger = logging.getLogger(__name__)

# Nomzodga ko'rsatiladigan xabar — til hali noma'lum bo'lishi mumkin, shuning
# uchun ikki tilda (botning til tanlash oynasi ham shunday).
USER_ERROR_MESSAGE = (
    "⚠️ <b>Kechirasiz, texnik xatolik yuz berdi.</b>\n"
    "Iltimos, /start buyrug'ini qaytadan yuboring.\n\n"
    "⚠️ <b>Извините, произошла техническая ошибка.</b>\n"
    "Пожалуйста, отправьте /start ещё раз."
)


def _describe(event: ErrorEvent) -> str:
    """Log uchun qisqa kontekst: qaysi update, kim, qaysi chat."""
    update = event.update
    inner = update.message or update.callback_query or update.edited_message
    user = getattr(inner, "from_user", None)
    chat = getattr(inner, "chat", None) or getattr(getattr(inner, "message", None), "chat", None)
    return (
        f"update_id={update.update_id} tur={type(inner).__name__} "
        f"user={getattr(user, 'id', None)} chat={getattr(chat, 'id', None)}"
    )


async def on_unhandled_error(event: ErrorEvent) -> bool:
    """Xatoni logga yozadi va nomzodga javob qaytaradi (jim qolmaydi)."""
    STATS.observe_error()
    logger.error(
        "❗️ Update qayta ishlanmadi: %s — %s: %s",
        _describe(event),
        type(event.exception).__name__,
        event.exception,
        exc_info=event.exception,
    )

    update = event.update
    bot = update.bot
    try:
        if isinstance(update.callback_query, CallbackQuery):
            callback = update.callback_query
            # Tugma ustidagi "soat" belgisi abadiy aylanmasin
            try:
                await callback.answer()
            except TelegramAPIError:
                pass
            target = callback.message
            if target is None or isinstance(target, InaccessibleMessage):
                if callback.from_user is not None:
                    await bot.send_message(callback.from_user.id, USER_ERROR_MESSAGE)
                return True
            await target.answer(USER_ERROR_MESSAGE)
            return True

        message: Message | None = update.message or update.edited_message
        if message is not None:
            await message.answer(USER_ERROR_MESSAGE)
    except TelegramAPIError as exc:  # pragma: no cover - Telegramning o'zi ishlamasa
        logger.warning("Xato xabarini yuborib bo'lmadi: %s", exc)
    return True


def register_error_handler(dp: Dispatcher) -> None:
    """Global xato handlerini ulaydi (ishlash muhitida `app.main` chaqiradi)."""
    dp.errors.register(on_unhandled_error)


__all__ = ["USER_ERROR_MESSAGE", "on_unhandled_error", "register_error_handler"]
