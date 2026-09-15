"""leadbot.storage uchun testlar."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from zoneinfo import ZoneInfo

from leadbot.qualify import Answers, qualify
from leadbot.storage import (
    add_application,
    build_report,
    build_search_report,
    count_applications,
    init_db,
)

CRITERIA = {"min_age": 18, "max_age": 30, "required_city": "Toshkent"}


def _answers(**overrides: object) -> Answers:
    base = {
        "full_name": "Aliyev Vali",
        "gender": "male",
        "age": 22,
        "lives_in_city": True,
        "phone": "+998901234567",
        "experience": "2 yil sotuvchi",
        "resume_info": "",
    }
    base.update(overrides)
    return Answers(**base)


def _tmp_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    return path


def test_init_db_creates_table_and_counts_empty() -> None:
    path = _tmp_db()
    init_db(path)
    assert count_applications(path) == 0


def test_add_and_count_applications() -> None:
    path = _tmp_db()
    init_db(path)
    add_application(path, _answers(), qualify(_answers(), **CRITERIA))
    add_application(path, _answers(age=35), qualify(_answers(age=35), **CRITERIA))
    assert count_applications(path) == 2


def test_build_report_empty_db() -> None:
    path = _tmp_db()
    init_db(path)

    report = build_report(path, ZoneInfo("Asia/Tashkent"))
    assert "Hali hech qanday ariza topshirilmagan" in report


def test_build_report_shows_totals_and_reasons() -> None:
    path = _tmp_db()
    init_db(path)

    # Mos kelgan
    ok = qualify(_answers(), **CRITERIA)
    add_application(path, _answers(), ok)
    # Yosh + shahar sababi bilan rad
    bad = qualify(_answers(age=40, lives_in_city=False), **CRITERIA)
    add_application(path, _answers(age=40, lives_in_city=False), bad)

    report = build_report(path, ZoneInfo("Asia/Tashkent"))
    plain = report.replace("<b>", "").replace("</b>", "")
    assert "Jami arizalar: 2" in plain
    assert "Mos kelgan: 1" in plain
    assert "Mos kelmagan: 1" in plain
    assert "Yosh chegarasidan tashqari" in report
    assert "Toshkentda yashamaydi" in report


def test_gender_stored_in_db() -> None:
    """Gender ma'lumoti bazada saqlanishi kerak."""
    path = _tmp_db()
    init_db(path)
    female_answers = _answers(full_name="Karimova Nilufar", gender="female")
    verdict = qualify(female_answers, **CRITERIA)
    add_application(path, female_answers, verdict)
    assert count_applications(path) == 1


def test_experience_stored_in_db() -> None:
    """Staj ma'lumoti bazada saqlanishi kerak."""
    path = _tmp_db()
    init_db(path)
    exp_answers = _answers(experience="3 yil dastavka")
    verdict = qualify(exp_answers, **CRITERIA)
    add_application(path, exp_answers, verdict)
    assert count_applications(path) == 1


def test_recent_list_is_limited_to_ten() -> None:
    path = _tmp_db()
    init_db(path)
    for i in range(15):
        answers = _answers(full_name=f"Nomzod {i}")
        add_application(path, answers, qualify(answers, **CRITERIA))

    report = build_report(path, ZoneInfo("Asia/Tashkent"))
    assert "Jami arizalar: 15" in report.replace("<b>", "").replace("</b>", "")
    # Faqat oxirgi 10 tasi ro'yxatda, eng yangisi (Nomzod 14) birinchi bo'lishi kerak
    assert report.count("Nomzod") == 10
    assert "Nomzod 14" in report
    assert "Nomzod 0" not in report


def test_long_names_are_truncated_in_report() -> None:
    path = _tmp_db()
    init_db(path)
    long_name = "A" * 80
    answers = _answers(full_name=long_name)
    add_application(path, answers, qualify(answers, **CRITERIA))

    report = build_report(path, ZoneInfo("Asia/Tashkent"))
    assert long_name not in report
    assert "A" * 39 + "…" in report
    # Hisobot Telegram sendMessage limitidan (4096) ancha past bo'lishi kerak
    assert len(report) < 2000


def test_migrate_adds_missing_columns_to_old_database() -> None:
    """Production'da avvaldan mavjud (eski sxemadagi) baza ustunlarsiz qolmasligi kerak."""
    path = _tmp_db()
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            age INTEGER NOT NULL,
            lives_in_city INTEGER NOT NULL,
            phone TEXT NOT NULL,
            is_qualified INTEGER NOT NULL,
            reject_codes TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    init_db(path)  # eski bazaga gender/experience/resume_info ustunlarini qo'shishi kerak

    answers = _answers()
    add_application(path, answers, qualify(answers, **CRITERIA))
    assert count_applications(path) == 1


def test_search_finds_matching_experience_case_insensitive() -> None:
    path = _tmp_db()
    init_db(path)
    a = _answers(full_name="Qurilishchi Aka", experience="3 yil Qurilishda ishlagan")
    b = _answers(full_name="Sotuvchi Uka", experience="2 yil do'konda sotuvchi")
    add_application(path, a, qualify(a, **CRITERIA))
    add_application(path, b, qualify(b, **CRITERIA))

    report = build_search_report(path, "qurilish")
    assert "Qurilishchi Aka" in report
    assert "Sotuvchi Uka" not in report


def test_search_no_match_reports_empty() -> None:
    path = _tmp_db()
    init_db(path)
    a = _answers(experience="2 yil sotuvchi")
    add_application(path, a, qualify(a, **CRITERIA))

    report = build_search_report(path, "haydovchi")
    assert "topilmadi" in report


def test_search_ignores_voice_placeholder_experience() -> None:
    """Ovozli xabar orqali kelgan javob (placeholder matn) qidiruvda chiqmasligi kerak."""
    path = _tmp_db()
    init_db(path)
    voice_answer = _answers(experience="🎤 Ovozli xabar orqali tushuntirildi")
    add_application(path, voice_answer, qualify(voice_answer, **CRITERIA))

    report = build_search_report(path, "qurilish")
    assert "topilmadi" in report


def test_search_results_are_bounded_and_truncated() -> None:
    path = _tmp_db()
    init_db(path)
    long_experience = "qurilish " + "A" * 200
    for i in range(25):
        answers = _answers(full_name=f"Nomzod {i}", experience=long_experience)
        add_application(path, answers, qualify(answers, **CRITERIA))

    report = build_search_report(path, "qurilish")
    assert report.count("Nomzod") == 20
    assert len(report) < 4096
