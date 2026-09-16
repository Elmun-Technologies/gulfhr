"""Til tanlash (/start → 🇺🇿/🇷🇺) va suhbatning tanlangan tilda davom etishi."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.bot.handlers import candidates as ch
from app.candidates import texts
from app.candidates.texts import RUSSIAN, UZBEK, get_texts
from app.config import get_settings
from app.db.models import Application
from app.db.session import session_scope
from tests.test_candidates_handlers import (
    GROUP_ID,
    FakeBot,
    FakeCallback,
    FakeMessage,
    make_state,
)


async def _finish_flow(bot: FakeBot, state, *, name: str = "Vali Karimov") -> FakeMessage:
    """Til tanlanganidan keyingi butun oqimni bosib o'tadi."""
    await ch.on_full_name(FakeMessage(bot, name), state)
    await ch.on_gender(FakeCallback("cand_gender:male", FakeMessage(bot)), state)
    await ch.on_age(FakeMessage(bot, "22"), state)
    await ch.on_city(FakeCallback("cand_yes", FakeMessage(bot)), state)
    await ch.on_russian(FakeCallback("cand_yes", FakeMessage(bot)), state)
    await ch.on_phone_text(FakeMessage(bot, "+998901234567"), state)
    await ch.on_experience(FakeMessage(bot, "2 yil sotuv menejeri"), state)
    last = FakeMessage(bot)
    await ch.on_resume_skip(FakeCallback("cand_skip_resume", last), state)
    return last


@pytest.fixture(autouse=True)
def _candidate_group(monkeypatch):
    monkeypatch.setenv("CANDIDATES_CHAT_ID", str(GROUP_ID))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------- #
# Til tanlash qadami
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_language_button_switches_whole_flow_to_russian() -> None:
    bot = FakeBot()
    msg = FakeMessage(bot)
    state = make_state()

    await ch.start_candidate_application(msg, state)
    assert (await state.get_state()) == "ApplicationStates:language"

    await ch.on_language(FakeCallback("lang:ru", msg), state)

    assert (await state.get_state()) == "ApplicationStates:full_name"
    assert (await state.get_data())["lang"] == "ru"
    # Salomlashuv + birinchi savol bitta xabarda (ikkita API chaqiruvi o'rniga bitta)
    assert len(msg.answered) == 2  # 1) til tanlash, 2) salomlashuv+savol
    assert "Здравствуйте" in msg.answered[1][0]
    assert RUSSIAN.ask_full_name in msg.answered[1][0]


@pytest.mark.asyncio
async def test_uzbek_button_keeps_uzbek() -> None:
    bot = FakeBot()
    msg = FakeMessage(bot)
    state = make_state()

    await ch.start_candidate_application(msg, state)
    await ch.on_language(FakeCallback("lang:uz", msg), state)

    assert (await state.get_data())["lang"] == "uz"
    assert UZBEK.ask_full_name in msg.answered[1][0]


@pytest.mark.asyncio
async def test_language_can_be_typed_instead_of_button() -> None:
    bot = FakeBot()
    state = make_state()
    await ch.start_candidate_application(FakeMessage(bot), state)

    msg = FakeMessage(bot, "русский")
    await ch.on_language_text(msg, state)

    assert (await state.get_state()) == "ApplicationStates:full_name"
    assert (await state.get_data())["lang"] == "ru"


@pytest.mark.asyncio
async def test_unknown_language_code_reasks_chooser() -> None:
    bot = FakeBot()
    state = make_state()
    await ch.start_candidate_application(FakeMessage(bot), state)

    msg = FakeMessage(bot)
    await ch.on_language(FakeCallback("lang:de", msg), state)

    # Noma'lum til — tanlash oynasi qayta ko'rsatiladi, holat saqlanadi
    assert (await state.get_state()) == "ApplicationStates:language"
    assert msg.answered[-1][0] == texts.CHOOSE_LANGUAGE


@pytest.mark.asyncio
async def test_lang_command_restarts_language_choice() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.age)
    await state.update_data(lang="uz", age=22)

    msg = FakeMessage(bot, "/lang")
    await ch.cmd_lang(msg, state)

    assert (await state.get_state()) == "ApplicationStates:language"
    assert msg.answered[0][0] == texts.CHOOSE_LANGUAGE


