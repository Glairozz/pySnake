"""Tests for safe high-score and statistics persistence."""

from __future__ import annotations

import json

from pysnake.storage import (
    MAX_SAVED_VALUE,
    Stats,
    load_high_score,
    load_stats,
    save_high_score,
    save_stats,
)


def test_stats_roundtrip(tmp_path):
    path = tmp_path / "scores.json"
    original = Stats(high_score=120, games_played=7, last_score=80, best_length=14)
    assert save_stats(original, path) is True
    assert load_stats(path) == original


def test_missing_file_returns_blank_stats(tmp_path):
    assert load_stats(tmp_path / "missing.json") == Stats()


def test_corrupt_json_returns_blank_stats(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_stats(path) == Stats()


def test_non_object_json_returns_blank_stats(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_stats(path) == Stats()


def test_invalid_values_are_sanitised(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text(
        json.dumps(
            {
                "high_score": "not-a-number",
                "games_played": None,
                "last_score": -4,
                "best_length": True,
            }
        ),
        encoding="utf-8",
    )
    assert load_stats(path) == Stats()


def test_numeric_strings_and_integral_floats_are_accepted(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text(
        json.dumps(
            {
                "high_score": "120",
                "games_played": 3.0,
                "last_score": 40,
                "best_length": "9",
            }
        ),
        encoding="utf-8",
    )
    assert load_stats(path) == Stats(
        high_score=120,
        games_played=3,
        last_score=40,
        best_length=9,
    )


def test_partial_legacy_file_is_supported(tmp_path):
    path = tmp_path / "highscore.json"
    path.write_text(json.dumps({"high_score": 120}), encoding="utf-8")
    assert load_stats(path) == Stats(high_score=120)


def test_huge_values_are_clamped(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text(
        json.dumps({"high_score": 10**30, "games_played": -1}),
        encoding="utf-8",
    )
    stats = load_stats(path)
    assert stats.high_score == MAX_SAVED_VALUE
    assert stats.games_played == 0


def test_save_overwrites_previous_file_atomically(tmp_path):
    path = tmp_path / "scores.json"
    assert save_stats(Stats(high_score=10), path) is True
    assert save_stats(Stats(high_score=20, games_played=2), path) is True
    assert load_stats(path) == Stats(high_score=20, games_played=2)
    # No temporary files should be left behind.
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "scores" / "file.json"
    assert save_stats(Stats(high_score=5), path) is True
    assert load_high_score(path) == 5


def test_save_failure_is_reported_without_raising(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file", encoding="utf-8")
    path = blocker / "scores.json"
    assert save_stats(Stats(high_score=5), path) is False


def test_saved_values_are_sanitised(tmp_path):
    path = tmp_path / "scores.json"
    save_stats(
        Stats(high_score=-10, games_played=-2, last_score=-3, best_length=-1), path
    )
    assert load_stats(path) == Stats()


def test_load_high_score_helper(tmp_path):
    path = tmp_path / "scores.json"
    save_stats(Stats(high_score=42, games_played=4), path)
    assert load_high_score(path) == 42


def test_save_high_score_helper_preserves_other_statistics(tmp_path):
    path = tmp_path / "scores.json"
    save_stats(Stats(high_score=10, games_played=3, last_score=8, best_length=6), path)
    assert save_high_score(50, path) is True
    assert load_stats(path) == Stats(
        high_score=50,
        games_played=3,
        last_score=8,
        best_length=6,
    )


def test_save_high_score_does_not_lower_a_record(tmp_path):
    path = tmp_path / "scores.json"
    save_stats(Stats(high_score=50), path)
    assert save_high_score(20, path) is True
    assert load_high_score(path) == 50


def test_pathlike_and_string_paths_both_work(tmp_path):
    path = tmp_path / "scores.json"
    assert save_stats(Stats(high_score=1), str(path)) is True
    assert load_stats(path).high_score == 1
