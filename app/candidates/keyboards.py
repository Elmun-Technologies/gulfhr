"""Nomzod arizasi suhbati uchun klaviaturalar.

Eslatma: callback_data larda `cand_` prefikisi ishlatiladi — asosiy ilovaning
xodimlar uchun klaviaturalari (role:, metric:, period: ...) bilan to'qnashmasligi
uchun.
"""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.candidates.texts import (
    BTN_FEMALE,
    BTN_MALE,
    BTN_NO,
    BTN_SHARE_CONTACT,
    BTN_SKIP_RESUME,
    BTN_YES,
)

YES_NO_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=BTN_YES, callback_data="cand_yes"),
            InlineKeyboardButton(text=BTN_NO, callback_data="cand_no"),
        ]
    ]
)

GENDER_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=BTN_MALE, callback_data="cand_gender:male"),
            InlineKeyboardButton(text=BTN_FEMALE, callback_data="cand_gender:female"),
        ]
    ]
)

RESUME_SKIP_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=BTN_SKIP_RESUME, callback_data="cand_skip_resume")],
    ]
)

CONTACT_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_SHARE_CONTACT, request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

REMOVE_KB = ReplyKeyboardRemove()
