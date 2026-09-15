"""FSM holatlari."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddEmployeeStates(StatesGroup):
    waiting_name = State()
    waiting_role = State()
    waiting_amo_link = State()


class SetTargetStates(StatesGroup):
    waiting_employee = State()
    waiting_metric = State()
    waiting_period = State()
    waiting_value = State()
