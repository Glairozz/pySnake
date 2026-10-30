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
    ACHIEVEMENT_KEYS,
    BONUS_HUNTER_COUNT,
    CENTURY_SCORE,
    DIFFICULTIES,
    LONG_BODY_LENGTH,
    MAX_QUEUED_TURNS,
    SURVIVOR_MOVES,
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
    ACHIEVEMENT = auto()
    GAME_OVER = auto()
    VICTORY = auto()


@dataclass(frozen=True)
class GameEvent:
    """A small, immutable notification emitted by :class:`Game`.

    ``value`` and ``combo`` describe the points awarded by a food event;
    ``text`` carries an achievement key.  Both are ignored by event kinds
    that do not need them.
    """

    kind: EventKind
    position: Cell | None = None
    value: int = 0
    combo: int = 0
    text: str | None = None


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
        self.wrap = config.wrap
        self.body: list[Cell] = []
        self.direction: Direction = (0, -1)
        self._pending: deque[Direction] = deque()
        self.grow = False
        self.wrapped_last_move = False
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
        self.wrapped_last_move = False

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

        In wrap mode the snake leaves one edge and reappears on the opposite
        edge instead of hitting a wall.  The tail cell is exempt while it is
        vacating this tick (unless the snake is growing), so following your
        own tail remains legal.
        """
        if self._pending:
            self.direction = self._pending.popleft()

        head_x, head_y = self.head
        x = head_x + self.direction[0]
        y = head_y + self.direction[1]
        wrapped = False
        if self.wrap:
            wrapped = not (0 <= x < self.cols and 0 <= y < self.rows)
            x %= self.cols
            y %= self.rows
        elif not (0 <= x < self.cols and 0 <= y < self.rows):
            return False
        new_head = (x, y)

        occupied = self.body if self.grow else self.body[:-1]
        if new_head in occupied:
            return False

        self.body.insert(0, new_head)
        if self.grow:
            self.grow = False
        else:
            self.body.pop()
        self.wrapped_last_move = wrapped
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
        self.combo = 0
        self.combo_ticks_left = 0
        self.max_combo = 0
        self.bonus_eaten = 0
        self.moves = 0
        self.wrapped_once = False
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

    @property
    def combo_multiplier(self) -> int:
        """The score multiplier earned by the current food combo."""
        return min(self.combo, self.config.combo_multiplier_cap)

    @property
    def speed_progress(self) -> float:
        """Progress (0..1) towards the next speed-up, or 1.0 at the cap."""
        preset = self.difficulty
        if self.speed >= preset.max_speed:
            return 1.0
        return (max(0, self.score) % preset.speed_step_score) / (
            preset.speed_step_score
        )

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
        return self._begin_fresh_run()

    def restart_run(self) -> bool:
        """Abandon the current run and immediately start a new one.

        This is the in-game ``R`` shortcut: it works while playing or paused
        so a bad run never forces the player to quit.  The current score is
        kept on the leaderboard, just like a regular game over.
        """
        if self.state not in (GameState.PLAYING, GameState.PAUSED):
            return False
        self._record_current_run()
        return self._begin_fresh_run()

    def _begin_fresh_run(self) -> bool:
        self._reset_run()
        self.state = GameState.PLAYING
        self._emit(EventKind.STARTED)
        return True

    def _record_current_run(self) -> None:
        """Persist the current score without counting an extra finished game."""
        if self.score > 0:
            self.stats.add_score(self.score)
            save_stats(self.stats, self.config.data_file)

    def _reset_run(self) -> None:
        """Clear everything that belongs to a single run."""
        self.snake.reset()
        self.food.spawn(self.snake.body)
        self.bonus = None
        self.score = 0
        self.foods_eaten = 0
        self.combo = 0
        self.combo_ticks_left = 0
        self.max_combo = 0
        self.bonus_eaten = 0
        self.moves = 0
        self.wrapped_once = False
        self.is_new_high = False
        self.victory = False
        self._events.clear()

    # -- simulation ---------------------------------------------------------

    def tick(self) -> None:
        """Advance the game by one move (no-op outside of PLAYING)."""
        if self.state is not GameState.PLAYING:
            return

        self._advance_combo()
        if not self.snake.move():
            self._end_game(victory=False)
            return

        self.moves += 1
        self.wrapped_once = self.wrapped_once or self.snake.wrapped_last_move
        head = self.snake.head

        if self.bonus is not None and head == self.bonus.position:
            bonus_position = self.bonus.position
            self.score += self.config.bonus_points
            self.bonus_eaten += 1
            self.snake.grow = True
            self.bonus = None
            self._emit(
                EventKind.ATE_BONUS,
                bonus_position,
                value=self.config.bonus_points,
            )
        elif self.bonus is not None:
            self.bonus.ticks_left -= 1
            if self.bonus.ticks_left <= 0:
                expired_at = self.bonus.position
                self.bonus = None
                self._emit(EventKind.BONUS_EXPIRED, expired_at)

        if head == self.food.position:
            self._eat_food()

        self._check_achievements()

    def _advance_combo(self) -> None:
        """Tick down the combo window, dropping the combo when it expires."""
        if self.combo_ticks_left <= 0:
            return
        self.combo_ticks_left -= 1
        if self.combo_ticks_left == 0:
            self.combo = 0

    def _eat_food(self) -> None:
        position = self.food.position
        self.combo += 1
        self.combo_ticks_left = self.config.combo_window
        self.max_combo = max(self.max_combo, self.combo)
        multiplier = self.combo_multiplier
        points = self.difficulty.points_per_food * multiplier

        self.snake.grow = True
        self.score += points
        self.foods_eaten += 1
        self._emit(
            EventKind.ATE_FOOD,
            position,
            value=points,
            combo=multiplier,
        )

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

    def _check_achievements(self, *, persist: bool = True) -> None:
        """Unlock any achievements whose conditions are now met."""
        conditions = {
            "first_bite": self.foods_eaten >= 1,
            "combo_master": self.max_combo >= self.config.combo_multiplier_cap,
            "century": self.score >= CENTURY_SCORE,
            "long_body": len(self.snake.body) >= LONG_BODY_LENGTH,
            "bonus_hunter": self.bonus_eaten >= BONUS_HUNTER_COUNT,
            "survivor": self.moves >= SURVIVOR_MOVES,
            "wrap_walker": self.wrapped_once,
            "victory": self.victory,
        }
        unlocked = False
        for key in ACHIEVEMENT_KEYS:
            if self.stats.has_achievement(key):
                continue
            if not conditions.get(key, False):
                continue
            if self.stats.unlock(key):
                unlocked = True
                self._emit(EventKind.ACHIEVEMENT, self.snake.head, text=key)
        if unlocked and persist:
            save_stats(self.stats, self.config.data_file)

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
        self.stats.add_score(self.score)
        self._check_achievements(persist=False)
        save_stats(self.stats, self.config.data_file)

        if self.is_new_high:
            self._emit(EventKind.NEW_HIGH_SCORE)
        self._emit(
            EventKind.VICTORY if victory else EventKind.GAME_OVER,
            self.snake.head,
        )

    def abandon(self) -> None:
        """Persist the current run when the player quits mid-run.

        A new best score is never lost and a good run still reaches the
        leaderboard, but ``games_played`` is only incremented by a real game
        over so quitting does not inflate the statistics.
        """
        if self.state not in (GameState.PLAYING, GameState.PAUSED):
            return
        self._record_current_run()

    # -- events -------------------------------------------------------------

    def _emit(
        self,
        kind: EventKind,
        position: Cell | None = None,
        *,
        value: int = 0,
        combo: int = 0,
        text: str | None = None,
    ) -> None:
        self._events.append(GameEvent(kind, position, value, combo, text))

    def drain_events(self) -> list[GameEvent]:
        """Return and clear all events accumulated since the last call."""
        events = self._events
        self._events = []
        return events
