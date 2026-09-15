"""Telegram klaviaturalari."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.db.base import MetricType, Role, TargetPeriod
from app.db.models import Employee

BTN_MY_STATUS = "📊 Mening natijam"
BTN_MY_ALERTS = "⚠️ Ogohlantirishlar"
BTN_NOTIFICATIONS = "🔔 Bildirishnomalar"
BTN_TEAM_OVERVIEW = "👥 Jamoa holati"
BTN_ADD_EMPLOYEE = "➕ Xodim qo'shish"
BTN_SET_TARGET = "🎯 Target belgilash"
BTN_EMPLOYEES_LIST = "📋 Xodimlar ro'yxati"
BTN_SYNC_NOW = "🔄 Sinxronlash"
BTN_CANCEL = "❌ Bekor qilish"


def main_menu(employee: Employee) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text=BTN_MY_STATUS), KeyboardButton(text=BTN_MY_ALERTS)],
        [KeyboardButton(text=BTN_NOTIFICATIONS)],
    ]
    if employee.role.is_manager:
        rows.append([KeyboardButton(text=BTN_TEAM_OVERVIEW), KeyboardButton(text=BTN_EMPLOYEES_LIST)])
        rows.append([KeyboardButton(text=BTN_ADD_EMPLOYEE), KeyboardButton(text=BTN_SET_TARGET)])
    if employee.role == Role.ADMIN:
        rows.append([KeyboardButton(text=BTN_SYNC_NOW)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True
    )


def role_choice_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=role.label_uz, callback_data=f"role:{role.value}")]
        for role in Role
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def employees_choice_keyboard(employees: list[Employee], prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=emp.full_name, callback_data=f"{prefix}:{emp.id}")]
        for emp in employees
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def metric_choice_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=metric.label_uz, callback_data=f"metric:{metric.value}")]
        for metric in MetricType
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def period_choice_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=period.label_uz, callback_data=f"period:{period.value}")]
        for period in TargetPeriod
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def notifications_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    text = "🔕 O'chirish" if enabled else "🔔 Yoqish"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="toggle_notifications")]]
    )
