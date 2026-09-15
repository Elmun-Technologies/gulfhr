"""Nomzodning vakansiya talablarga mosligini tekshiruvchi sof mantiq (UI'dan mustaqil)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateAnswers:
    full_name: str
    gender: str  # "male" yoki "female"
    age: int
    lives_in_city: bool
    phone: str
    experience: str = ""
    resume_info: str = ""


@dataclass(frozen=True)
class Verdict:
    is_qualified: bool
    reasons: list[str]
    reject_codes: tuple[str, ...] = ()


def qualify_candidate(
    answers: CandidateAnswers, *, min_age: int, max_age: int, required_city: str
) -> Verdict:
    """Javoblarni vakansiya talablari bilan solishtiradi.

    Talablar:
    - yosh: `min_age`..`max_age` (default 18-30)
    - doimiy `required_city` da istiqomat (yotoqxona berilmaydi)

    Jins va staj saralash mezoniga kirmaydi — ular shunchaki ma'lumot sifatida
    HR guruhiga yuboriladi.
    """
    reasons: list[str] = []
    codes: list[str] = []

    if not (min_age <= answers.age <= max_age):
        reasons.append(f"Yosh chegarasi: {min_age}-{max_age} (siz: {answers.age})")
        codes.append("age")

    if not answers.lives_in_city:
        reasons.append(
            f"Doimiy {required_city}da istiqomat qilish talab etiladi (yotoqxona yo'q)"
        )
        codes.append("city")

    return Verdict(is_qualified=not reasons, reasons=reasons, reject_codes=tuple(codes))
