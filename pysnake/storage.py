"""Persistence for the high score and simple play statistics.

The score file is written atomically (temporary file + :func:`os.replace`) so a
crash or a full disk cannot leave a half-written JSON file behind.  Reading is
deliberately forgiving: missing, corrupt or hand-edited files fall back to
safe defaults instead of preventing the game from starting.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import DEFAULT_DATA_FILE

# Keep absurd values from a hand-edited file from producing silly displays.
MAX_SAVED_VALUE = 1_000_000_000

#: How many recent best scores the leaderboard keeps.
TOP_SCORES_LIMIT = 5


def _non_negative_int(value: Any, default: int = 0) -> int:
    """Convert *value* to a clamped, non-negative integer or return *default*."""
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            value = int(text)
        except ValueError:
            return default
    if isinstance(value, float):
        if not value.is_integer():
            return default
        value = int(value)
    if not isinstance(value, int):
        return default
    return max(0, min(value, MAX_SAVED_VALUE))


def _score_list(value: Any, limit: int = TOP_SCORES_LIMIT) -> list[int]:
    """Return a sorted, sanitised leaderboard from *value*.

    Only positive integers are kept, so a corrupt file cannot inject blank
    entries.  The list is always newest-best first and capped at *limit*.
    """
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        return []
    scores: list[int] = []
    for item in value:
        score = _non_negative_int(item)
        if score > 0:
            scores.append(score)
    return sorted(scores, reverse=True)[: max(0, limit)]


@dataclass
class Stats:
    """Data persisted between sessions."""

    high_score: int = 0
    games_played: int = 0
    last_score: int = 0
    best_length: int = 0
    top_scores: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "high_score": _non_negative_int(self.high_score),
            "games_played": _non_negative_int(self.games_played),
            "last_score": _non_negative_int(self.last_score),
            "best_length": _non_negative_int(self.best_length),
            "top_scores": _score_list(self.top_scores),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Stats:
        """Build sanitised statistics from a decoded JSON object."""
        return cls(
            high_score=_non_negative_int(data.get("high_score")),
            games_played=_non_negative_int(data.get("games_played")),
            last_score=_non_negative_int(data.get("last_score")),
            best_length=_non_negative_int(data.get("best_length")),
            top_scores=_score_list(data.get("top_scores")),
        )

    def add_score(self, score: int) -> bool:
        """Record *score* on the leaderboard; return True for a new best.

        Zero scores are ignored so an abandoned run does not push a blank
        entry onto the board.  The returned flag mirrors the old "new high
        score" check used by the renderer.
        """
        value = _non_negative_int(score)
        if value <= 0:
            return False
        is_high = value > self.high_score
        if is_high:
            self.high_score = value
        self.top_scores = sorted([*self.top_scores, value], reverse=True)[
            :TOP_SCORES_LIMIT
        ]
        return is_high

    def leaderboard(self, limit: int = TOP_SCORES_LIMIT) -> list[int]:
        """Return the best scores, newest-best first."""
        return self.top_scores[: max(0, limit)]


def load_stats(path: str | os.PathLike[str] = DEFAULT_DATA_FILE) -> Stats:
    """Load statistics; any read or format problem yields blank statistics."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError):
        return Stats()
    if not isinstance(data, dict):
        return Stats()
    return Stats.from_dict(data)


def save_stats(
    stats: Stats,
    path: str | os.PathLike[str] = DEFAULT_DATA_FILE,
) -> bool:
    """Atomically persist *stats*; return False if the file cannot be written."""
    target = Path(path)
    temp_path: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=str(target.parent),
        )
        temp_path = Path(temp_name)
    except OSError:
        return False

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(Stats.from_dict(stats.to_dict()).to_dict(), handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        return True
    except (OSError, TypeError, ValueError):
        try:
            os.close(descriptor)
        except OSError:
            pass
        return False
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Backwards-compatible helpers for the original high-score-only file.
# ---------------------------------------------------------------------------


def load_high_score(path: str | os.PathLike[str] = DEFAULT_DATA_FILE) -> int:
    """Return just the persisted high score (0 when unavailable)."""
    return load_stats(path).high_score


def save_high_score(
    score: int,
    path: str | os.PathLike[str] = DEFAULT_DATA_FILE,
) -> bool:
    """Update only the high score, preserving existing statistics."""
    stats = load_stats(path)
    candidate = _non_negative_int(score)
    if candidate > stats.high_score:
        stats.high_score = candidate
        return save_stats(stats, path)
    return True
