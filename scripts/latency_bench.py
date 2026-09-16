"""Nomzod oqimining kechikishini o'lchaydi — real Telegram'siz.

Nima uchun kerak: bot "sekin" bo'lganda aybdor ko'pincha handler emas, balki
**ketma-ket bajarilayotgan Telegram API chaqiruvlari** bo'ladi. Har biri
tarmoq RTT'siga teng (Fly/ams ↔ api.telegram.org ~80 ms), va ular ketma-ket
ketsa kechikish ko'payib boradi.

Bu skript butun ariza oqimini haqiqiy `Dispatcher` orqali o'tkazadi, lekin
Telegram o'rniga kechikishni simulyatsiya qiluvchi session ishlatadi. Har bir
qadam uchun shu ko'rsatkichlar chiqadi:

- `calls`  — shu qadamda jami nechta API chaqiruv bo'ldi;
- `RTT`    — **kritik yo'lda** nechta ketma-ket so'rov kutildi
  (qadam vaqti / simulyatsiya qilingan kechikish) — asosiy o'lchov shu;
- `ms`     — qadam qancha vaqt oldi.

Ishga tushirish:

    python scripts/latency_bench.py                # 80 ms kechikish bilan
    python scripts/latency_bench.py --latency 300  # sekin tarmoq
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("BOT_TOKEN", "123456:BENCH")
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP_DB.name}")
os.environ.setdefault("CANDIDATES_CHAT_ID", "-1001234567890")

from aiogram import Bot  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import SendMessage  # noqa: E402
from aiogram.methods.base import TelegramMethod  # noqa: E402
from aiogram.types import (  # noqa: E402
    CallbackQuery,
    Chat,
    Message,
    Update,
    User,
)

from app.bot.setup import ROUTERS, build_dispatcher  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.fsm_storage import SqliteStorage  # noqa: E402
from app.db.session import dispose_db, get_engine  # noqa: E402

CHAT = Chat(id=42, type="private")
USER = User(id=42, is_bot=False, first_name="Vali", username="vali")


class LatencySession(BaseSession):
    """Telegram API o'rniga: har bir so'rov `latency` soniya "tarmoqda" yuradi."""

    def __init__(self, latency: float = 0.08) -> None:
        super().__init__()
        self.latency = latency
        self.calls: list[tuple[float, float, TelegramMethod]] = []

    async def close(self) -> None:
        return None

    async def make_request(self, bot, method: TelegramMethod, timeout=None):  # noqa: ANN001
        started = time.perf_counter()
        if self.latency:
            await asyncio.sleep(self.latency)
        self.calls.append((started, time.perf_counter(), method))
        if isinstance(method, SendMessage):
            return Message(message_id=len(self.calls) + 1, date=datetime.now(UTC), chat=CHAT)

    async def stream_content(  # noqa: ANN001
        self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True
    ) -> AsyncGenerator[bytes, None]:  # pragma: no cover
        if False:
            yield b""

    def take(self) -> list[tuple[float, float, TelegramMethod]]:
        calls, self.calls = self.calls, []
        return calls


@dataclass
class StepResult:
    name: str
    latency: float
    calls: list[tuple[float, float, TelegramMethod]] = field(default_factory=list)
    started: float = 0.0
    finished: float = 0.0
    error: BaseException | None = None

    @property
    def wall_ms(self) -> float:
        return (self.finished - self.started) * 1000

    @property
    def round_trips(self) -> int:
        """Kritik yo'ldagi KETMA-KET so'rovlar soni.

        Parallel (bir vaqtda) ketgan so'rovlar 1 ta hisoblanadi: bot javob
        yuborishdan oldin necha marta tarmoqni kutdi — nomzod sezadigan
        kechikish aynan shunga bog'liq.
        """
        calls = sorted(self.calls, key=lambda c: c[0])
        best = [1] * len(calls)
        for i, (start_i, _, _) in enumerate(calls):
            for j in range(i):
                if calls[j][1] <= start_i:
                    best[i] = max(best[i], best[j] + 1)
        return max(best) if best else 0

    @property
    def late_calls(self) -> int:
        """Handler qaytgandan keyin ketgan (fon) so'rovlar."""
        return sum(1 for start, _, _ in self.calls if start > self.finished)


