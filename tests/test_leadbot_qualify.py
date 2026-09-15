"""leadbot.qualify uchun testlar."""

from __future__ import annotations

from leadbot.qualify import Answers, qualify

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


def test_qualified_when_all_criteria_met() -> None:
    verdict = qualify(_answers(), **CRITERIA)
    assert verdict.is_qualified
    assert verdict.reasons == []


def test_rejected_when_too_young() -> None:
    verdict = qualify(_answers(age=16), **CRITERIA)
    assert not verdict.is_qualified
    assert any("Yosh" in reason for reason in verdict.reasons)


def test_rejected_when_too_old() -> None:
    verdict = qualify(_answers(age=35), **CRITERIA)
    assert not verdict.is_qualified


def test_rejected_when_not_living_in_city() -> None:
    verdict = qualify(_answers(lives_in_city=False), **CRITERIA)
    assert not verdict.is_qualified
    assert any("Toshkent" in reason for reason in verdict.reasons)


def test_multiple_reasons_accumulate() -> None:
    verdict = qualify(_answers(age=40, lives_in_city=False), **CRITERIA)
    assert not verdict.is_qualified
    assert len(verdict.reasons) == 2


def test_boundary_ages_are_accepted() -> None:
    assert qualify(_answers(age=18), **CRITERIA).is_qualified
    assert qualify(_answers(age=30), **CRITERIA).is_qualified


def test_age_25_is_accepted_with_new_range() -> None:
    """Yosh chegarasi 18-30, 25 yosh mos kelishi kerak."""
    assert qualify(_answers(age=25), **CRITERIA).is_qualified


def test_gender_does_not_affect_qualification() -> None:
    """Jins qualification ga ta'sir qilmaydi."""
    assert qualify(_answers(gender="female"), **CRITERIA).is_qualified
    assert qualify(_answers(gender="male"), **CRITERIA).is_qualified


def test_experience_does_not_affect_qualification() -> None:
    """Staj qualification ga ta'sir qilmaydi (faqat ma'lumot sifatida)."""
    assert qualify(_answers(experience="tajribam yo'q"), **CRITERIA).is_qualified
    assert qualify(_answers(experience="5 yil"), **CRITERIA).is_qualified
