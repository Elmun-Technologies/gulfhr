"""app.bot.handlers.candidates — ariza oqimi bo'yicha testlar (soxta bot bilan)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select

from app.bot.handlers import candidates as ch
from app.candidates import texts
from app.config import get_settings
from app.db.models import Application
from app.db.session import session_scope

GROUP_ID = -1001234567890


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple] = []

    async def send_message(self, chat_id, text, **kwargs) -> None:
        self.sent.append(("send_message", chat_id, text))

    async def send_voice(self, chat_id, file_id, **kwargs) -> None:
        self.sent.append(("send_voice", chat_id, file_id))

    async def send_audio(self, chat_id, file_id, **kwargs) -> None:
        self.sent.append(("send_audio", chat_id, file_id))

    async def send_document(self, chat_id, file_id, **kwargs) -> None:
        self.sent.append(("send_document", chat_id, file_id))


class FakeUser:
    id = 777
    username = "vali"


class FakeMessage:
    def __init__(self, bot: FakeBot, text: str | None = None, **extra) -> None:
        self.bot = bot
        self.text = text
        self.contact = extra.get("contact")
        self.voice = extra.get("voice")
        self.document = extra.get("document")
        self.audio = extra.get("audio")
        self.chat = SimpleNamespace(id=1)
        self.from_user = FakeUser()
        self.answered: list[tuple] = []
        self.edited: list = []

    async def answer(self, text, **kwargs) -> None:
        self.answered.append((text, kwargs))

    async def edit_reply_markup(self, **kwargs) -> None:
        self.edited.append(kwargs)


class FakeCallback:
    def __init__(self, data: str, message: FakeMessage) -> None:
        self.data = data
        self.message = message
        self.answers: list = []

    async def answer(self, **kwargs) -> None:
        self.answers.append(kwargs)


def make_state() -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=1, user_id=1),
    )


@pytest.fixture(autouse=True)
def _candidate_group(monkeypatch):
    monkeypatch.setenv("CANDIDATES_CHAT_ID", str(GROUP_ID))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------- #
# Telefon normalizatsiyasi
# ---------------------------------------------------------------------- #


def test_normalize_phone_plain() -> None:
    assert ch._normalize_phone("901234567") == "+998901234567"


def test_normalize_phone_full() -> None:
    assert ch._normalize_phone("+998901234567") == "+998901234567"


def test_normalize_phone_strips_spaces() -> None:
    assert ch._normalize_phone("+998 90 123-45-67") == "+998901234567"


def test_normalize_phone_rejects_short() -> None:
    assert ch._normalize_phone("12345") is None


def test_normalize_phone_rejects_garbage() -> None:
    assert ch._normalize_phone("abc") is None


# ---------------------------------------------------------------------- #
# Oqim: /start → natija
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_start_candidate_application_sets_first_state() -> None:
    bot = FakeBot()
    msg = FakeMessage(bot)
    state = make_state()
    await state.set_state(ch.ApplicationStates.age)  # oldin boshqa holatda

    await ch.start_candidate_application(msg, state)

    assert (await state.get_state()) == "ApplicationStates:full_name"
    assert msg.answered[0][0] == texts.WELCOME
    assert "Ish grafigi" not in texts.WELCOME
    assert msg.answered[1][0] == texts.ASK_FULL_NAME


@pytest.mark.asyncio
async def test_full_qualified_flow_with_voice_resume() -> None:
    bot = FakeBot()
    state = make_state()

    # 1. Ism
    await ch.on_full_name(FakeMessage(bot, "Vali Karimov"), state)
    assert (await state.get_state()) == "ApplicationStates:gender"

    # 2. Jins (tugma orqali)
    gender_msg = FakeMessage(bot)
    await ch.on_gender(FakeCallback("cand_gender:male", gender_msg), state)
    assert (await state.get_state()) == "ApplicationStates:age"
    assert gender_msg.answered[0][0] == texts.ASK_AGE

    # 3. Yosh
    await ch.on_age(FakeMessage(bot, "22"), state)
    assert (await state.get_state()) == "ApplicationStates:city"

    # 4. Shahar
    city_msg = FakeMessage(bot)
    await ch.on_city(FakeCallback("cand_yes", city_msg), state)
    assert (await state.get_state()) == "ApplicationStates:phone"
    assert "Telefon" in city_msg.answered[0][0]

    # 5. Telefon
    await ch.on_phone_text(FakeMessage(bot, "+998901234567"), state)
    assert (await state.get_state()) == "ApplicationStates:experience"

    # 6. Staj
    await ch.on_experience(FakeMessage(bot, "2 yil sotuvchi"), state)
    assert (await state.get_state()) == "ApplicationStates:resume"

    # 7. Rezume — golos
    voice_msg = FakeMessage(bot, voice=SimpleNamespace(file_id="voice_123"))
    await ch.on_resume_voice(voice_msg, state)

    # Natija: mos keldi
    assert (await state.get_state()) is None  # oqim tozalandi
    result_text = voice_msg.answered[0][0]
    assert "mos" in result_text.lower() or "Rahmat" in result_text
    assert texts.RESULT_QUALIFIED.format(name="Vali Karimov") == result_text

    # Baza
    async with session_scope() as session:
        rows = (await session.execute(select(Application))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.full_name == "Vali Karimov"
    assert row.gender == "male"
    assert row.age == 22
    assert row.lives_in_city is True
    assert row.phone == "+998901234567"
    assert row.experience == "2 yil sotuvchi"
    assert row.resume_file_kind == "voice"
    assert row.resume_file_id == "voice_123"
    assert row.is_qualified is True

    # HR guruhiga karta + golos
    group_msgs = [s for s in bot.sent if s[0] == "send_message"]
    assert len(group_msgs) == 1
    assert group_msgs[0][1] == GROUP_ID
    assert "🟢" in group_msgs[0][2]
    assert "Vali Karimov" in group_msgs[0][2]
    assert ("send_voice", GROUP_ID, "voice_123") in bot.sent


@pytest.mark.asyncio
async def test_rejected_flow_age_and_city() -> None:
    bot = FakeBot()
    state = make_state()

    await ch.on_full_name(FakeMessage(bot, "Bobo Akbar"), state)
    await ch.on_gender(FakeCallback("cand_gender:female", FakeMessage(bot)), state)
    await ch.on_age(FakeMessage(bot, "35"), state)
    await ch.on_city(FakeCallback("cand_no", FakeMessage(bot)), state)
    await ch.on_phone_contact(
        FakeMessage(bot, contact=SimpleNamespace(phone_number="+998901234567")), state
    )
    await ch.on_experience(FakeMessage(bot, "3 oy dastavka"), state)

    # Rezume — skip tugmasi
    skip_msg = FakeMessage(bot)
    await ch.on_resume_skip(FakeCallback("cand_skip_resume", skip_msg), state)

    result_text = skip_msg.answered[0][0]
    assert result_text == texts.RESULT_NOT_QUALIFIED.format(
        name="Bobo Akbar",
        reasons="\n".join(
            [
                "• Yosh chegarasi: 18-30 (siz: 35)",
                "• Doimiy Toshkentda istiqomat qilish talab etiladi (yotoqxona yo'q)",
            ]
        ),
    )

    async with session_scope() as session:
        rows = (await session.execute(select(Application))).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_qualified is False
    assert set(rows[0].reject_codes.split(",")) == {"age", "city"}
    assert rows[0].gender == "female"
    assert rows[0].resume_file_kind is None

    group_msgs = [s for s in bot.sent if s[0] == "send_message"]
    assert "🔴" in group_msgs[0][2]


@pytest.mark.asyncio
async def test_age_validation_rejects_non_numeric_and_out_of_range() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.age)

    for bad in ("yigirma", "", "9", "81"):
        msg = FakeMessage(bot, bad)
        await ch.on_age(msg, state)
        assert (await state.get_state()) == "ApplicationStates:age"
        assert msg.answered[0][0] == texts.ASK_AGE_INVALID


@pytest.mark.asyncio
async def test_short_name_is_asked_again() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.full_name)
    msg = FakeMessage(bot, "Va")
    await ch.on_full_name(msg, state)
    assert (await state.get_state()) == "ApplicationStates:full_name"
    assert msg.answered[0][0] == texts.ASK_FULL_NAME


@pytest.mark.asyncio
async def test_invalid_phone_is_asked_again() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.phone)
    msg = FakeMessage(bot, "12345")
    await ch.on_phone_text(msg, state)
    assert (await state.get_state()) == "ApplicationStates:phone"
    assert msg.answered[0][0] == texts.ASK_PHONE_INVALID


@pytest.mark.asyncio
async def test_resume_document_is_forwarded_to_group() -> None:
    bot = FakeBot()
    state = make_state()
    # Oqimni tezlashtirish uchun to'g'ridan-to'g'ri resume holatiga o'tamiz
    await state.update_data(
        full_name="Samarah Aliyeva",
        gender="female",
        age=25,
        lives_in_city=True,
        phone="+998901234567",
        experience="tajribam yo'q",
    )
    await state.set_state(ch.ApplicationStates.resume)

    doc_msg = FakeMessage(
        bot, document=SimpleNamespace(file_id="doc_9", file_name="resume.pdf")
    )
    await ch.on_resume_document(doc_msg, state)

    async with session_scope() as session:
        rows = (await session.execute(select(Application))).scalars().all()
    assert rows[0].resume_info == "📄 Fayl: resume.pdf"
    assert rows[0].resume_file_kind == "document"
    assert ("send_document", GROUP_ID, "doc_9") in bot.sent


@pytest.mark.asyncio
async def test_cancel_clears_candidate_state() -> None:
    bot = FakeBot()
    state = make_state()
    await state.set_state(ch.ApplicationStates.age)
    msg = FakeMessage(bot, "/cancel")
    await ch.cmd_cancel(msg, state)
    assert (await state.get_state()) is None
    assert msg.answered[0][0] == texts.CANCELLED


@pytest.mark.asyncio
async def test_cancel_outside_flow_skips() -> None:
    from aiogram.dispatcher.event.bases import SkipHandler

    bot = FakeBot()
    state = make_state()  # holat yo'q
    with pytest.raises(SkipHandler):
        await ch.cmd_cancel(FakeMessage(bot, "/cancel"), state)


@pytest.mark.asyncio
async def test_stats_outside_group_is_refused() -> None:
    bot = FakeBot()
    msg = FakeMessage(bot, "/stats")
    msg.chat = SimpleNamespace(id=42)  # HR guruhida emas
    await ch.cmd_stats(msg)
    assert msg.answered[0][0] == texts.STATS_GROUP_ONLY


@pytest.mark.asyncio
async def test_stats_inside_group_returns_report() -> None:
    bot = FakeBot()
    msg = FakeMessage(bot, "/stats")
    msg.chat = SimpleNamespace(id=GROUP_ID)
    await ch.cmd_stats(msg)
    assert msg.answered[0][0].startswith("📊")
