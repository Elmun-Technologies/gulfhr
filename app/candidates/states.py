"""Nomzod arizasi suhbati uchun FSM holatlari."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ApplicationStates(StatesGroup):
    # 0. Til tanlash — /start dan keyingi birinchi qadam
    language = State()
    full_name = State()
    gender = State()
    age = State()
    city = State()
    russian = State()
    phone = State()
    experience = State()
    resume = State()
