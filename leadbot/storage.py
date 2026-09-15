"""Arizalarni SQLite bazaga saqlash va analitika hisobotlarini tuzish.

Baza fayli `LEAD_DB_PATH` (default: ./data/leadbot.db) da joylashadi. Yozuvlar
har bir ariza topshirilganda `add_application` orqali qo'shiladi, `/stats`
buyrug'i esa `build_report` orqali guruhga umumiy statistika chiqaradi.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from leadbot.qualify import Answers, Verdict

REJECT_LABELS: dict[str, str] = {
    "age": "Yosh chegarasidan tashqari",
    "city": "Toshkentda yashamaydi",
}


def _connect(db_path: str) -> sqlite3.Connection:
    directory = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_new_columns(conn: sqlite3.Connection) -> None:
    """Mavjud bazaga yangi ustunlarni qo'shadi (migration)."""
    cur = conn.execute("PRAGMA table_info(applications)")
    existing = {row["name"] for row in cur.fetchall()}
    if "gender" not in existing:
        conn.execute("ALTER TABLE applications ADD COLUMN gender TEXT NOT NULL DEFAULT ''")
    if "experience" not in existing:
        conn.execute("ALTER TABLE applications ADD COLUMN experience TEXT NOT NULL DEFAULT ''")
    if "resume_info" not in existing:
        conn.execute("ALTER TABLE applications ADD COLUMN resume_info TEXT NOT NULL DEFAULT ''")


