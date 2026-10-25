"""Display-independent game rules for pySnake.

Nothing in this module imports pygame: movement, collisions, scoring,
difficulty, bonus food and the game-state machine can all be exercised with
plain Python unit tests.  Rendering and keyboard handling live in
:mod:`pysnake.ui` and :mod:`pysnake.app`.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto

from .config import (
    DIFFICULTIES,
    MAX_QUEUED_TURNS,
    Difficulty,
    GameConfig,
    speed_for_score,
)
from .storage import Stats, load_stats, save_stats

Cell = tuple[int, int]
Direction = tuple[int, int]

DIRECTIONS: frozenset[Direction] = frozenset({(0, -1), (0, 1), (-1, 0), (1, 0)})


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class GameState(Enum):
    """Every state the game can be in."""

    START = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()  # also used for a completed (full) board


class EventKind(Enum):
    """Things the renderer and sound layer may react to."""

    STARTED = auto()
    ATE_FOOD = auto()
    ATE_BONUS = auto()
    BONUS_EXPIRED = auto()
    PAUSED = auto()
    RESUMED = auto()
    NEW_HIGH_SCORE = auto()
    GAME_OVER = auto()
    VICTORY = auto()


@dataclass(frozen=True)
class GameEvent:
    """A small, immutable notification emitted by :class:`Game`."""

    kind: EventKind
    position: Cell | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def free_cells(
    cols: int,
    rows: int,
    occupied: Iterable[Cell],
) -> list[Cell]:
    """Return every board cell not present in *occupied*."""
    taken = set(occupied)
    return [(x, y) for y in range(rows) for x in range(cols) if (x, y) not in taken]


def random_free_cell(
    cols: int,
    rows: int,
    occupied: Iterable[Cell],
    rng: random.Random,
) -> Cell | None:
    """Pick a random unoccupied cell, or return None when the board is full."""
    candidates = free_cells(cols, rows, occupied)
    return rng.choice(candidates) if candidates else None


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class Snake:
    """The snake's body and movement/collision rules."""

    def __init__(self, config: GameConfig) -> None:
        self.cols = config.cols
        self.rows = config.rows
        self.start_length = config.start_length
        self.body: list[Cell] = []
        self.direction: Direction = (0, -1)
        self._pending: deque[Direction] = deque()
        self.grow = False
        self.reset()

    def reset(self) -> None:
        """Restore the starting layout: a short snake facing upwards."""
        column = self.cols // 2
        middle = self.rows // 2
        top = max(0, min(middle - 1, self.rows - self.start_length))
        # Head first, tail trailing downwards so the snake faces away from
        # its own body and cannot collide on the first move.
        self.body = [(column, top + index) for index in range(self.start_length)]
        self.direction = (0, -1)
        self._pending.clear()
        self.grow = False

    @property
    def head(self) -> Cell:
        """Grid coordinates of the head segment."""
        return self.body[0]

    @property
    def next_direction(self) -> Direction:
        """The heading that will be used on the next move."""
        return self._pending[-1] if self._pending else self.direction

    def change_direction(self, dx: int, dy: int) -> bool:
        """Queue a turn and report whether it was accepted.

        A turn is validated against the *last queued* heading, not just the
        current one.  This lets two quick key presses (for example up then
        left) execute on consecutive ticks while still rejecting anything
        that would reverse the snake into its own neck.  At most
        :data:`MAX_QUEUED_TURNS` turns are buffered.
        """
        target = (dx, dy)
        if target not in DIRECTIONS:
            return False
        reference = self.next_direction
        if target == reference:
            return False
        if target == (-reference[0], -reference[1]):
            return False
        if len(self._pending) >= MAX_QUEUED_TURNS:
            return False
        self._pending.append(target)
        return True

    def move(self) -> bool:
        """Advance one step; return False on a wall or body collision.

        The tail cell is exempt while it is vacating this tick (unless the
        snake is growing), so following your own tail remains legal.
        """
        if self._pending:
            self.direction = self._pending.popleft()

        head_x, head_y = self.head
        new_head = (head_x + self.direction[0], head_y + self.direction[1])
        x, y = new_head
        if not (0 <= x < self.cols and 0 <= y < self.rows):
            return False

        occupied = self.body if self.grow else self.body[:-1]
        if new_head in occupied:
            return False

        self.body.insert(0, new_head)
        if self.grow:
            self.grow = False
        else:
            self.body.pop()
        return True


