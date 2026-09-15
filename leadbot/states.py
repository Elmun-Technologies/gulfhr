"""Ariza suhbati uchun FSM holatlari."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Application(StatesGroup):
    full_name = State()
    gender = State()
    age = State()
    city = State()
    phone = State()
    experience = State()
