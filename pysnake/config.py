"""Configuration, difficulty presets and visual constants for pySnake.

This module has no dependency on pygame, so the game rules can be imported and
tested in a completely headless Python environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Limits and defaults
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = PROJECT_ROOT / "highscore.json"

MIN_BOARD_SIZE = 8
MAX_BOARD_SIZE = 60
MIN_CELL_SIZE = 12
MAX_CELL_SIZE = 40
MAX_WINDOW_DIMENSION = 2400

DEFAULT_COLS = 24
DEFAULT_ROWS = 24
DEFAULT_CELL_SIZE = 25
DEFAULT_HEADER_HEIGHT = 50
DEFAULT_START_LENGTH = 3

#: Rendering runs at a steady frame rate; game moves happen on a fixed tick
#: schedule inside that loop.  This keeps movement timing independent of the
#: display refresh rate and keeps animations smooth on every machine.
RENDER_FPS = 60

#: Never simulate more than this much time in one frame.  It prevents a long
#: stall (dragging the window, waking from sleep) from causing a burst of
#: moves that the player could not react to.
MAX_FRAME_TIME = 0.25

#: How many turns may be buffered while waiting for the next move.
MAX_QUEUED_TURNS = 2


# ---------------------------------------------------------------------------
# Difficulty
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Difficulty:
    """Tuning values for one difficulty level."""

    key: str
    label: str
    base_speed: int
    max_speed: int
    speed_step: int
    speed_step_score: int
    description: str
    points_per_food: int = 10


DIFFICULTIES: dict[str, Difficulty] = {
    "easy": Difficulty(
        key="easy",
        label="EASY",
        base_speed=8,
        max_speed=18,
        speed_step=1,
        speed_step_score=50,
        description="Relaxed start with a gentle ramp-up",
    ),
    "normal": Difficulty(
        key="normal",
        label="NORMAL",
        base_speed=12,
        max_speed=25,
        speed_step=2,
        speed_step_score=50,
        description="The classic pySnake pace",
    ),
    "hard": Difficulty(
        key="hard",
        label="HARD",
        base_speed=16,
        max_speed=32,
        speed_step=2,
        speed_step_score=30,
        description="Fast start and frequent speed-ups",
    ),
}
DIFFICULTY_KEYS = tuple(DIFFICULTIES)


def speed_for_score(difficulty: Difficulty, score: int) -> int:
    """Return the tick rate (moves per second) for *score*."""
    steps = max(0, score) // difficulty.speed_step_score
    return min(
        difficulty.base_speed + steps * difficulty.speed_step, difficulty.max_speed
    )


# ---------------------------------------------------------------------------
# Game configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GameConfig:
    """Immutable settings for one game window.

    Board dimensions, speed preset, random seed, optional features and the
    score-file location all live here.  ``Game`` and the renderer receive a
    config instead of relying on global constants, which makes small-board
    tests and CLI overrides straightforward.
    """

    cols: int = DEFAULT_COLS
    rows: int = DEFAULT_ROWS
    cell_size: int = DEFAULT_CELL_SIZE
    header_height: int = DEFAULT_HEADER_HEIGHT
    start_length: int = DEFAULT_START_LENGTH
    difficulty: str = "normal"
    seed: int | None = None
    show_grid: bool = True
    sound: bool = True
    bonus_food: bool = True
    bonus_every: int = 5
    bonus_lifetime: int = 50
    bonus_points: int = 30
    data_file: Path = field(default_factory=lambda: DEFAULT_DATA_FILE)

    def __post_init__(self) -> None:
        """Normalise the data-file path and reject impossible settings."""
        object.__setattr__(self, "data_file", Path(self.data_file).expanduser())

        if not (MIN_BOARD_SIZE <= self.cols <= MAX_BOARD_SIZE):
            raise ValueError(
                f"columns must be between {MIN_BOARD_SIZE} and {MAX_BOARD_SIZE}"
            )
        if not (MIN_BOARD_SIZE <= self.rows <= MAX_BOARD_SIZE):
            raise ValueError(
                f"rows must be between {MIN_BOARD_SIZE} and {MAX_BOARD_SIZE}"
            )
        if not (MIN_CELL_SIZE <= self.cell_size <= MAX_CELL_SIZE):
            raise ValueError(
                f"cell size must be between {MIN_CELL_SIZE} and {MAX_CELL_SIZE}"
            )
        if self.header_height < 24:
            raise ValueError("header height must be at least 24 pixels")
        if not 1 <= self.start_length <= self.rows - 2:
            raise ValueError("start length must leave room for the snake on the board")
        if self.difficulty not in DIFFICULTIES:
            choices = ", ".join(DIFFICULTY_KEYS)
            raise ValueError(
                f"unknown difficulty {self.difficulty!r} (choose {choices})"
            )
        if self.width > MAX_WINDOW_DIMENSION or self.height > MAX_WINDOW_DIMENSION:
            raise ValueError(
                "the requested window is too large; reduce --cols, --rows or "
                "--cell-size"
            )
        if self.bonus_every < 1 or self.bonus_lifetime < 1 or self.bonus_points < 0:
            raise ValueError("bonus-food settings must be positive")

    @property
    def width(self) -> int:
        """Window width in pixels."""
        return self.cols * self.cell_size

    @property
    def height(self) -> int:
        """Window height in pixels, including the HUD strip."""
        return self.header_height + self.rows * self.cell_size

    @property
    def board_top(self) -> int:
        """Pixel y coordinate of the first board row."""
        return self.header_height

    @property
    def difficulty_preset(self) -> Difficulty:
        """The selected difficulty preset."""
        return DIFFICULTIES[self.difficulty]

    def cell_origin(self, gx: int, gy: int) -> tuple[int, int]:
        """Pixel coordinates of the top-left corner of a board cell."""
        return gx * self.cell_size, self.board_top + gy * self.cell_size

    def cell_center(self, gx: int, gy: int) -> tuple[float, float]:
        """Pixel coordinates of the centre of a board cell."""
        x, y = self.cell_origin(gx, gy)
        half = self.cell_size / 2
        return x + half, y + half


# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

COLORS: dict[str, tuple[int, int, int]] = {
    "bg": (15, 15, 25),
    "bg_light": (25, 25, 40),
    "board": (18, 18, 30),
    "grid": (35, 35, 55),
    "grid_bright": (52, 52, 78),
    "snake_head": (120, 255, 120),
    "snake_head_inner": (84, 225, 96),
    "snake_body": (70, 220, 70),
    "snake_shadow": (40, 140, 40),
    "food": (255, 70, 70),
    "food_glow": (255, 120, 120),
    "food_inner": (255, 170, 170),
    "bonus": (255, 215, 70),
    "bonus_glow": (255, 235, 140),
    "bonus_inner": (255, 250, 210),
    "text": (230, 230, 230),
    "accent": (100, 200, 255),
    "warning": (255, 180, 50),
    "eye": (18, 22, 30),
    "dim_text": (120, 120, 145),
    "panel": (10, 10, 18),
}
