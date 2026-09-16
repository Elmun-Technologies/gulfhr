"""Suhbat hech bir bosqichda to'xtab qolmasligi ("davom etmayapti" muammosi).

Uch xil holat tekshiriladi:
1. Nomzod tugma o'rniga YOZIB yuborsa (erkak / ha / да) — oqim davom etadi.
2. Nomzod kutilmagan narsa yuborsa (rasm, stiker) — savol qayta so'raladi,
   bot jim qolmaydi.
3. Telegram xatosi (tugma allaqachon bosilgan, callback eskirgan, xabar
   o'chirilgan) — oqim baribir keyingi savolga o'tadi.
"""

from __future__ import annotations

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Chat, InaccessibleMessage

from app.bot.handlers import candidates as ch
from app.candidates.texts import RUSSIAN, UZBEK
from tests.test_candidates_handlers import FakeBot, FakeMessage, make_state


class TrackingMessage:
    """answer/edit tartibini yozib boruvchi soxta xabar."""

    def __init__(self, bot, log: list[str], *, fail_edit: Exception | None = None) -> None:
        self.bot = bot
        self.chat = type("C", (), {"id": 1})()
        self.from_user = type("U", (), {"id": 7, "username": "vali"})()
        self._log = log
        self._fail_edit = fail_edit
        self.texts: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self._log.append("answer")
        self.texts.append(text)

    async def edit_reply_markup(self, **kwargs) -> None:
        self._log.append("edit")
        if self._fail_edit is not None:
            raise self._fail_edit


class TrackingCallback:
    def __init__(self, data: str, message, log: list[str], *, fail_answer: bool = False) -> None:
        self.data = data
        self.message = message
        self.bot = message.bot
        self.from_user = message.from_user
        self._log = log
        self._fail_answer = fail_answer

    async def answer(self, **kwargs) -> None:
        self._log.append("callback_answer")
        if self._fail_answer:
            raise TelegramBadRequest(method=None, message="Query is too old and response timeout expired")


# ---------------------------------------------------------------------- #
# 1. Tugma o'rniga yozib yuborish
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_gender_typed_as_text_continues_flow() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.gender)

    msg = FakeMessage(bot, "erkak")
    await ch.on_gender_text(msg, state)

    assert (await state.get_state()) == "ApplicationStates:age"
    assert (await state.get_data())["gender"] == "male"
    assert msg.answered[0][0] == UZBEK.ask_age


@pytest.mark.asyncio
async def test_city_typed_as_text_continues_flow() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.city)

    msg = FakeMessage(bot, "ha")
    await ch.on_city_text(msg, state)

    assert (await state.get_state()) == "ApplicationStates:russian"
    assert (await state.get_data())["lives_in_city"] is True
    # Keyingi savol — rus tili (til tanlash emas!)
    assert msg.answered[0][0] == UZBEK.ask_russian


@pytest.mark.asyncio
async def test_russian_answered_in_russian_text_continues_flow() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.russian)
    await state.update_data(lang="ru")

    msg = FakeMessage(bot, "да")
    await ch.on_russian_text(msg, state)

    assert (await state.get_state()) == "ApplicationStates:phone"
    assert (await state.get_data())["knows_russian"] is True
    assert msg.answered[0][0] == RUSSIAN.ask_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("✅ Ha", True),
        ("Ha", True),
        ("да", True),
        ("yes", True),
        ("❌ Yo'q", False),
        ("yoq", False),
        ("нет", False),
        ("no", False),
        ("bilmadim", None),
        ("", None),
    ],
)
def test_parse_yes_no(raw: str, expected: bool | None) -> None:
    assert ch._parse_yes_no(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("👨 Erkak", "male"),
        ("erkak", "male"),
        ("мужской", "male"),
        ("👩 Ayol", "female"),
        ("женский", "female"),
        ("nima", None),
    ],
)
def test_parse_gender(raw: str, expected: str | None) -> None:
    assert ch._parse_gender(raw) == expected


# ---------------------------------------------------------------------- #
# 2. Kutilmagan xabar — savol qayta so'raladi
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state_name", "expected_fragment"),
    [
        ("ApplicationStates:language", "Tilni tanlang"),
        ("ApplicationStates:full_name", UZBEK.ask_full_name),
        ("ApplicationStates:gender", UZBEK.ask_gender),
        ("ApplicationStates:age", UZBEK.ask_age),
        ("ApplicationStates:city", "Doimiy Toshkentda"),
        ("ApplicationStates:russian", UZBEK.ask_russian),
        ("ApplicationStates:phone", UZBEK.ask_phone),
        ("ApplicationStates:experience", UZBEK.ask_experience),
        ("ApplicationStates:resume", UZBEK.ask_resume),
    ],
)
async def test_every_state_reasks_when_confused(
    state_name: str, expected_fragment: str
) -> None:
    """Har bir bosqichda bot javob beradi — hech qachon jim qolmaydi."""
    bot = FakeBot()
    state = make_state()
    await state.set_state(state_name)

    msg = FakeMessage(bot, "🤷 nima deyishni bilmadim")
    await ch.on_unexpected(msg, state)

    assert len(msg.answered) == 1, "bot jim qoldi"
    assert expected_fragment in msg.answered[0][0]
    assert (await state.get_state()) == state_name


