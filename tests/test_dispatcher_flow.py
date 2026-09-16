"""Haqiqiy Dispatcher orqali butun oqim — router ulanishini tekshirish.

Bu test handler'larni qo'lda chaqirmaydi: Telegram update'lari
`Dispatcher.feed_update` orqali haqiqiy router zanjiriga (start → candidates →
common) beriladi. Shunday qilib "biror bosqichda handler topilmadi → bot jim
qoldi" va "tugma bosilgach hech narsa bo'lmadi" kabi xatolar ushlanadi.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import GetMe, SendMessage
from aiogram.methods.base import TelegramMethod
from aiogram.types import (
    CallbackQuery,
    Chat,
    Message,
    PhotoSize,
    Update,
    User,
    WebhookInfo,
)
from sqlalchemy import select

from app.bot.setup import ROUTERS, build_dispatcher
from app.candidates.texts import RUSSIAN, UZBEK
from app.db.fsm_storage import SqliteStorage
from app.db.models import Application
from app.db.session import session_scope


def _free_routers() -> None:
    """Routerlarni oldingi dispatcher'dan ajratadi.

    Routerlar modul darajasida bitta — aiogram bir routerni ikkinchi marta
    biriktirishga ruxsat bermaydi. Ishlash muhitida dispatcher bitta, bu faqat
    testda bir nechta "bot qayta ishga tushishi"ni simulyatsiya qilish uchun.
    """
    for router in ROUTERS:
        router._parent_router = None

CHAT = Chat(id=42, type="private")
USER = User(id=42, is_bot=False, first_name="Vali", username="vali")


class MockedSession(BaseSession):
    """Telegram API'ni soxtalashtiradi — barcha chaqiruvlarni yozib boradi."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod] = []

    async def close(self) -> None:  # pragma: no cover
        return None

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(message_id=len(self.calls) + 1, date=datetime.now(UTC), chat=CHAT)
        if isinstance(method, GetMe):
            # /diag o'lchovlari uchun haqiqiy `User` kerak (True emas)
            return User(id=1, is_bot=True, first_name="Gulf HR", username="gulf_hr_bot")
        if method.__api_method__ == "getWebhookInfo":
            return WebhookInfo(url="")
        return True

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536,
                             raise_for_status=True) -> AsyncGenerator[bytes, None]:  # pragma: no cover
        if False:
            yield b""


class FlowDriver:
    """Nomzod nomidan bot bilan gaplashadi."""

    def __init__(self, storage=None, session: BaseSession | None = None) -> None:
        # `session` — kechikishni o'lchash uchun almashtiriladigan sessiya
        self.session = session or MockedSession()
        self.bot = Bot(token="123456:TEST", session=self.session)
        _free_routers()
        self.dp = build_dispatcher(storage)
        self.storage = storage
        self.errors: list[BaseException] = []
        self._update_id = 0
        self._callback_id = 0

        @self.dp.errors()
        async def _on_error(event) -> bool:  # noqa: ANN001
            self.errors.append(event.exception)
            return True

    async def close(self) -> None:
        """Storage'ni yopadi (aks holda aiosqlite oqimi pytest'ni kutib qoldiradi)."""
        if self.storage is not None:
            await self.storage.close()

    # -- yordamchilar ----------------------------------------------------- #

    def _next_update_id(self) -> int:
        self._update_id += 1
        return self._update_id

    @property
    def texts(self) -> list[str]:
        return [c.text for c in self.session.calls if isinstance(c, SendMessage)]

    @property
    def last_text(self) -> str:
        return self.texts[-1]

    @property
    def last_markup(self):
        return [c for c in self.session.calls if isinstance(c, SendMessage)][-1].reply_markup

    async def _feed(self, update: Update) -> list[TelegramMethod]:
        before = len(self.session.calls)
        await self.dp.feed_update(self.bot, update)
        assert not self.errors, f"handler xato tashladi: {self.errors}"
        return self.session.calls[before:]

    async def send(self, text: str) -> list[TelegramMethod]:
        message = Message(
            message_id=self._next_update_id(),
            date=datetime.now(UTC),
            chat=CHAT,
            from_user=USER,
            text=text,
        )
        return await self._feed(Update(update_id=self._next_update_id(), message=message))

    async def send_photo(self) -> list[TelegramMethod]:
        message = Message(
            message_id=self._next_update_id(),
            date=datetime.now(UTC),
            chat=CHAT,
            from_user=USER,
            photo=[PhotoSize(file_id="p1", file_unique_id="u1", width=100, height=100)],
        )
        return await self._feed(Update(update_id=self._next_update_id(), message=message))

    async def click(self, data: str) -> list[TelegramMethod]:
        self._callback_id += 1
        callback = CallbackQuery(
            id=f"cb{self._callback_id}",
            from_user=USER,
            chat_instance="ci",
            data=data,
            message=Message(
                message_id=1000 + self._callback_id,
                date=datetime.now(UTC),
                chat=CHAT,
                from_user=USER,
                text="savol",
            ),
        )
        return await self._feed(Update(update_id=self._next_update_id(), callback_query=callback))


