"""`/diag` — bot qanday ishlayotganini ko'rsatadigan diagnostika buyrug'i.

Nima uchun kerak: "bot sekin" degan shikoyatda aybdor **kod**, **tarmoq** yoki
**server** bo'lishi mumkin. Buni taxmin qilmasdan ko'rish uchun bot Telegram
bilan aloqa tezligini (RTT), bazalar holatini va o'z ish statistikasini
o'lchab beradi.

Buyruqni **HR guruhida** istalgan a'zo yuborishi mumkin (xuddi `/stats` kabi).
Shaxsiy chatda faqat `ADMIN_USER_IDS` dagi foydalanuvchilar uchun ishlaydi —
nomzodlarga texnik ma'lumot ko'rinmasligi uchun.
"""

from __future__ import annotations

import logging
import os
import time

import aiosqlite
from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select

from app.bot.stats import STATS, humanize_duration
from app.candidates.texts import STATS_GROUP_ONLY
from app.config import get_settings
from app.db.models import Application
from app.db.session import session_scope

logger = logging.getLogger(__name__)
router = Router(name="diagnostics")

# Sekin tarmoq chegarasi: shundan qisqa RTT normal hisoblanadi
GOOD_RTT_MS = 300.0
SLOW_RTT_MS = 800.0


async def _api_rtt_ms(bot, rounds: int = 3) -> tuple[float, float]:  # noqa: ANN001
    """Telegram API javob vaqtini o'lchaydi: (o'rtacha, eng yaxshi) ms."""
    times: list[float] = []
    for _ in range(rounds):
        started = time.perf_counter()
        await bot.get_me()
        times.append((time.perf_counter() - started) * 1000)
    return sum(times) / len(times), min(times)


async def _send_rtt_ms(bot, chat_id: int, rounds: int = 2) -> float:
    """Xabar yuborish yo'lini o'lchaydi — `sendChatAction` ko'rinmaydi."""
    times: list[float] = []
    for _ in range(rounds):
        started = time.perf_counter()
        try:
            await bot.send_chat_action(chat_id, "typing")
        except Exception:  # noqa: BLE001 - o'lchov uchun xato muhim emas
            break
        times.append((time.perf_counter() - started) * 1000)
    return min(times) if times else -1.0


async def _fsm_rows(path: str) -> tuple[int, float]:
    """FSM bazasidagi suhbatlar soni va fayl hajmi (MB)."""
    size_mb = 0.0
    for suffix in ("", "-wal"):
        try:
            size_mb += os.path.getsize(path + suffix) / (1024 * 1024)
        except OSError:
            pass
    rows = 0
    if os.path.exists(path):
        try:
            async with aiosqlite.connect(path) as db:
                async with db.execute("SELECT COUNT(*) FROM fsm_states") as cursor:
                    row = await cursor.fetchone()
                    rows = int(row[0]) if row else 0
        except Exception as exc:  # noqa: BLE001 - diagnostika xato tashlamasin
            logger.warning("FSM bazasini o'qib bo'lmadi: %s", exc)
    return rows, size_mb


async def _applications_count() -> int:
    async with session_scope() as session:
        return int((await session.execute(select(func.count(Application.id)))).scalar_one())


def _rtt_comment(rtt_ms: float) -> str:
    if rtt_ms < 0:
        return "⚠️ o'lchab bo'lmadi"
    if rtt_ms <= GOOD_RTT_MS:
        return "✅ normal"
    if rtt_ms <= SLOW_RTT_MS:
        return "⚠️ sekinroq (server hududi uzoq bo'lishi mumkin)"
    return "🔴 juda sekin — server/tarmoqni almashtirish kerak (DEPLOY_FLY.md)"


