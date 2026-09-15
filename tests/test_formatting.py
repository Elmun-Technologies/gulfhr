"""Formatlash yordamchi funksiyalari bo'yicha testlar."""

from __future__ import annotations

from app.services.formatting import money, progress_bar, status_emoji


def test_money_formats_with_spaces():
    assert money(1234567) == "1 234 567"


def test_progress_bar_full_and_empty():
    assert progress_bar(0) == "░" * 10
    assert progress_bar(1) == "▓" * 10
    assert progress_bar(0.5) == "▓" * 5 + "░" * 5


def test_status_emoji_on_track_vs_lagging():
    assert status_emoji(1.0, 1.0) == "🏆"
    assert status_emoji(0.97, 1.0) == "🟢"
    assert status_emoji(0.85, 1.0) == "🟡"
    assert status_emoji(0.3, 1.0) == "🔴"
