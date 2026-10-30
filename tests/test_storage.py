"""Tests for safe high-score and statistics persistence."""

from __future__ import annotations

import json

from pysnake.storage import (
    MAX_SAVED_VALUE,
    TOP_SCORES_LIMIT,
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


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


def test_leaderboard_roundtrip(tmp_path):
    path = tmp_path / "scores.json"
    original = Stats(high_score=120, top_scores=[120, 90, 60])
    assert save_stats(original, path) is True
    assert load_stats(path) == original


def test_top_scores_are_sorted_trimmed_and_sanitised(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text(
        json.dumps(
            {
                "top_scores": [
                    10,
                    "bad",
                    -5,
                    True,
                    50,
                    None,
                    20,
                    40,
                    30,
                    60,
                    100,
                ]
            }
        ),
        encoding="utf-8",
    )
    assert load_stats(path).top_scores == [100, 60, 50, 40, 30]


def test_non_list_top_scores_fall_back_to_empty(tmp_path):
    path = tmp_path / "scores.json"
    for bad_value in ("100,90", 42, {"a": 1}, None):
        path.write_text(
            json.dumps({"top_scores": bad_value}),
            encoding="utf-8",
        )
        assert load_stats(path).top_scores == []


def test_add_score_updates_the_high_score_and_leaderboard():
    stats = Stats(high_score=80, top_scores=[80, 50])
    assert stats.add_score(120) is True
    assert stats.high_score == 120
    assert stats.top_scores == [120, 80, 50]

    assert stats.add_score(70) is False
    assert stats.top_scores == [120, 80, 70, 50]
    assert stats.high_score == 120


def test_add_score_ignores_zero_and_negative_values():
    stats = Stats()
    assert stats.add_score(0) is False
    assert stats.add_score(-10) is False
    assert stats.top_scores == []
    assert stats.high_score == 0


def test_add_score_keeps_only_the_best_scores():
    stats = Stats()
    for score in range(10, 110, 10):
        stats.add_score(score)
    assert len(stats.top_scores) == TOP_SCORES_LIMIT
    assert stats.top_scores == [100, 90, 80, 70, 60]
    assert stats.high_score == 100


def test_leaderboard_helper_respects_its_limit():
    stats = Stats(top_scores=[100, 90, 80, 70, 60])
    assert stats.leaderboard(3) == [100, 90, 80]
    assert stats.leaderboard(0) == []
    assert stats.leaderboard() == [100, 90, 80, 70, 60]


def test_leaderboard_is_written_to_the_score_file(tmp_path):
    path = tmp_path / "scores.json"
    save_stats(Stats(high_score=30, top_scores=[30, 20]), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["top_scores"] == [30, 20]


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------


def test_achievements_roundtrip(tmp_path):
    path = tmp_path / "scores.json"
    original = Stats(achievements=["first_bite", "century"])
    assert save_stats(original, path) is True
    assert load_stats(path) == original


def test_unknown_and_duplicate_achievements_are_removed(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text(
        json.dumps(
            {
                "achievements": [
                    "century",
                    "not-a-real-achievement",
                    "first_bite",
                    "century",
                    42,
                    None,
                ]
            }
        ),
        encoding="utf-8",
    )
    assert load_stats(path).achievements == ["first_bite", "century"]


def test_non_list_achievements_fall_back_to_empty(tmp_path):
    path = tmp_path / "scores.json"
    for bad_value in ("first_bite", 42, {"a": 1}, None):
        path.write_text(
            json.dumps({"achievements": bad_value}),
            encoding="utf-8",
        )
        assert load_stats(path).achievements == []


def test_unlock_only_adds_new_known_keys():
    stats = Stats()
    assert stats.unlock("first_bite") is True
    assert stats.unlock("first_bite") is False
    assert stats.unlock("not-a-real-achievement") is False
    assert stats.has_achievement("first_bite") is True
    assert stats.achievements == ["first_bite"]


def test_achievements_are_written_to_the_score_file(tmp_path):
    path = tmp_path / "scores.json"
    save_stats(Stats(achievements=["first_bite"]), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["achievements"] == ["first_bite"]
