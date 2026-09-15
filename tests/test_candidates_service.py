"""app.candidates.service — baza saqlash, karta va analitika bo'yicha testlar."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.candidates.qualify import CandidateAnswers, qualify_candidate
from app.candidates.service import build_candidates_report, build_group_card, save_application
from app.config import get_settings
from app.db.models import Application
from app.db.session import session_scope


def _answers(**overrides) -> CandidateAnswers:
    base = dict(
        full_name="Vali Karimov",
        gender="male",
        age=22,
        lives_in_city=True,
        phone="+998901234567",
        experience="2 yil sotuvchi",
        resume_info="",
    )
    base.update(overrides)
    return CandidateAnswers(**base)


def _verdict(answers: CandidateAnswers):
    settings = get_settings()
    return qualify_candidate(
        answers,
        min_age=settings.candidate_min_age,
        max_age=settings.candidate_max_age,
        required_city=settings.candidate_city,
    )


@pytest.mark.asyncio
async def test_save_application_persists_all_fields() -> None:
    answers = _answers(resume_info="📄 Fayl: resume.pdf")
    verdict = _verdict(answers)
    record = await save_application(
        answers,
        verdict,
        telegram_id=777,
        telegram_username="vali",
        resume_file_kind="document",
        resume_file_id="doc_file_id_1",
    )
    assert record.is_qualified is True
    assert record.reject_codes == ""

    async with session_scope() as session:
        row = (
            (await session.execute(select(Application).where(Application.id == record.id)))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.full_name == "Vali Karimov"
        assert row.gender == "male"
        assert row.age == 22
        assert row.lives_in_city is True
        assert row.phone == "+998901234567"
        assert row.experience == "2 yil sotuvchi"
        assert row.resume_info == "📄 Fayl: resume.pdf"
        assert row.resume_file_kind == "document"
        assert row.resume_file_id == "doc_file_id_1"
        assert row.telegram_id == 777
        assert row.telegram_username == "vali"


@pytest.mark.asyncio
async def test_save_rejected_application_stores_codes() -> None:
    answers = _answers(age=35, lives_in_city=False, gender="female")
    verdict = _verdict(answers)
    record = await save_application(answers, verdict)
    assert record.is_qualified is False
    assert set(record.reject_codes.split(",")) == {"age", "city"}


@pytest.mark.asyncio
async def test_report_empty_database() -> None:
    report = await build_candidates_report(get_settings())
    assert "Hali hech qanday ariza" in report


@pytest.mark.asyncio
async def test_report_totals_today_and_reasons() -> None:
    # Bugungi ariza (mos)
    await save_application(_answers(), _verdict(_answers()))
    # Bugungi rad etilgan ariza (yoshi katta)
    bad = _answers(age=45, full_name="Bobo Akbar")
    await save_application(bad, _verdict(bad))
    # Ikki kun oldingi ariza (shahar bo'yicha rad)
    old = _answers(lives_in_city=False, full_name="Samarah")
    async with session_scope() as session:
        session.add(
            Application(
                full_name=old.full_name,
                gender=old.gender,
                age=old.age,
                lives_in_city=old.lives_in_city,
                phone=old.phone,
                experience=old.experience,
                resume_info=old.resume_info,
                is_qualified=False,
                reject_codes="city",
                created_at=datetime.now(UTC) - timedelta(days=2),
            )
        )

    report = await build_candidates_report(get_settings())
    assert "👥 <b>Jami arizalar:</b> 3" in report
    assert "✅ <b>Mos kelgan:</b> 1" in report
    assert "❌ <b>Mos kelmagan:</b> 2" in report
    assert "📅 <b>Bugun:</b> 2" in report
    assert "• Yosh chegarasidan tashqari: 1" in report
    assert "• Toshkentda yashamaydi: 1" in report
    assert "🟢 Vali Karimov (Erkak) — 22 yosh" in report
    assert "🔴 Bobo Akbar (Erkak) — 45 yosh" in report
    assert "🔴 Samarah (Male)" not in report  # jins belgilanmagan bo'lsa yorliq chiqmaydi


def test_group_card_qualified() -> None:
    answers = _answers(resume_info="🎤 Ovozli xabar yuborildi")
    verdict = _verdict(answers)
    card = build_group_card(
        answers,
        verdict,
        telegram_id=777,
        telegram_username="vali",
        now=datetime(2026, 8, 28, 9, 30),
    )
    assert "🟢" in card and "MOS KELADI" in card
    assert "👤 Ism: Vali Karimov" in card
    assert "⚧ Jins: Erkak" in card
    assert "🎂 Yosh: 22" in card
    assert "📞 Telefon: +998901234567" in card
    assert "💼 Staj: 2 yil sotuvchi" in card
    assert "📎 Rezume: 🎤 Ovozli xabar yuborildi" in card
    assert "💬 Telegram: @vali (id: <code>777</code>)" in card
    assert "28.08.2026 09:30" in card
    assert "Sabab(lar):" not in card


def test_group_card_not_qualified_lists_reasons() -> None:
    answers = _answers(age=35, lives_in_city=False, gender="female")
    verdict = _verdict(answers)
    card = build_group_card(
        answers,
        verdict,
        now=datetime(2026, 8, 28, 9, 30),
    )
    assert "🔴" in card and "MOS KELMAYDI" in card
    assert "⚧ Jins: Ayol" in card
    assert "Sabab(lar):" in card
    assert "• Yosh chegarasi: 18-30 (siz: 35)" in card
    assert "Toshkentda istiqomat" in card


def test_group_card_defaults_when_info_missing() -> None:
    answers = _answers(experience="", resume_info="", gender="")
    verdict = _verdict(answers)
    card = build_group_card(answers, verdict)
    assert "💼 Staj: —" in card
    assert "📎 Rezume: Yuborilmagan" in card
    assert "⚧ Jins: —" in card
    assert "💬 Telegram: —" in card