@pytest.mark.asyncio
async def test_reask_returns_keyboard_for_button_steps() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.city)

    msg = FakeMessage(bot, "rasm yubordi")
    await ch.on_unexpected(msg, state)

    markup = msg.answered[0][1]["reply_markup"]
    assert [b.callback_data for row in markup.inline_keyboard for b in row] == [
        "cand_yes",
        "cand_no",
    ]


# ---------------------------------------------------------------------- #
# 3. Telegram xatolariga bardoshlilik
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_flow_continues_when_keyboard_edit_fails() -> None:
    """Tugma ikki marta bosilsa Telegram 'message is not modified' qaytaradi."""
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.city)

    log: list[str] = []
    message = TrackingMessage(bot, log, fail_edit=TelegramBadRequest(method=None, message="message is not modified"))
    await ch.on_city(TrackingCallback("cand_yes", message, log), state)

    assert (await state.get_state()) == "ApplicationStates:russian"
    assert message.texts[0] == UZBEK.ask_russian


@pytest.mark.asyncio
async def test_flow_continues_when_callback_answer_fails() -> None:
    """Callback eskirgan bo'lsa ham keyingi savol yuboriladi."""
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.russian)

    log: list[str] = []
    message = TrackingMessage(bot, log)
    await ch.on_russian(
        TrackingCallback("cand_yes", message, log, fail_answer=True), state
    )

    assert (await state.get_state()) == "ApplicationStates:phone"
    assert message.texts[0] == UZBEK.ask_phone


@pytest.mark.asyncio
async def test_callback_spinner_is_removed_before_next_question() -> None:
    """Tugma 'soat'i keyingi savoldan OLDIN o'chiriladi (tezlik hissi)."""
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.city)

    log: list[str] = []
    message = TrackingMessage(bot, log)
    await ch.on_city(TrackingCallback("cand_yes", message, log), state)

    assert log[0] == "callback_answer"
    assert log[1] == "edit"
    assert log[2] == "answer"


@pytest.mark.asyncio
async def test_flow_continues_when_callback_message_is_inaccessible() -> None:
    """Xabar o'chirilgan/48 soatdan eski bo'lsa ham savol yangi xabar bilan boradi."""
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.city)

    inaccessible = InaccessibleMessage(
        chat=Chat(id=99, type="private"), message_id=123
    ).as_(bot)

    class Callback:
        data = "cand_yes"
        message = inaccessible
        from_user = type("U", (), {"id": 99, "username": None})()

        async def answer(self, **kwargs) -> None:
            return None

    await ch.on_city(Callback(), state)

    assert (await state.get_state()) == "ApplicationStates:russian"
    # Soxta botga yuborilgan xabarlar orasida keyingi savol bor
    assert any(s[0] == "send_message" and s[1] == 99 for s in bot.sent)


@pytest.mark.asyncio
async def test_phone_keyboard_is_removed_after_phone() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.phone)

    msg = FakeMessage(bot, "+998901234567")
    await ch.on_phone_text(msg, state)

    assert (await state.get_state()) == "ApplicationStates:experience"
    assert "reply_markup" in msg.answered[0][1]


@pytest.mark.asyncio
async def test_experience_over_limit_is_rejected() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.experience)

    msg = FakeMessage(bot, "x" * 501)
    await ch.on_experience(msg, state)

    assert (await state.get_state()) == "ApplicationStates:experience"
    assert msg.answered[0][0] == UZBEK.ask_experience


@pytest.mark.asyncio
async def test_name_over_limit_is_rejected() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.full_name)

    msg = FakeMessage(bot, "x" * 81)
    await ch.on_full_name(msg, state)

    assert (await state.get_state()) == "ApplicationStates:full_name"
    assert msg.answered[0][0] == UZBEK.ask_full_name_invalid


def test_prompt_for_covers_all_states() -> None:
    """Har bir FSM holati uchun takroriy savol mavjud."""
    for state in ch.ApplicationStates.__all_states__:
        assert ch._prompt_for(state.state, UZBEK) is not None, state.state
