"""Nomzod arizasi suhbati uchun FSM holatlari."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ApplicationStates(StatesGroup):
    full_name = State()
    gender = State()
    age = State()
    city = State()
    phone = State()
    experience = State()
    resume = State()