@router.message(Command("diag", "ping", "tezlik"))
async def cmd_diag(message: Message, bot=None) -> None:  # noqa: ANN001
    """Botning ishlash tezligi va bazalar holati haqida hisobot."""
    settings = get_settings()
    group_id = settings.candidates_group_chat_id
    is_group = group_id is not None and message.chat.id == group_id
    is_admin = (
        message.chat.type == ChatType.PRIVATE
        and message.from_user is not None
        and message.from_user.id in settings.admin_user_id_set
    )
    if not (is_group or is_admin):
        await message.answer(
            STATS_GROUP_ONLY
            + "\n\n<i>Shaxsiy chatda /diag faqat ADMIN_USER_IDS uchun ishlaydi.</i>"
        )
        return

    bot = bot or message.bot
    started = time.perf_counter()

    avg_rtt, best_rtt = await _api_rtt_ms(bot)
    send_rtt = await _send_rtt_ms(bot, message.chat.id)
    fsm_rows, fsm_size = await _fsm_rows(settings.fsm_db_path)
    try:
        applications = await _applications_count()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Arizalar bazasini o'qib bo'lmadi: %s", exc)
        applications = -1

    webhook_line = "📡 Webhook: yo'q (long polling) ✅"
    try:
        info = await bot.get_webhook_info()
        if info.url:
            webhook_line = (
                "📡 Webhook: ⚠️ O'RNATILGAN — bu long polling bilan konflikt beradi!\n"
                f"   <code>{info.url}</code>\n"
                "   <i>Boshqa deploy (eski server) ham shu botni ushlab turgan bo'lishi mumkin.</i>"
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("getWebhookInfo bajarilmadi: %s", exc)

    stats = STATS.snapshot()
    me = await bot.get_me()
    slowest = float(stats["slowest_seconds"] or 0.0)
    last_slow = stats["last_slow_at"]

    lines = [
        "🩺 <b>BOT DIAGNOSTIKASI</b>",
        "",
        f"🤖 Bot: @{me.username or '—'} (id: <code>{me.id}</code>)",
        f"🕒 Ish vaqti: {humanize_duration(float(stats['uptime_seconds']))}",
        "",
        "<b>Telegram bilan aloqa</b>",
        f"⏱ API javob vaqti: {avg_rtt:.0f} ms (eng yaxshi: {best_rtt:.0f} ms) — {_rtt_comment(avg_rtt)}",
        f"📨 Xabar yuborish: {send_rtt:.0f} ms",
        webhook_line,
        "",
        "<b>So'rovlar</b>",
        f"🔄 Qayta ishlangan update: {stats['updates']}",
        f"🐌 Sekin (&gt;{settings.slow_request_threshold}s): {stats['slow']}",
        f"❗️ Xatolar: {stats['errors']}",
    ]
    if slowest:
        lines.append(f"🐢 Eng sekin so'rov: {slowest:.2f}s — <code>{stats['slowest_label']}</code>")
    if last_slow and stats["last_slow_label"]:
        minutes = (time.time() - float(last_slow)) / 60
        lines.append(
            f"🕘 Oxirgi sekin: {minutes:.0f} daqiqa oldin — <code>{stats['last_slow_label']}</code>"
        )

    applications_label = applications if applications >= 0 else "—"
    dropping = "ha" if settings.drop_pending_updates else "yo'q"
    language_choice = "yoqilgan" if settings.language_choice else "o'chirilgan"
    lines += [
        "",
        "<b>Bazalar</b>",
        f"🗄 Suhbat holati (FSM): {fsm_rows} ta yozuv, {fsm_size:.2f} MB",
        f"📋 Arizalar bazasi: {applications_label} ta",
        "",
        "<b>Sozlamalar</b>",
        f"⏳ So'rov timeout: {settings.tg_request_timeout:.0f}s, polling: {settings.polling_timeout}s",
        f"🧹 Eski update'larni tashlash: {dropping}",
        f"🌐 Til tanlash oynasi: {language_choice}",
        "",
        f"<i>Hisobot {((time.perf_counter() - started) * 1000):.0f} ms da tayyorlandi.</i>",
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")


__all__ = ["router"]
