"""Kechikish byudjeti — nomzod har bir bosqichda ko'p kutmasligi test bilan qotiriladi.

Tarix: tugma bosilganda uchta so'rov **ketma-ket** ketardi
(`answerCallbackQuery` → `editMessageReplyMarkup` → `sendMessage`) va har biri
bitta tarmoq RTT sini qo'shardi. Sekin tarmoqda nomzod har bosqichda bir necha
sekund kutardi — "bot o'ylanib qoldi, keyingi etapga o'tmayapti".

Bu test o'lchovni **haqiqiy Dispatcher** orqali, kechikishni simulyatsiya
qiluvchi sessiya bilan bajaradi va ikki narsani talab qiladi:

1. bitta bosqichda kritik yo'l = **1 RTT** (parallel so'rovlar bitta hisoblanadi);
2. butun ariza uchun jami ketma-ket kutishlar soni byudjetdan oshmasin.

Shu bilan kelajakda kimdir yana so'rovlarni ketma-ket qilib qo'ysa, test
yiqiladi va kechikish qaytishidan oldin ushlanadi.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

import pytest
from aiogram import Bot
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, SendMessage
from aiogram.methods.base import TelegramMethod

from tests.test_dispatcher_flow import CHAT, FlowDriver, MockedSession

# Simulyatsiya qilingan tarmoq kechikishi. Real Fly/ams ↔ Telegram RTT ~80 ms,
# lekin test tez ishlashi uchun 30 ms yetarli: ketma-ketlik yaqqol ko'rinadi.
LATENCY = 0.03

# Byudjetlar: bitta arizada nomzod kutadigan ketma-ket so'rovlar soni
MAX_STEP_ROUND_TRIPS = 1  # tugma bosish ham, matn yozish ham — 1 RTT
MAX_TOTAL_ROUND_TRIPS = 12  # 10 bosqich + natija uchun zaxira


class LatencySession(MockedSession):
    """`MockedSession` + har bir so'rov "tarmoqda" `LATENCY` vaqt yuradi."""

    def __init__(self, latency: float = LATENCY) -> None:
        super().__init__()
        self.latency = latency
        # (boshlanish, tugash, metod) — vaqt o'qini tahlil qilish uchun
        self.timeline: list[tuple[float, float, TelegramMethod]] = []

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout=None):  # noqa: ANN001
        started = time.perf_counter()
        if self.latency:
            await asyncio.sleep(self.latency)
        result = await super().make_request(bot, method, timeout)
        self.timeline.append((started, time.perf_counter(), method))
        return result


@dataclass
class Step:
    """Bitta nomzod harakati: qaysi so'rovlar ketdi va nomzod qancha kutdi."""

    name: str
    timeline: list[tuple[float, float, TelegramMethod]]
    started: float
    returned: float

    @property
    def methods(self) -> list[TelegramMethod]:
        """Shu qadamda yuborilgan so'rovlar (yuborilish tartibida)."""
        return [method for _, _, method in self.timeline]

    @property
    def round_trips(self) -> int:
        """Kritik yo'ldagi ketma-ket so'rovlar soni (parallel so'rovlar = 1 ta)."""
        calls = sorted(self.timeline, key=lambda item: item[0])
        best = [1] * len(calls)
        for i, (start_i, _, _) in enumerate(calls):
            for j in range(i):
                if calls[j][1] <= start_i:
                    best[i] = max(best[i], best[j] + 1)
        return max(best) if best else 0

    @property
    def late_calls(self) -> list[TelegramMethod]:
        """Handler qaytgandan KEYIN yuborilgan (fon) so'rovlar."""
        return [method for start, _, method in self.timeline if start > self.returned]

    @property
    def candidate_wait_ms(self) -> float:
        """Nomzod javobni ko'rgunicha o'tgan vaqt (HR guruhga ketadigan so'rovlar kirmaydi)."""
        ends = [
            end
            for _, end, method in self.timeline
            if not isinstance(method, SendMessage) or method.chat_id == CHAT.id
        ]
        return (max(ends) - self.started) * 1000 if ends else 0.0