# ---------------------------------------------------------------------- #
# Tugmalar orqali to'liq oqim (o'zbekcha)
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_full_flow_with_buttons_never_goes_silent() -> None:
    flow = FlowDriver()

    # 1. /start → til tanlash
    await flow.send("/start")
    assert "Tilni tanlang" in flow.last_text
    assert [b.callback_data for row in flow.last_markup.inline_keyboard for b in row] == [
        "lang:uz",
        "lang:ru",
    ]

    # 2. Til → salomlashuv + ism savoli (BITTA xabar)
    calls = await flow.click("lang:uz")
    new_messages = [c for c in calls if isinstance(c, SendMessage)]
    assert len(new_messages) == 1, "salomlashuv va savol bitta xabarda bo'lishi kerak"
    assert UZBEK.welcome in flow.last_text and UZBEK.ask_full_name in flow.last_text

    # 3. Ism → jins
    await flow.send("Vali Karimov")
    assert flow.last_text == UZBEK.ask_gender

    # 4. Jins → yosh
    await flow.click("cand_gender:male")
    assert flow.last_text == UZBEK.ask_age

    # 5. Yosh → shahar
    await flow.send("22")
    assert "Doimiy Toshkentda" in flow.last_text

    # 6. Shahar → RUS TILI SAVOLI (bu savol albatta chiqishi kerak)
    await flow.click("cand_yes")
    assert flow.last_text == UZBEK.ask_russian

    # 7. Rus tili → telefon
    await flow.click("cand_yes")
    assert flow.last_text == UZBEK.ask_phone

    # 8. Telefon → staj
    await flow.send("+998901234567")
    assert flow.last_text == UZBEK.ask_experience

    # 9. Staj → rezume
    await flow.send("2 yil sotuv menejeri")
    assert flow.last_text == UZBEK.ask_resume

    # 10. Rezume skip → natija
    await flow.click("cand_skip_resume")
    assert flow.last_text == UZBEK.result_qualified.format(name="Vali Karimov")

    async with session_scope() as session:
        row = (await session.execute(select(Application))).scalars().one()
    assert row.full_name == "Vali Karimov"
    assert row.language == "uz"
    assert row.is_qualified is True


# ---------------------------------------------------------------------- #
# Tugmasiz (yozib) to'liq oqim — ruscha
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_full_flow_typed_answers_in_russian() -> None:
    flow = FlowDriver()

    await flow.send("/start ru")  # deep-link: til tanlash oynasisiz
    assert "Здравствуйте" in flow.last_text

    await flow.send("Malika Rahimova")
    assert flow.last_text == RUSSIAN.ask_gender

    await flow.send("женский")  # tugma o'rniga yozdi
    assert flow.last_text == RUSSIAN.ask_age

    await flow.send("25")
    assert "проживаете в городе Toshkent" in flow.last_text

    await flow.send("да")
    assert flow.last_text == RUSSIAN.ask_russian

    await flow.send("нет")
    assert flow.last_text == RUSSIAN.ask_phone

    await flow.send("901234567")
    assert flow.last_text == RUSSIAN.ask_experience

    await flow.send("1 yil B2B savdo")
    assert flow.last_text == RUSSIAN.ask_resume

    await flow.send("skip")  # rezume o'rniga matn → skip
    assert "спасибо за заявку" in flow.last_text.lower()
    assert "Знание русского языка" in flow.last_text

    async with session_scope() as session:
        row = (await session.execute(select(Application))).scalars().one()
    assert row.language == "ru"
    assert row.knows_russian is False
    assert row.is_qualified is False
    assert row.phone == "+998901234567"


