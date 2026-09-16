"""Nomzod arizalari: bazaga saqlash, HR guruhiga karta tuzish, /stats analitikasi."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time

from aiogram import Bot
from sqlalchemy import func, select

from app.candidates.qualify import CandidateAnswers, Verdict
from app.candidates.texts import (
    GENDER_LABELS,
    GROUP_HEADER_NOT_QUALIFIED,
    GROUP_HEADER_QUALIFIED,
    LANGUAGE_LABELS,
)
from app.config import Settings
from app.db.models import Application
from app.db.session import session_scope

logger = logging.getLogger(__name__)

# /stats hisobotida rad etish sabablari shu tartibda sanaladi
REJECT_CODE_LABELS = {
    "age": "Yosh chegarasidan tashqari",
    "city": "{city}da yashamaydi",
    "russian": "Rus tilini bilmaydi",
}
RECENT_LIMIT = 10


async def save_application(
    answers: CandidateAnswers,
    verdict: Verdict,
    *,
    telegram_id: int | None = None,
    telegram_username: str | None = None,
    resume_file_kind: str | None = None,
    resume_file_id: str | None = None,
) -> Application:
    """Bitta arizani bazaga yozadi."""
    async with session_scope() as session:
        record = Application(
            full_name=answers.full_name,
            gender=answers.gender,
            age=answers.age,
            lives_in_city=answers.lives_in_city,
            knows_russian=answers.knows_russian,
            phone=answers.phone,
            experience=answers.experience,
            resume_info=answers.resume_info,
            resume_file_kind=resume_file_kind,
            resume_file_id=resume_file_id,
            language=answers.language,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            is_qualified=verdict.is_qualified,
            reject_codes=",".join(verdict.reject_codes),
            created_at=datetime.now(UTC),
        )
        session.add(record)
        await session.flush()
        return record


def build_group_card(
    answers: CandidateAnswers,
    verdict: Verdict,
    *,
    telegram_id: int | None = None,
    telegram_username: str | None = None,
    now: datetime | None = None,
) -> str:
    """HR guruhiga yuboriladigan to'liq nomzod kartasi (HTML matn)."""
    if now is None:
        now = datetime.now(UTC)
    header = GROUP_HEADER_QUALIFIED if verdict.is_qualified else GROUP_HEADER_NOT_QUALIFIED
    gender_label = GENDER_LABELS.get(answers.gender, "—")
    resume_label = answers.resume_info if answers.resume_info else "Yuborilmagan"
    russian_label = "Ha" if answers.knows_russian else "Yo'q"
    language_label = LANGUAGE_LABELS.get(answers.language, "—")
    telegram_line = "💬 Telegram: —"
    if telegram_username or telegram_id is not None:
        username = f"@{telegram_username}" if telegram_username else "—"
        id_part = f" (id: <code>{telegram_id}</code>)" if telegram_id is not None else ""
        telegram_line = f"💬 Telegram: {username}{id_part}"

    lines = [
        header,
        "",
        f"👤 Ism: {answers.full_name}",
        f"⚧ Jins: {gender_label}",
        f"🎂 Yosh: {answers.age}",
        f"🗣 Rus tili: {russian_label}",
        f"🌐 Suhbat tili: {language_label}",
        f"📞 Telefon: {answers.phone}",
        f"💼 Staj: {answers.experience if answers.experience else '—'}",
        f"📎 Rezume: {resume_label}",
        telegram_line,
        f"🕓 Vaqt: {now.strftime('%d.%m.%Y %H:%M')}",
    ]
    if verdict.reasons:
        lines.append("")
        lines.append("Sabab(lar):")
        lines.extend(f"• {reason}" for reason in verdict.reasons)
    return "\n".join(lines)