async def measure(session: LatencySession, name: str, coro: Coroutine[Any, Any, Any]) -> Step:
    """Bitta harakatni o'lchaydi: so'rovlar vaqti va nomzod kutishi."""
    mark = len(session.timeline)
    started = time.perf_counter()
    await coro
    returned = time.perf_counter()
    return Step(name, session.timeline[mark:], started, returned)


FULL_FLOW_STEPS = (
    "1. /start",
    "2. til",
    "3. ism",
    "4. jins",
    "5. yosh",
    "6. shahar",
    "7. rus tili",
    "8. telefon",
    "9. staj",
    "10. rezume",
)


async def run_measured_flow() -> tuple[FlowDriver, LatencySession, list[Step]]:
    """Butun arizani o'tadi va har bir qadamni o'lchaydi."""
    session = LatencySession()
    flow = FlowDriver(session=session)
    actions: list[Coroutine[Any, Any, Any]] = [
        flow.send("/start"),
        flow.click("lang:uz"),
        flow.send("Vali Karimov"),
        flow.click("cand_gender:male"),
        flow.send("22"),
        flow.click("cand_yes"),
        flow.click("cand_yes"),
        flow.send("+998901234567"),
        flow.send("2 yil sotuv menejeri"),
        flow.click("cand_skip_resume"),
    ]
    steps: list[Step] = []
    for name, action in zip(FULL_FLOW_STEPS, actions, strict=True):
        steps.append(await measure(session, name, action))
    return flow, session, steps


@pytest.mark.asyncio
async def test_every_step_takes_one_network_round_trip() -> None:
    """Tugma ham, matn ham — nomzod bitta RTT ichida javob oladi."""
    flow, _session, steps = await run_measured_flow()

    assert not flow.errors, f"handler xato tashladi: {flow.errors}"

    for step in steps:
        # Oxirgi qadam HR guruhga kartani ham yuboradi (nomzod uni kutmaydi),
        # shuning uchun kritik yo'l 2 RTT gacha bo'lishi mumkin.
        limit = 2 if step.name.startswith("10.") else MAX_STEP_ROUND_TRIPS
        assert step.round_trips <= limit, (
            f"{step.name}: {step.round_trips} ta ketma-ket so'rov "
            f"({[type(c).__name__ for c in step.methods]}) — so'rovlar parallel ketishi kerak"
        )
        assert step.candidate_wait_ms < (limit + 1) * LATENCY * 1000, (
            f"{step.name}: nomzod {step.candidate_wait_ms:.0f} ms kutdi"
        )
        # Fon vazifasi qolib ketmasligi kerak — hammasi handler ichida kutiladi
        assert not step.late_calls, f"{step.name}: {step.late_calls}"

    total = sum(step.round_trips for step in steps)
    assert total <= MAX_TOTAL_ROUND_TRIPS, (
        f"Butun ariza {total} ta ketma-ket so'rov kutdi "
        f"(byudjet: {MAX_TOTAL_ROUND_TRIPS}) — nomzod har bosqichda sekinlashadi"
    )


@pytest.mark.asyncio
async def test_button_step_fires_requests_in_parallel() -> None:
    """Tugma bosilganda soat o'chirish, klaviatura va yangi savol bir vaqtda ketadi."""
    session = LatencySession()
    flow = FlowDriver(session=session)
    await flow.send("/start")
    await flow.click("lang:uz")
    await flow.send("Vali Karimov")

    step = await measure(session, "4. jins", flow.click("cand_gender:male"))

    kinds = [type(method) for method in step.methods]
    assert kinds == [AnswerCallbackQuery, EditMessageReplyMarkup, SendMessage], kinds
    # Uchta so'rov ham bitta RTT ga sig'adi (avval 3 ta ketma-ket so'rov edi)
    assert step.round_trips == 1
    assert step.candidate_wait_ms < 2 * LATENCY * 1000
