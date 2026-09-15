"""Bo'lim boshlig'i / HR uchun: jamoa holati, xodim qo'shish, target belgilash."""

from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    BTN_ADD_EMPLOYEE,
    BTN_CANCEL,
    BTN_EMPLOYEES_LIST,
    BTN_SET_TARGET,
    BTN_TEAM_OVERVIEW,
    cancel_keyboard,
    employees_choice_keyboard,
    main_menu,
    metric_choice_keyboard,
    period_choice_keyboard,
    role_choice_keyboard,
)
from app.bot.states import AddEmployeeStates, SetTargetStates
from app.db.base import MetricType, Role, TargetPeriod
from app.db.models import Employee, Target
from app.services.employees import create_invite, list_active_employees, list_unlinked_amo_users
from app.services.reports import build_team_overview
from app.services.targets import current_month_range, current_week_range

router = Router(name="manager")


def _require_manager(employee: Employee | None) -> bool:
    return employee is not None and employee.role.is_manager


# ---------------------------------------------------------------------- #
# Jamoa holati va ro'yxat
# ---------------------------------------------------------------------- #

@router.message(F.text == BTN_TEAM_OVERVIEW)
@router.message(Command("team"))
async def team_overview(message: Message, session: AsyncSession, employee: Employee | None) -> None:
    if not _require_manager(employee):
        await message.answer("Bu bo'lim faqat rahbariyat uchun.")
        return
    text = await build_team_overview(session)
    await message.answer(text, disable_web_page_preview=True)


@router.message(F.text == BTN_EMPLOYEES_LIST)
async def employees_list(message: Message, session: AsyncSession, employee: Employee | None) -> None:
    if not _require_manager(employee):
        await message.answer("Bu bo'lim faqat rahbariyat uchun.")
        return
    employees = await list_active_employees(session)
    if not employees:
        await message.answer("Hozircha xodimlar ro'yxatga olinmagan.")
        return
    lines = ["📋 <b>Xodimlar:</b>", ""]
    for emp in employees:
        status = "🟢 ulangan" if emp.telegram_id else f"⏳ kod: <code>{emp.invite_code}</code>"
        amo_status = f"amo_id:{emp.amo_user_id}" if emp.amo_user_id else "amo bog'lanmagan"
        lines.append(f"• {emp.full_name} — {emp.role.label_uz} — {status} — {amo_status}")
    await message.answer("\n".join(lines))


# ---------------------------------------------------------------------- #
# Xodim qo'shish (FSM)
# ---------------------------------------------------------------------- #

@router.message(F.text == BTN_ADD_EMPLOYEE)
@router.message(Command("addemployee"))
async def add_employee_start(message: Message, state: FSMContext, employee: Employee | None) -> None:
    if not _require_manager(employee):
        await message.answer("Bu bo'lim faqat rahbariyat uchun.")
        return
    await state.set_state(AddEmployeeStates.waiting_name)
    await message.answer(
        "Yangi xodimning to'liq ismini kiriting:", reply_markup=cancel_keyboard()
    )


@router.message(StateFilter(AddEmployeeStates.waiting_name), F.text == BTN_CANCEL)
@router.message(StateFilter(AddEmployeeStates.waiting_role), F.text == BTN_CANCEL)
async def add_employee_cancel(message: Message, state: FSMContext, employee: Employee) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu(employee))


@router.message(StateFilter(AddEmployeeStates.waiting_name))
async def add_employee_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Iltimos, ism-familiyani matn ko'rinishida yuboring.")
        return
    await state.update_data(full_name=name)
    await state.set_state(AddEmployeeStates.waiting_role)
    await message.answer("Rolini tanlang:", reply_markup=role_choice_keyboard())


@router.callback_query(StateFilter(AddEmployeeStates.waiting_role), F.data.startswith("role:"))
async def add_employee_role(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, employee: Employee
) -> None:
    if not callback.data or not callback.message:
        return
    role_value = callback.data.split(":", 1)[1]
    role = Role(role_value)
    data = await state.get_data()
    full_name = data["full_name"]

    invited = await create_invite(session, full_name=full_name, role=role)
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>{full_name}</b> ({role.label_uz}) uchun taklif yaratildi.\n\n"
        f"Ushbu kodni xodimga yuboring:\n<code>/start {invited.invite_code}</code>\n\n"
        "Xodim botga shu buyruq bilan kirgach, ro'yxatdan avtomatik o'tadi.\n"
        "amoCRM akkountini bog'lash uchun keyinroq /linkamo dan foydalanishingiz mumkin."
    )
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu(employee))
    await callback.answer()


# ---------------------------------------------------------------------- #
# amoCRM foydalanuvchisini xodimga bog'lash
# ---------------------------------------------------------------------- #

@router.message(Command("linkamo"))
async def link_amo_start(message: Message, session: AsyncSession, employee: Employee | None) -> None:
    if not _require_manager(employee):
        await message.answer("Bu bo'lim faqat rahbariyat uchun.")
        return
    employees = [e for e in await list_active_employees(session) if e.amo_user_id is None]
    if not employees:
        await message.answer("Barcha faol xodimlar allaqachon amoCRM bilan bog'langan.")
        return
    await message.answer(
        "Qaysi xodimni amoCRM foydalanuvchisi bilan bog'laymiz?",
        reply_markup=employees_choice_keyboard(employees, "linkamo_emp"),
    )