async def notify_hr_group(
    bot: Bot,
    settings: Settings,
    answers: CandidateAnswers,
    verdict: Verdict,
    *,
    telegram_id: int | None = None,
    telegram_username: str | None = None,
    resume_file_kind: str | None = None,
    resume_file_id: str | None = None,
    now: datetime | None = None,
) -> None:
    """Nomzod kartasini (va rezume faylini) HR guruhiga yuboradi.

    Xato tashlamaydi — guruh sozlanmagan yoki yuborish muvaffaqiyatsiz bo'lsa
    faqat log'ga yozadi, nomzod oqimi uzilmaydi.
    """
    group_id = settings.candidates_group_chat_id
    if group_id is None:
        logger.debug("HR guruh sozlanmagan — nomzod kartasi yuborilmadi")
        return

    if now is None:
        now = datetime.now(UTC).astimezone(settings.timezone)
    card = build_group_card(
        answers,
        verdict,
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        now=now,
    )

    try:
        await bot.send_message(group_id, card, parse_mode="HTML")
    except Exception:  # noqa: BLE001
        logger.exception("HR guruhga xabar yuborib bo'lmadi (chat_id=%s)", group_id)
        return

    if resume_file_kind and resume_file_id:
        try:
            if resume_file_kind == "voice":
                await bot.send_voice(group_id, resume_file_id)
            elif resume_file_kind == "audio":
                await bot.send_audio(group_id, resume_file_id)
            elif resume_file_kind == "document":
                await bot.send_document(group_id, resume_file_id)
        except Exception:  # noqa: BLE001
            logger.exception("HR guruhga rezume yuborib bo'lmadi (chat_id=%s)", group_id)


async def build_candidates_report(settings: Settings) -> str:
    """/stats uchun analitika hisoboti (HTML matn).

    Barcha jamlanmalar SQL'da hisoblanadi — jadval Python'ga yuklanmaydi,
    shuning uchun arizalar soni oshsa ham hisobot tez chiqadi.
    """
    tz = settings.timezone
    now = datetime.now(tz)
    today_local = now.date()
    day_start_utc = (
        datetime.combine(today_local, time.min, tzinfo=tz)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    day_end_utc = (
        datetime.combine(today_local, time.max, tzinfo=tz)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )

    async with session_scope() as session:
        total = (await session.execute(select(func.count(Application.id)))).scalar_one()
        if total == 0:
            return "📊 <b>ANALITIKA</b>\n\nHali hech qanday ariza topshirilmagan."

        qualified = (
            await session.execute(
                select(func.count(Application.id)).where(Application.is_qualified.is_(True))
            )
        ).scalar_one()
        today = (
            await session.execute(
                select(func.count(Application.id)).where(
                    Application.created_at >= day_start_utc,
                    Application.created_at <= day_end_utc,
                )
            )
        ).scalar_one()

        # Rad etish sabablari SQL'da sanaladi — oldingi versiya 1000 ta satrni
        # Python'ga yuklab, u yerda sanardi (arizalar ko'paygani sari /stats
        # sekinlashar edi). Chegaralangan LIKE so'rovi jadvalni to'liq o'qimaydi.
        reject_counts: dict[str, int] = {}
        for code in REJECT_CODE_LABELS:
            count = (
                await session.execute(
                    select(func.count(Application.id)).where(
                        ("," + Application.reject_codes + ",").like(f"%,{code},%")
                    )
                )
            ).scalar_one()
            if count:
                reject_counts[code] = count

        rows = (
            await session.execute(
                select(
                    Application.full_name,
                    Application.gender,
                    Application.age,
                    Application.is_qualified,
                )
                .order_by(Application.created_at.desc(), Application.id.desc())
                .limit(RECENT_LIMIT)
            )
        ).all()

    rejected = total - qualified
    city = settings.candidate_city

    recent_lines: list[str] = []
    for r in rows:
        mark = "🟢" if r.is_qualified else "🔴"
        gender_label = GENDER_LABELS.get(r.gender or "", "")
        gender_str = f" ({gender_label})" if gender_label else ""
        recent_lines.append(f"{mark} {r.full_name}{gender_str} — {r.age} yosh")

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
            lines.append(f"• {REJECT_CODE_LABELS.get(code, code).format(city=city)}: {cnt}")
        lines.append("")

    if recent_lines:
        lines.append(f"🕘 <b>Oxirgi {RECENT_LIMIT} nomzod:</b>")
        lines.extend(recent_lines)

    return "\n".join(lines)