# ---------------------------------------------------------------------- #
# Kutilmagan xabar va buyruqlar
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_photo_in_the_middle_of_flow_is_reasked() -> None:
    flow = FlowDriver()
    await flow.send("/start")
    await flow.click("lang:uz")

    calls = await flow.send_photo()

    assert [c for c in calls if isinstance(c, SendMessage)], "bot jim qoldi"
    assert UZBEK.ask_full_name in flow.last_text

    # Oqim buzilmadi — ismni yozsa davom etadi
    await flow.send("Vali Karimov")
    assert flow.last_text == UZBEK.ask_gender


@pytest.mark.asyncio
async def test_garbage_answer_on_button_step_is_reasked() -> None:
    flow = FlowDriver()
    await flow.send("/start")
    await flow.click("lang:uz")
    await flow.send("Vali Karimov")
    await flow.click("cand_gender:male")
    await flow.send("22")

    calls = await flow.send("bilmadim")  # Ha/Yo'q o'rniga
    assert [c for c in calls if isinstance(c, SendMessage)]
    assert "Doimiy Toshkentda" in flow.last_text


@pytest.mark.asyncio
async def test_cancel_and_start_again() -> None:
    flow = FlowDriver()
    await flow.send("/start")
    await flow.click("lang:uz")

    await flow.send("/cancel")
    assert flow.last_text == UZBEK.cancelled

    await flow.send("Vali")  # oqim bekor qilingan → fallback
    assert "/start" in flow.last_text


@pytest.mark.asyncio
async def test_help_is_answered() -> None:
    flow = FlowDriver()
    await flow.send("/help")
    assert "Gulf HR bot" in flow.last_text


# ---------------------------------------------------------------------- #
# Bot qayta ishga tushganda suhbat davom etadi
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_flow_survives_bot_restart(tmp_path) -> None:
    db_file = str(tmp_path / "fsm.db")

    # --- birinchi ishga tushish ---
    first = FlowDriver(SqliteStorage(db_file))
    try:
        await first.send("/start")
        await first.click("lang:uz")
        await first.send("Vali Karimov")
        await first.click("cand_gender:male")
        await first.send("22")
        assert "Doimiy Toshkentda" in first.last_text
    finally:
        await first.close()

    # --- bot "qayta ishga tushdi" (yangi dispatcher, yangi storage, shu fayl) ---
    second = FlowDriver(SqliteStorage(db_file))
    try:
        # Nomzod shunchaki yozishni davom ettiradi — /start bosmaydi
        await second.send("ha")

        # Oldingi bosqich saqlangan: shahar javobi qabul qilindi va rus tili so'raldi
        assert second.last_text == UZBEK.ask_russian
        await second.send("ha")
        assert second.last_text == UZBEK.ask_phone
    finally:
        await second.close()


@pytest.mark.asyncio
async def test_memory_storage_loses_flow_on_restart() -> None:
    """MemoryStorage bilan (eski holat) suhbat uzilib qolishini ko'rsatadi."""
    first = FlowDriver()  # standart MemoryStorage
    await first.send("/start")
    await first.click("lang:uz")
    await first.send("Vali Karimov")

    second = FlowDriver()  # "restart"
    calls = await second.send("erkak")
    # Holat yo'qolgan → fallback /start ni so'raydi, oqim davom ETMAYDI
    assert "/start" in second.last_text
    assert len([c for c in calls if isinstance(c, SendMessage)]) == 1