@router.callback_query(F.data.startswith("linkamo_emp:"))
async def link_amo_pick_employee(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    if not callback.data or not callback.message:
        return
    employee_id = int(callback.data.split(":", 1)[1])
    amo_users = await list_unlinked_amo_users(session)
    if not amo_users:
        await callback.message.edit_text(
            "Bog'lanmagan amoCRM foydalanuvchilari topilmadi. Avval /sync ni bajarib ko'ring."
        )
        await callback.answer()
        return
    rows_text = "\n".join(f"• <code>{u.id}</code> — {u.name}" for u in amo_users[:20])
    await callback.message.edit_text(
        "amoCRM foydalanuvchi ID sini yuboring:\n\n" + rows_text
    )
    await callback.answer()
    # Keyingi matn xabarini kutish uchun holatni saqlaymiz — soddalik uchun reply orqali:
    await callback.message.answer(
        f"Endi shu buyruqni yuboring:\n<code>/setamoid {employee_id} AMO_ID</code>"
    )


@router.message(Command("setamoid"))
async def set_amo_id(message: Message, session: AsyncSession, employee: Employee | None) -> None:
    if not _require_manager(employee):
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Foydalanish: /setamoid EMPLOYEE_ID AMO_USER_ID")
        return
    try:
        emp_id, amo_id = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("ID'lar butun son bo'lishi kerak.")
        return
    target_employee = await session.get(Employee, emp_id)
    if not target_employee:
        await message.answer("Bunday xodim topilmadi.")
        return
    target_employee.amo_user_id = amo_id
    await message.answer(f"✅ {target_employee.full_name} amoCRM ID={amo_id} bilan bog'landi.")


# ---------------------------------------------------------------------- #
# Target belgilash (FSM)
# ---------------------------------------------------------------------- #

@router.message(F.text == BTN_SET_TARGET)
@router.message(Command("settarget"))
async def set_target_start(
    message: Message, state: FSMContext, session: AsyncSession, employee: Employee | None
) -> None:
    if not _require_manager(employee):
        await message.answer("Bu bo'lim faqat rahbariyat uchun.")
        return
    employees = await list_active_employees(session, role=Role.SALES)
    if not employees:
        await message.answer("Hozircha sotuvchilar ro'yxatga olinmagan.")
        return
    await state.set_state(SetTargetStates.waiting_employee)
    await message.answer(
        "Kimga target belgilaymiz?", reply_markup=employees_choice_keyboard(employees, "target_emp")
    )


@router.callback_query(StateFilter(SetTargetStates.waiting_employee), F.data.startswith("target_emp:"))
async def set_target_employee(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    emp_id = int(callback.data.split(":", 1)[1])
    await state.update_data(employee_id=emp_id)
    await state.set_state(SetTargetStates.waiting_metric)
    await callback.message.edit_text("Qaysi ko'rsatkich bo'yicha?")
    await callback.message.answer("Tanlang:", reply_markup=metric_choice_keyboard())
    await callback.answer()


@router.callback_query(StateFilter(SetTargetStates.waiting_metric), F.data.startswith("metric:"))
async def set_target_metric(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    metric = MetricType(callback.data.split(":", 1)[1])
    await state.update_data(metric=metric.value)
    await state.set_state(SetTargetStates.waiting_period)
    await callback.message.edit_text(f"Ko'rsatkich: {metric.label_uz}")
    await callback.message.answer("Davrni tanlang:", reply_markup=period_choice_keyboard())
    await callback.answer()


@router.callback_query(StateFilter(SetTargetStates.waiting_period), F.data.startswith("period:"))
async def set_target_period(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    period = TargetPeriod(callback.data.split(":", 1)[1])
    await state.update_data(period=period.value)
    await state.set_state(SetTargetStates.waiting_value)
    data = await state.get_data()
    metric = MetricType(data["metric"])
    await callback.message.edit_text(
        f"Davr: {period.label_uz}\n\nEndi target qiymatini kiriting (masalan: 50000000 yoki 20).\n"
        f"O'lchov birligi: {metric.unit_uz}"
    )
    await callback.answer()


@router.message(StateFilter(SetTargetStates.waiting_value))
async def set_target_value(
    message: Message, state: FSMContext, session: AsyncSession, employee: Employee
) -> None:
    raw = (message.text or "").replace(" ", "").replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        await message.answer("Iltimos, faqat son kiriting. Masalan: 50000000")
        return

    data = await state.get_data()
    target_employee_id = int(data["employee_id"])
    metric = MetricType(data["metric"])
    period = TargetPeriod(data["period"])
    today = date.today()

    if period == TargetPeriod.WEEKLY:
        start, end = current_week_range(today)
    elif period == TargetPeriod.MONTHLY:
        start, end = current_month_range(today)
    else:
        start = end = today

    target_employee = await session.get(Employee, target_employee_id)
    if target_employee is None:
        await state.clear()
        await message.answer("Xodim topilmadi.", reply_markup=main_menu(employee))
        return

    existing_result = await session.execute(
        select(Target).where(
            Target.employee_id == target_employee_id,
            Target.metric == metric,
            Target.period_start == start,
            Target.period_end == end,
        )
    )
    existing_target = existing_result.scalar_one_or_none()
    if existing_target:
        existing_target.target_value = value
        existing_target.is_active = True
        existing_target.created_by_id = employee.id
    else:
        session.add(
            Target(
                employee_id=target_employee_id,
                metric=metric,
                period=period,
                period_start=start,
                period_end=end,
                target_value=value,
                created_by_id=employee.id,
            )
        )
    await state.clear()
    await message.answer(
        f"✅ Target belgilandi:\n"
        f"👤 {target_employee.full_name}\n"
        f"🎯 {metric.label_uz}: {value:g} {metric.unit_uz}\n"
        f"📅 {period.label_uz} ({start.strftime('%d.%m')} — {end.strftime('%d.%m.%Y')})",
        reply_markup=main_menu(employee),
    )