def init_db(db_path: str) -> None:
    """Agar baza bo'lmasa, jadvalni yaratadi."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                gender TEXT NOT NULL DEFAULT '',
                age INTEGER NOT NULL,
                lives_in_city INTEGER NOT NULL,
                phone TEXT NOT NULL,
                experience TEXT NOT NULL DEFAULT '',
                resume_info TEXT NOT NULL DEFAULT '',
                is_qualified INTEGER NOT NULL,
                reject_codes TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        _ensure_new_columns(conn)
        conn.commit()
    finally:
        conn.close()


def add_application(
    db_path: str,
    answers: Answers,
    verdict: Verdict,
    *,
    created_at: datetime | None = None,
) -> None:
    """Bitta arizani bazaga yozadi (yangi nomzod har safar kelganda chaqiriladi)."""
    if created_at is None:
        created_at = datetime.now(UTC)
    codes = ",".join(verdict.reject_codes)
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO applications (
                full_name, gender, age, lives_in_city, phone,
                experience, resume_info,
                is_qualified, reject_codes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                answers.full_name,
                answers.gender,
                answers.age,
                int(answers.lives_in_city),
                answers.phone,
                answers.experience,
                answers.resume_info,
                int(verdict.is_qualified),
                codes,
                created_at.isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def count_applications(db_path: str) -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM applications")
        return int(cur.fetchone()[0])
    finally:
        conn.close()


# /stats hisobotida ko'rsatiladigan so'nggi arizalar soni
RECENT_LIMIT = 10
# Har bir nomni shu uzunlikdan uzun bo'lsa qisqartiramiz (Telegram xabar limitidan
# himoya — o'nlab uzun ismlar ham hisobotni 4096 belgidan oshirib yubormasligi uchun)
MAX_DISPLAY_NAME_LENGTH = 40


def _truncate(text: str, limit: int = MAX_DISPLAY_NAME_LENGTH) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_report(db_path: str, tz: ZoneInfo) -> str:
    """Umumiy analitika hisobotini (matn) qaytaradi.

    Butun jadvalni Python'ga yuklamaslik uchun jamlanmalar SQL orqali
    hisoblanadi, so'nggi arizalar esa `LIMIT`li so'rov bilan olinadi.
    """
    from leadbot.texts import GENDER_LABELS

    conn = _connect(db_path)
    try:
        total = int(conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0])
        if total == 0:
            return "📊 <b>Analitika</b>\n\nHali hech qanday ariza topshirilmagan."

        qualified = int(
            conn.execute(
                "SELECT COUNT(*) FROM applications WHERE is_qualified = 1"
            ).fetchone()[0]
        )
        rejected = total - qualified

        # Bugungi kunni mahalliy vaqt mintaqasida hisoblab, UTC chegaralarga
        # o'tkazamiz — created_at ustuni doim UTC ISO satr sifatida saqlanadi,
        # shu format lug'aviy taqqoslashda ham xronologik tartibga mos keladi.
        now_local = datetime.now(tz)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        today = int(
            conn.execute(
                "SELECT COUNT(*) FROM applications WHERE created_at >= ? AND created_at < ?",
                (start_local.astimezone(UTC).isoformat(), end_local.astimezone(UTC).isoformat()),
            ).fetchone()[0]
        )

        # Reject sabablari bo'yicha taqsimot — bog'langan qiymatlar bilan
        # chegaralangan (LIKE) so'rovlar, to'liq jadval o'qilmaydi
        reject_counts: dict[str, int] = {}
        for code in REJECT_LABELS:
            cnt = int(
                conn.execute(
                    "SELECT COUNT(*) FROM applications "
                    "WHERE (',' || reject_codes || ',') LIKE ('%,' || ? || ',%')",
                    (code,),
                ).fetchone()[0]
            )
            if cnt:
                reject_counts[code] = cnt

        recent_rows = conn.execute(
            "SELECT full_name, gender, age, is_qualified FROM applications "
            "ORDER BY id DESC LIMIT ?",
            (RECENT_LIMIT,),
        ).fetchall()
    finally:
        conn.close()

    recent_lines = []
    for r in recent_rows:
        mark = "🟢" if r["is_qualified"] else "🔴"
        gender_label = GENDER_LABELS.get(r["gender"] or "", "")
        gender_str = f" ({gender_label})" if gender_label else ""
        recent_lines.append(f"{mark} {_truncate(r['full_name'])}{gender_str} — {r['age']} yosh")

    lines = [
        "📊 <b>ANALITIKA</b>\n",
        f"👥 <b>Jami arizalar:</b> {total}",
        f"✅ <b>Mos kelgan:</b> {qualified}",
        f"❌ <b>Mos kelmagan:</b> {rejected}",
        f"📅 <b>Bugun:</b> {today}",
        "",
    ]

    if reject_counts:
        lines.append("🚫 <b>Rad etish sabablari:</b>")
        for code, cnt in sorted(reject_counts.items(), key=lambda x: -x[1]):
            label = REJECT_LABELS.get(code, code)
            lines.append(f"• {label}: {cnt}")
        lines.append("")

    if recent_lines:
        lines.append("🕘 <b>Oxirgi 10 nomzod:</b>")
        lines.extend(recent_lines)

    return "\n".join(lines)


# /qidir buyrug'ida bittа so'rovda qaytariladigan maksimal natija soni
SEARCH_LIMIT = 20
# Har bir natijada staj matnini shu uzunlikkacha qisqartiramiz — 20 ta natija
# bilan ham hisobot Telegram'ning 4096 belgili sendMessage limitidan oshmasin
MAX_EXPERIENCE_DISPLAY_LENGTH = 80


def search_by_experience(db_path: str, keyword: str) -> list[sqlite3.Row]:
    """Staj matnida (faqat qo'lda yozilgan javoblarda) kalit so'zni qidiradi.

    Ovozli xabar yoki rezyume fayl orqali yuborilgan tajriba bu qidiruvga
    kirmaydi — bot ularning ichidagi matnni bilmaydi (transkripsiya yo'q).
    Faqat sifat bo'yicha bog'langan (?) LIKE so'rovi ishlatiladi, SQL
    in'ektsiyadan himoyalangan.
    """
    conn = _connect(db_path)
    try:
        pattern = f"%{keyword}%"
        return conn.execute(
            "SELECT full_name, age, phone, experience, is_qualified FROM applications "
            "WHERE experience LIKE ? COLLATE NOCASE "
            "ORDER BY id DESC LIMIT ?",
            (pattern, SEARCH_LIMIT),
        ).fetchall()
    finally:
        conn.close()


def build_search_report(db_path: str, keyword: str) -> str:
    """`/qidir <so'z>` uchun natijalar hisobotini (matn) qaytaradi."""
    rows = search_by_experience(db_path, keyword)
    safe_keyword = _truncate(keyword, 60)

    if not rows:
        return (
            f'🔍 <b>Qidiruv: "{safe_keyword}"</b>\n\n'
            "Hech qanday natija topilmadi (faqat qo'lda yozilgan staj javoblari "
            "orasida qidiriladi — ovozli xabarlar bu yerga kirmaydi)."
        )

    lines = [f'🔍 <b>Qidiruv: "{safe_keyword}"</b> — {len(rows)} ta natija\n']
    for r in rows:
        mark = "🟢" if r["is_qualified"] else "🔴"
        experience = _truncate(r["experience"] or "", MAX_EXPERIENCE_DISPLAY_LENGTH)
        lines.append(
            f"{mark} {_truncate(r['full_name'])} — {r['age']} yosh — {r['phone']}\n"
            f"   💼 {experience}"
        )

    if len(rows) == SEARCH_LIMIT:
        lines.append(f"\n⚠️ Faqat so'nggi {SEARCH_LIMIT} ta natija ko'rsatildi.")

    return "\n".join(lines)