class Food:
    """A regular food pellet."""

    def __init__(
        self,
        config: GameConfig | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.config = config or GameConfig()
        self.rng = rng or random.Random()
        self.position: Cell = (0, 0)
        self.spawn()

    def spawn(self, occupied: Iterable[Cell] = ()) -> bool:
        """Move the food to a free cell; return False when the board is full."""
        cell = random_free_cell(
            self.config.cols,
            self.config.rows,
            occupied,
            self.rng,
        )
        if cell is None:
            return False
        self.position = cell
        return True


@dataclass
class BonusFood:
    """A temporary golden pellet worth extra points."""

    position: Cell
    ticks_left: int


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------


class Game:
    """Complete game state and rules, deliberately free of pygame."""

    def __init__(
        self,
        config: GameConfig | None = None,
        *,
        stats: Stats | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.config = config or GameConfig()
        self.rng = rng or random.Random(self.config.seed)
        self.stats = stats if stats is not None else load_stats(self.config.data_file)
        self.difficulty: Difficulty = DIFFICULTIES[self.config.difficulty]
        self.snake = Snake(self.config)
        self.food = Food(self.config, self.rng)
        self.food.spawn(self.snake.body)
        self.bonus: BonusFood | None = None

        self.state = GameState.START
        self.score = 0
        self.foods_eaten = 0
        self.is_new_high = False
        self.victory = False
        self._events: list[GameEvent] = []

    # -- read-only state ----------------------------------------------------

    @property
    def high_score(self) -> int:
        """The best recorded score, loaded from disk at startup."""
        return self.stats.high_score

    @property
    def speed(self) -> int:
        """Current tick rate in moves per second."""
        return speed_for_score(self.difficulty, self.score)

    # -- input --------------------------------------------------------------

    def set_difficulty(self, key: str) -> bool:
        """Select a difficulty on the start screen."""
        if self.state is not GameState.START or key not in DIFFICULTIES:
            return False
        self.difficulty = DIFFICULTIES[key]
        return True

    def start(self, direction: Direction | None = None) -> bool:
        """Leave the start screen, optionally queueing the first heading.

        A direction that would reverse the snake's initial heading is
        rejected (and does not start the game), matching the behaviour of
        every other turn.
        """
        if self.state is not GameState.START:
            return False
        if direction is not None:
            if direction not in DIRECTIONS:
                return False
            if direction == (
                -self.snake.direction[0],
                -self.snake.direction[1],
            ):
                return False
            if direction != self.snake.direction:
                self.snake.change_direction(*direction)
        self.state = GameState.PLAYING
        self._emit(EventKind.STARTED)
        return True

    def turn(self, direction: Direction) -> bool:
        """Handle a direction key for the current state."""
        if self.state is GameState.START:
            return self.start(direction)
        if self.state is GameState.PLAYING:
            return self.snake.change_direction(*direction)
        if self.state is GameState.PAUSED:
            accepted = self.snake.change_direction(*direction)
            self._resume()
            return accepted
        return False

    def toggle_pause(self) -> bool:
        """Pause a running game, or resume a paused one."""
        if self.state is GameState.PLAYING:
            self.state = GameState.PAUSED
            self._emit(EventKind.PAUSED)
            return True
        if self.state is GameState.PAUSED:
            self._resume()
            return True
        return False

    def _resume(self) -> None:
        self.state = GameState.PLAYING
        self._emit(EventKind.RESUMED)

    def restart(self) -> bool:
        """Start a fresh run after game over."""
        if self.state is not GameState.GAME_OVER:
            return False
        self._reset_run()
        self.state = GameState.PLAYING
        self._emit(EventKind.STARTED)
        return True

    def _reset_run(self) -> None:
        """Clear everything that belongs to a single run."""
        self.snake.reset()
        self.food.spawn(self.snake.body)
        self.bonus = None
        self.score = 0
        self.foods_eaten = 0
        self.is_new_high = False
        self.victory = False
        self._events.clear()

    # -- simulation ---------------------------------------------------------

    def tick(self) -> None:
        """Advance the game by one move (no-op outside of PLAYING)."""
        if self.state is not GameState.PLAYING:
            return
        if not self.snake.move():
            self._end_game(victory=False)
            return

        head = self.snake.head

        if self.bonus is not None and head == self.bonus.position:
            bonus_position = self.bonus.position
            self.score += self.config.bonus_points
            self.snake.grow = True
            self.bonus = None
            self._emit(EventKind.ATE_BONUS, bonus_position)
        elif self.bonus is not None:
            self.bonus.ticks_left -= 1
            if self.bonus.ticks_left <= 0:
                expired_at = self.bonus.position
                self.bonus = None
                self._emit(EventKind.BONUS_EXPIRED, expired_at)

        if head == self.food.position:
            self._eat_food()

    def _eat_food(self) -> None:
        position = self.food.position
        self.snake.grow = True
        self.score += self.difficulty.points_per_food
        self.foods_eaten += 1
        self._emit(EventKind.ATE_FOOD, position)

        if not self.food.spawn(self.snake.body):
            # No free cell remains: the player has filled the whole board.
            self._end_game(victory=True)
            return

        if self._bonus_due():
            self._spawn_bonus()

    def _bonus_due(self) -> bool:
        return (
            self.config.bonus_food
            and self.bonus is None
            and self.foods_eaten % self.config.bonus_every == 0
        )

    def _spawn_bonus(self) -> None:
        occupied = set(self.snake.body)
        occupied.add(self.food.position)
        cell = random_free_cell(
            self.config.cols,
            self.config.rows,
            occupied,
            self.rng,
        )
        if cell is not None:
            self.bonus = BonusFood(cell, self.config.bonus_lifetime)

    def _end_game(self, victory: bool) -> None:
        self.victory = victory
        self.state = GameState.GAME_OVER
        self.is_new_high = self.score > self.stats.high_score

        self.stats.games_played += 1
        self.stats.last_score = self.score
        final_length = min(
            len(self.snake.body) + (1 if self.snake.grow else 0),
            self.config.cols * self.config.rows,
        )
        self.stats.best_length = max(self.stats.best_length, final_length)
        if self.is_new_high:
            self.stats.high_score = self.score
        save_stats(self.stats, self.config.data_file)

        if self.is_new_high:
            self._emit(EventKind.NEW_HIGH_SCORE)
        self._emit(
            EventKind.VICTORY if victory else EventKind.GAME_OVER,
            self.snake.head,
        )

    def abandon(self) -> None:
        """Persist a new best score when the player quits mid-run."""
        if self.state not in (GameState.PLAYING, GameState.PAUSED):
            return
        if self.score > self.stats.high_score:
            self.stats.high_score = self.score
            save_stats(self.stats, self.config.data_file)

    # -- events -------------------------------------------------------------

    def _emit(self, kind: EventKind, position: Cell | None = None) -> None:
        self._events.append(GameEvent(kind, position))

    def drain_events(self) -> list[GameEvent]:
        """Return and clear all events accumulated since the last call."""
        events = self._events
        self._events = []
        return events
