"""Nomzod arizasi suhbati uchun klaviaturalar.

Eslatma: callback_data larda `cand_` prefikisi ishlatiladi — asosiy ilovaning
xodimlar uchun klaviaturalari (role:, metric:, period: ...) bilan to'qnashmasligi
uchun. Tugma matnlari tanlangan tilga bog'liq, shuning uchun ular funksiya
orqali (`yes_no_kb(t)`) yig'iladi.
"""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.candidates.texts import RU, UZ, Lang

REMOVE_KB = ReplyKeyboardRemove()

# Til tanlash — birinchi qadam. Callback data: lang:uz / lang:ru
LANG_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data=f"lang:{UZ}")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"lang:{RU}")],
    ]
)


def yes_no_kb(t: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t.btn_yes, callback_data="cand_yes"),
                InlineKeyboardButton(text=t.btn_no, callback_data="cand_no"),
            ]
        ]
    )


def gender_kb(t: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t.btn_male, callback_data="cand_gender:male"),
                InlineKeyboardButton(text=t.btn_female, callback_data="cand_gender:female"),
            ]
        ]
    )


def resume_skip_kb(t: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t.btn_skip_resume, callback_data="cand_skip_resume")],
        ]
    )


def contact_kb(t: Lang) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t.btn_share_contact, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
