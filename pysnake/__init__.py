"""Core package for pySnake.

Importing :mod:`pysnake` is safe without pygame installed.  The graphical
front-end lives in :mod:`pysnake.app` and is imported only by ``snake.py``.
"""

from __future__ import annotations

from .config import (
    ACHIEVEMENT_KEYS,
    ACHIEVEMENTS,
    DIFFICULTIES,
    DIFFICULTY_KEYS,
    Achievement,
    Difficulty,
    GameConfig,
    speed_for_score,
)
from .logic import (
    BonusFood,
    EventKind,
    Food,
    Game,
    GameEvent,
    GameState,
    Snake,
)
from .storage import (
    TOP_SCORES_LIMIT,
    Stats,
    load_high_score,
    load_stats,
    save_high_score,
    save_stats,
)

__all__ = [
    "ACHIEVEMENTS",
    "ACHIEVEMENT_KEYS",
    "DIFFICULTIES",
    "DIFFICULTY_KEYS",
    "TOP_SCORES_LIMIT",
    "Achievement",
    "BonusFood",
    "Difficulty",
    "EventKind",
    "Food",
    "Game",
    "GameConfig",
    "GameEvent",
    "GameState",
    "Snake",
    "Stats",
    "load_high_score",
    "load_stats",
    "save_high_score",
    "save_stats",
    "speed_for_score",
]

__version__ = "2.2.0"
