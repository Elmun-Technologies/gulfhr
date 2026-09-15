"""app.candidates.qualify — saralash mantig'i bo'yicha testlar."""

from __future__ import annotations

from app.candidates.qualify import CandidateAnswers, qualify_candidate


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


def test_qualified_candidate_passes() -> None:
    verdict = qualify_candidate(_answers(), min_age=18, max_age=30, required_city="Toshkent")
    assert verdict.is_qualified
    assert verdict.reasons == []
    assert verdict.reject_codes == ()


def test_age_boundaries_18_and_30_are_qualified() -> None:
    for age in (18, 30):
        verdict = qualify_candidate(
            _answers(age=age), min_age=18, max_age=30, required_city="Toshkent"
        )
        assert verdict.is_qualified, f"yosh={age} chegarada bo'lishi kerak"


def test_too_young_is_rejected_with_age_code() -> None:
    verdict = qualify_candidate(_answers(age=17), min_age=18, max_age=30, required_city="Toshkent")
    assert not verdict.is_qualified
    assert "age" in verdict.reject_codes
    assert any("Yosh chegarasi: 18-30" in r for r in verdict.reasons)


def test_too_old_is_rejected_with_age_code() -> None:
    verdict = qualify_candidate(_answers(age=31), min_age=18, max_age=30, required_city="Toshkent")
    assert not verdict.is_qualified
    assert "age" in verdict.reject_codes


def test_living_outside_city_is_rejected_with_city_code() -> None:
    verdict = qualify_candidate(
        _answers(lives_in_city=False), min_age=18, max_age=30, required_city="Toshkent"
    )
    assert not verdict.is_qualified
    assert "city" in verdict.reject_codes
    assert any("Toshkentda" in r for r in verdict.reasons)


def test_both_reasons_are_reported() -> None:
    verdict = qualify_candidate(
        _answers(age=40, lives_in_city=False), min_age=18, max_age=30, required_city="Toshkent"
    )
    assert not verdict.is_qualified
    assert verdict.reject_codes == ("age", "city")
    assert len(verdict.reasons) == 2


def test_gender_and_experience_do_not_affect_verdict() -> None:
    # Jins va staj — saralash mezoniga kiradi, faqat ma'lumot sifatida yuboriladi
    verdict = qualify_candidate(
        _answers(gender="female", experience="tajribam yo'q"),
        min_age=18,
        max_age=30,
        required_city="Toshkent",
    )
    assert verdict.is_qualified
