"""Reply/inline klaviaturalar."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from leadbot.texts import BTN_FEMALE, BTN_MALE, BTN_NO, BTN_SHARE_CONTACT, BTN_SKIP_RESUME, BTN_YES

YES_NO_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=BTN_YES, callback_data="yes"),
            InlineKeyboardButton(text=BTN_NO, callback_data="no"),
        ]
    ]
)

GENDER_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=BTN_MALE, callback_data="gender:male"),
            InlineKeyboardButton(text=BTN_FEMALE, callback_data="gender:female"),
        ]
    ]
)

RESUME_SKIP_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=BTN_SKIP_RESUME, callback_data="skip_resume")],
    ]
)

CONTACT_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_SHARE_CONTACT, request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

REMOVE_KB = ReplyKeyboardRemove()