# ---------------------------------------------------------------------- #
# Butun oqim tanlangan tilda
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_russian_flow_asks_and_answers_in_russian() -> None:
    bot = FakeBot()
    state = make_state()
    await state.update_data(lang="ru")

    name_msg = FakeMessage(bot, "Vali Karimov")
    await ch.on_full_name(name_msg, state)
    assert name_msg.answered[0][0] == RUSSIAN.ask_gender

    age_msg = FakeMessage(bot)
    await ch.on_gender(FakeCallback("cand_gender:male", age_msg), state)
    assert age_msg.answered[0][0] == RUSSIAN.ask_age

    city_msg = FakeMessage(bot, "22")
    await ch.on_age(city_msg, state)
    assert city_msg.answered[0][0] == RUSSIAN.ask_city.format(city="Toshkent")

    russian_msg = FakeMessage(bot)
    await ch.on_city(FakeCallback("cand_yes", russian_msg), state)
    assert russian_msg.answered[0][0] == RUSSIAN.ask_russian

    phone_msg = FakeMessage(bot)
    await ch.on_russian(FakeCallback("cand_yes", phone_msg), state)
    assert phone_msg.answered[0][0] == RUSSIAN.ask_phone

    exp_msg = FakeMessage(bot, "+998901234567")
    await ch.on_phone_text(exp_msg, state)
    assert exp_msg.answered[0][0] == RUSSIAN.ask_experience

    resume_msg = FakeMessage(bot, "2 yil sotuv menejeri")
    await ch.on_experience(resume_msg, state)
    assert resume_msg.answered[0][0] == RUSSIAN.ask_resume

    last = FakeMessage(bot)
    await ch.on_resume_skip(FakeCallback("cand_skip_resume", last), state)
    assert last.answered[0][0] == RUSSIAN.result_qualified.format(name="Vali Karimov")


@pytest.mark.asyncio
async def test_russian_rejection_reasons_are_translated() -> None:
    bot = FakeBot()
    state = make_state()
    await state.update_data(lang="ru")

    await ch.on_full_name(FakeMessage(bot, "Bobo Akbar"), state)
    await ch.on_gender(FakeCallback("cand_gender:male", FakeMessage(bot)), state)
    await ch.on_age(FakeMessage(bot, "35"), state)
    await ch.on_city(FakeCallback("cand_no", FakeMessage(bot)), state)
    await ch.on_russian(FakeCallback("cand_no", FakeMessage(bot)), state)
    await ch.on_phone_text(FakeMessage(bot, "+998901234567"), state)
    await ch.on_experience(FakeMessage(bot, "3 oy"), state)

    last = FakeMessage(bot)
    await ch.on_resume_skip(FakeCallback("cand_skip_resume", last), state)

    result = last.answered[0][0]
    assert "Возрастное ограничение: 18-30 (ваш возраст: 35)" in result
    assert "Требуется постоянное проживание в г. Toshkent" in result
    assert "Знание русского языка" in result
    # HR guruhiga ketadigan karta o'zbekcha qoladi
    group_card = [s for s in bot.sent if s[0] == "send_message"][0][2]
    assert "Yosh chegarasi: 18-30 (siz: 35)" in group_card
    assert "🌐 Suhbat tili: Rus" in group_card


@pytest.mark.asyncio
async def test_language_is_saved_with_application() -> None:
    bot = FakeBot()
    state = make_state()
    await state.update_data(lang="ru")

    await _finish_flow(bot, state)

    async with session_scope() as session:
        row = (await session.execute(select(Application))).scalars().one()
    assert row.language == "ru"


@pytest.mark.asyncio
async def test_language_defaults_to_uzbek_when_not_chosen() -> None:
    bot = FakeBot()
    state = make_state()

    await _finish_flow(bot, state, name="Ali Valiyev")

    async with session_scope() as session:
        row = (await session.execute(select(Application))).scalars().one()
    assert row.language == "uz"


@pytest.mark.asyncio
async def test_cancel_answered_in_chosen_language() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.age)
    await state.update_data(lang="ru")

    msg = FakeMessage(bot, "/cancel")
    await ch.cmd_cancel(msg, state)

    assert msg.answered[0][0] == RUSSIAN.cancelled
    assert (await state.get_state()) is None


# ---------------------------------------------------------------------- #
# Matn yordamchilari
# ---------------------------------------------------------------------- #


def test_get_texts_falls_back_to_uzbek() -> None:
    assert get_texts("uz") is UZBEK
    assert get_texts("ru") is RUSSIAN
    assert get_texts("RU") is RUSSIAN
    assert get_texts("de") is UZBEK
    assert get_texts(None) is UZBEK
    assert get_texts("") is UZBEK


def test_all_languages_have_every_text() -> None:
    """Biror tilda tarjimasi yo'q matn qolmasligi kerak."""
    missing = {
        field
        for field in UZBEK.__dataclass_fields__
        if not getattr(RUSSIAN, field, None)
    }
    assert not missing


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("o'zbekcha", "uz"),
        ("O'ZBEKCHA", "uz"),
        ("ruscha", "ru"),
        ("русский", "ru"),
        ("ru", "ru"),
        ("uz", "uz"),
        ("nemis", None),
        ("", None),
    ],
)
def test_parse_language(raw: str, expected: str | None) -> None:
    assert ch._parse_language(raw) == expected