class Bench:
    """Oqimni qadam-baqadam o'tkazadi va vaqtni o'lchaydi."""

    def __init__(self, latency: float, storage: SqliteStorage) -> None:
        for router in ROUTERS:
            router._parent_router = None
        self.latency = latency
        self.session = LatencySession(latency)
        self.bot = Bot(token="123456:BENCH", session=self.session)
        self.dp = build_dispatcher(storage)
        self.storage = storage
        self.errors: list[BaseException] = []
        self._update_id = 0
        self._callback_id = 0
        self.results: list[StepResult] = []

        @self.dp.errors()
        async def _on_error(event) -> bool:  # noqa: ANN001
            self.errors.append(event.exception)
            return True

    def _next_id(self) -> int:
        self._update_id += 1
        return self._update_id

    async def _run(self, name: str, update: Update) -> StepResult:
        # oldingi qadamning "fon" chaqiruvlarini ham shu qadamga qo'shamiz
        result = StepResult(name=name, latency=self.latency)
        before = len(self.session.calls)
        result.started = time.perf_counter()
        try:
            await self.dp.feed_update(self.bot, update)
        except BaseException as exc:  # noqa: BLE001
            result.error = exc
        result.finished = time.perf_counter()
        # fon (fire-and-forget) chaqiruvlar ham hisobga olinsin
        await asyncio.sleep(self.latency * 2 + 0.02)
        result.calls = self.session.calls[before:]
        del self.session.calls[before:]
        self.results.append(result)
        return result

    async def send(self, name: str, text: str) -> StepResult:
        message = Message(
            message_id=self._next_id(),
            date=datetime.now(UTC),
            chat=CHAT,
            from_user=USER,
            text=text,
        )
        return await self._run(name, Update(update_id=self._next_id(), message=message))

    async def click(self, name: str, data: str) -> StepResult:
        self._callback_id += 1
        message = Message(
            message_id=self._next_id(),
            date=datetime.now(UTC),
            chat=CHAT,
            text="...",
            reply_markup=None,
        )
        callback = CallbackQuery(
            id=f"cb{self._callback_id}",
            from_user=USER,
            chat_instance="ci",
            data=data,
            message=message,
        )
        return await self._run(name, Update(update_id=self._next_id(), callback_query=callback))

    async def close(self) -> None:
        await self.storage.close()


async def build_bench(latency: float) -> Bench:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    storage = SqliteStorage(f"{_TMP_DB.name}.fsm")
    await storage.setup()
    return Bench(latency, storage)


async def full_flow(latency: float) -> list[StepResult]:
    bench = await build_bench(latency)
    try:
        await bench.send("1. /start", "/start")
        await bench.click("2. til: o'zbekcha", "lang:uz")
        await bench.send("3. ism", "Vali Karimov")
        await bench.click("4. jins: erkak", "cand_gender:male")
        await bench.send("5. yosh", "22")
        await bench.click("6. shahar: ha", "cand_yes")
        await bench.click("7. rus tili: ha", "cand_yes")
        await bench.send("8. telefon", "+998901234567")
        await bench.send("9. staj", "2 yil sotuv menejeri")
        await bench.click("10. rezume: o'tkazib yuborish", "cand_skip_resume")
        return bench.results
    finally:
        await bench.close()
        await dispose_db()


def report(results: list[StepResult], latency: float) -> int:
    print(f"\nSimulyatsiya qilingan tarmoq kechikishi: {latency * 1000:.0f} ms\n")
    header = f"{'qadam':<34}{'calls':>6}{'ketma-ket RTT':>14}{'javob, ms':>12}{'fon':>6}"
    print(header)
    print("-" * len(header))
    total_rtt = 0
    total_ms = 0.0
    for result in results:
        total_rtt += result.round_trips
        total_ms += result.wall_ms
        note = f"  ⚠ {result.error!r}" if result.error else ""
        print(
            f"{result.name:<34}{len(result.calls):>6}"
            f"{result.round_trips:>12d}{result.wall_ms:>12.0f}"
            f"{result.late_calls:>6}{note}"
        )
    print("-" * len(header))
    print(f"{'JAMI':<34}{'':>6}{total_rtt:>12d}{total_ms:>12.0f}")
    print(
        "\nPastdagi raqam qancha kam bo'lsa, nomzod shuncha tez javob oladi:\n"
        "`ketma-ket RTT` = bot javob yuborishdan oldin necha marta tarmoqni kutdi.\n"
    )
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--latency",
        type=float,
        default=0.08,
        help="Har bir Telegram so'rovi uchun kechikish, soniya (default: 0.08)",
    )
    args = parser.parse_args()
    results = await full_flow(args.latency)
    return report(results, args.latency)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
