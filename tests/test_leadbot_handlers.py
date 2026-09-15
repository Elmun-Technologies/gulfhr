"""leadbot.handlers ichidagi telefon normalizatsiyasi uchun testlar."""

from __future__ import annotations

from leadbot.handlers import _normalize_phone


def test_normalizes_plain_uzbek_number() -> None:
    assert _normalize_phone("901234567") == "+998901234567"


def test_keeps_already_full_international_number() -> None:
    assert _normalize_phone("+998901234567") == "+998901234567"


def test_strips_spaces_and_dashes() -> None:
    assert _normalize_phone("+998 90 123-45-67") == "+998901234567"


def test_rejects_too_short_number() -> None:
    assert _normalize_phone("12345") is None


def test_rejects_non_numeric_garbage() -> None:
    assert _normalize_phone("abc") is None
