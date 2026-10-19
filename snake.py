"""pySnake — a polished desktop Snake game built with pygame.

Run it with::

    python snake.py

All game rules (movement, collisions, scoring, difficulty) live in
display-independent classes, so the logic can be unit-tested headlessly.
``main`` only wires those rules to a pygame window.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from collections.abc import Iterable
from enum import Enum, auto

try:
    import pygame
except ModuleNotFoundError:  # pragma: no cover - depends on environment
    if __name__ == "__main__":
        sys.exit(
            "pygame is required to run pySnake.\n"
            "Install the dependencies with:  pip install -r requirements.txt"
        )
    raise

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 600, 650
HEADER_HEIGHT = 50  # HUD strip above the play field
GRID_SIZE = 25  # pixel size of one board cell
GRID_WIDTH = WIDTH // GRID_SIZE  # 24 columns
GRID_HEIGHT = (HEIGHT - HEADER_HEIGHT) // GRID_SIZE  # 24 rows
BOARD_TOP = HEADER_HEIGHT  # pixel y of the first board row

STARTING_LENGTH = 3
POINTS_PER_FOOD = 10

# Difficulty: the tick rate (moves per second) grows by SPEED_STEP every
# SPEED_STEP_SCORE points until it reaches MAX_SPEED.
BASE_SPEED = 12
MAX_SPEED = 25
SPEED_STEP = 2
SPEED_STEP_SCORE = 50

UI_FPS = 30  # frame rate for menus, pause and game over

HIGH_SCORE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "highscore.json"
)

COLORS = {
    "bg": (15, 15, 25),
    "bg_light": (25, 25, 40),
    "grid": (35, 35, 55),
    "snake_head": (120, 255, 120),
    "snake_body": (70, 220, 70),
    "snake_shadow": (40, 140, 40),
    "food": (255, 70, 70),
    "food_glow": (255, 120, 120),
    "food_inner": (255, 150, 150),
    "text": (230, 230, 230),
    "accent": (100, 200, 255),
    "warning": (255, 180, 50),
    "particle_food": (255, 100, 100),
    "eye": (20, 20, 30),
    "dim_text": (100, 100, 120),
}

# Arrow keys and WASD mapped to board deltas.
DIRECTION_KEYS: dict[int, tuple[int, int]] = {
    pygame.K_UP: (0, -1),
    pygame.K_DOWN: (0, 1),
    pygame.K_LEFT: (-1, 0),
    pygame.K_RIGHT: (1, 0),
    pygame.K_w: (0, -1),
    pygame.K_s: (0, 1),
    pygame.K_a: (-1, 0),
    pygame.K_d: (1, 0),
}

# Font objects must be (re)created whenever the font subsystem is
# (re)initialised — pygame.quit() frees the underlying fonts, so ``main``
# calls this again after every pygame.init().  Importing the module only
# needs the font subsystem, never a display, which keeps the game logic
# testable headlessly.
TITLE_FONT: pygame.font.Font
HEADER_FONT: pygame.font.Font
SMALL_FONT: pygame.font.Font
UI_FONT: pygame.font.Font


def _create_fonts() -> None:
    """(Re)create the module-level fonts; safe to call repeatedly."""
    global TITLE_FONT, HEADER_FONT, SMALL_FONT, UI_FONT
    pygame.font.init()
    TITLE_FONT = pygame.font.Font(None, 56)
    HEADER_FONT = pygame.font.Font(None, 32)
    SMALL_FONT = pygame.font.Font(None, 22)
    UI_FONT = pygame.font.Font(None, 20)


_create_fonts()


class GameState(Enum):
    """Every state the game can be in."""

    START = auto()  # title screen, waiting for a direction key
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()  # also used for a completed (full) board


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def cell_origin(gx: int, gy: int) -> tuple[int, int]:
    """Pixel coordinates of the top-left corner of a board cell."""
    return gx * GRID_SIZE, BOARD_TOP + gy * GRID_SIZE


def speed_for_score(score: int) -> int:
    """Return the tick rate in moves per second for *score*."""
    steps = max(0, score) // SPEED_STEP_SCORE
    return min(BASE_SPEED + steps * SPEED_STEP, MAX_SPEED)


def load_high_score(path: str = HIGH_SCORE_FILE) -> int:
    """Read the persisted high score; missing or corrupt files yield 0."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            value = json.load(fh).get("high_score", 0)
        return max(0, int(value))
    except (OSError, ValueError, TypeError):
        return 0


def save_high_score(score: int, path: str = HIGH_SCORE_FILE) -> None:
    """Persist *score*, ignoring storage errors (e.g. read-only media)."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"high_score": max(0, int(score))}, fh)
    except (OSError, TypeError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class Particle:
    """A short-lived sparkle shown when food is eaten."""

    def __init__(self, x: float, y: float, color: tuple[int, int, int]) -> None:
        self.x = x
        self.y = y
        self.color = color
        self.life = 1.0
        self.decay = random.uniform(0.02, 0.04)
        self.size = random.randint(3, 8)
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1, 3)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed

    def update(self) -> bool:
        """Move one frame; returns False once the particle has faded out."""
        self.x += self.vx
        self.y += self.vy
        self.life -= self.decay
        return self.life > 0

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the particle, shrinking as it fades."""
        if self.life > 0:
            radius = max(1, int(self.size * self.life))
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), radius)


class Snake:
    """The snake: body, movement and collision rules.

    Pure game logic — safe to use without a display.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Restore the starting layout: three segments facing up."""
        col = GRID_WIDTH // 2
        mid = GRID_HEIGHT // 2
        # Head first, tail trailing downwards so the snake starts facing
        # away from its own body.
        self.body = [(col, mid - 1 + i) for i in range(STARTING_LENGTH)]
        self.direction: tuple[int, int] = (0, -1)
        self.next_direction: tuple[int, int] = (0, -1)
        self.grow = False

    @property
    def head(self) -> tuple[int, int]:
        """Grid coordinates of the head segment."""
        return self.body[0]

    def change_direction(self, dx: int, dy: int) -> bool:
        """Queue a turn and report whether it was accepted.

        180° reversals are rejected.  ``direction`` only changes inside
        :meth:`move`, so validating every input against the current heading
        guarantees the snake can never steer into its own neck — even when
        several keys arrive between two moves.
        """
        target = (dx, dy)
        if target not in {(0, -1), (0, 1), (-1, 0), (1, 0)}:
            return False
        if target == (-self.direction[0], -self.direction[1]):
            return False
        self.next_direction = target
        return True

    def move(self) -> bool:
        """Advance one step; returns False on a wall or body collision.

        The tail cell is exempt while it is vacating this tick (unless the
        snake is growing), matching the classic rule that following your own
        tail is allowed.
        """
        self.direction = self.next_direction
        hx, hy = self.head
        new_head = (hx + self.direction[0], hy + self.direction[1])
        nx, ny = new_head
        if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
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

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the whole snake, head (with eyes) on top."""
        length = len(self.body)
        for index, (gx, gy) in enumerate(self.body):
            x, y = cell_origin(gx, gy)
            if index == 0:
                self._draw_head(surface, x, y)
                continue
            # Subtle fade towards the tail for a sense of depth.
            fade = index / max(1, length - 1)
            body_color = tuple(
                int(channel * (1 - 0.25 * fade)) for channel in COLORS["snake_body"]
            )
            pygame.draw.rect(
                surface,
                body_color,
                (x + 4, y + 4, GRID_SIZE - 8, GRID_SIZE - 8),
                border_radius=6,
            )
            pygame.draw.rect(
                surface,
                COLORS["snake_shadow"],
                (x + 4, y + GRID_SIZE - 10, GRID_SIZE - 8, 4),
                border_radius=3,
            )

    def _draw_head(self, surface: pygame.Surface, x: int, y: int) -> None:
        """Draw the head cell and a pair of eyes facing the heading."""
        pygame.draw.rect(
            surface,
            COLORS["snake_head"],
            (x + 3, y + 3, GRID_SIZE - 6, GRID_SIZE - 6),
            border_radius=8,
        )
        pygame.draw.rect(
            surface,
            COLORS["bg"],
            (x + 5, y + 5, GRID_SIZE - 10, GRID_SIZE - 10),
            border_radius=6,
        )

        dx, dy = self.direction
        if dx == 1:  # facing right
            eyes = ((x + 16, y + 9), (x + 16, y + 16))
        elif dx == -1:  # facing left
            eyes = ((x + 9, y + 9), (x + 9, y + 16))
        elif dy == -1:  # facing up
            eyes = ((x + 9, y + 9), (x + 16, y + 9))
        else:  # facing down
            eyes = ((x + 9, y + 16), (x + 16, y + 16))
        for ex, ey in eyes:
            pygame.draw.circle(surface, COLORS["eye"], (ex, ey), 3)


class Food:
    """A single food pellet with a pulsing glow."""

    def __init__(self, occupied: Iterable[tuple[int, int]] = ()) -> None:
        self.position: tuple[int, int] = (0, 0)
        self.spawn(occupied)

    def spawn(self, occupied: Iterable[tuple[int, int]] = ()) -> bool:
        """Place the food on a random cell not covered by *occupied*.

        Returns False when no free cell remains (the board is full).
        """
        taken = set(occupied)
        free = [
            (gx, gy)
            for gx in range(GRID_WIDTH)
            for gy in range(GRID_HEIGHT)
            if (gx, gy) not in taken
        ]
        if not free:
            return False
        self.position = random.choice(free)
        return True

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the pellet with an animated glow behind it."""
        x, y = cell_origin(*self.position)
        pulse = abs(pygame.time.get_ticks() % 800 - 400) / 400
        glow_size = int(GRID_SIZE + pulse * 6)
        glow_offset = (glow_size - GRID_SIZE) // 2

        glow = pygame.Surface((glow_size + 10, glow_size + 10), pygame.SRCALPHA)
        pygame.draw.rect(
            glow,
            (*COLORS["food_glow"], int(50 + pulse * 30)),
            (5, 5, glow_size, glow_size),
            border_radius=10,
        )
        surface.blit(glow, (x - 5 - glow_offset, y - 5 - glow_offset))

        pygame.draw.rect(
            surface,
            COLORS["food"],
            (x + 4, y + 4, GRID_SIZE - 8, GRID_SIZE - 8),
            border_radius=8,
        )
        inner = GRID_SIZE - 14
        if inner > 0:
            pygame.draw.rect(
                surface,
                COLORS["food_inner"],
                (x + 7, y + 7, inner, inner),
                border_radius=4,
            )


# ---------------------------------------------------------------------------
# Game state machine
# ---------------------------------------------------------------------------


class Game:
    """Complete game state and rules; deliberately display-free.

    The pygame loop in :func:`main` feeds it keys and ticks, and the
    drawing functions render it.
    """

    def __init__(self, high_score_path: str = HIGH_SCORE_FILE) -> None:
        self.high_score_path = high_score_path
        self.high_score = load_high_score(high_score_path)
        self.state = GameState.START
        self.snake = Snake()
        self.food = Food(self.snake.body)
        self.particles: list[Particle] = []
        self.score = 0
        self.is_new_high = False
        self.victory = False

    @property
    def speed(self) -> int:
        """Current tick rate in moves per second."""
        return speed_for_score(self.score)

    # -- input --------------------------------------------------------------

    def handle_key(self, key: int) -> None:
        """React to one key press, depending on the current state."""
        direction = DIRECTION_KEYS.get(key)

        if self.state is GameState.START:
            # A direction that would reverse into the snake's neck (DOWN,
            # since the snake faces up) is rejected and does not start the
            # game — the player simply presses another key.
            if direction and self.snake.change_direction(*direction):
                self.state = GameState.PLAYING

        elif self.state is GameState.PLAYING:
            if key == pygame.K_p:
                self.state = GameState.PAUSED
            elif direction:
                self.snake.change_direction(*direction)

        elif self.state is GameState.PAUSED:
            if key == pygame.K_p:
                self.state = GameState.PLAYING
            elif direction and self.snake.change_direction(*direction):
                # Any valid direction key also resumes the game.
                self.state = GameState.PLAYING

        elif self.state is GameState.GAME_OVER and key in (
            pygame.K_SPACE,
            pygame.K_RETURN,
        ):
            self.restart()

    def restart(self) -> None:
        """Start a fresh game after game over."""
        self._reset_run()
        self.state = GameState.PLAYING

    def _reset_run(self) -> None:
        """Clear everything that belongs to a single run."""
        self.snake.reset()
        self.food.spawn(self.snake.body)
        self.particles.clear()
        self.score = 0
        self.is_new_high = False
        self.victory = False

    # -- simulation ---------------------------------------------------------

    def tick(self) -> None:
        """Advance the game by one move (no-op outside of PLAYING)."""
        if self.state is not GameState.PLAYING:
            return
        if not self.snake.move():
            self._end_game(victory=False)
            return
        if self.snake.head == self.food.position:
            self._eat_food()

    def _eat_food(self) -> None:
        fx, fy = self.food.position
        self.snake.grow = True
        self.score += POINTS_PER_FOOD
        px, py = cell_origin(fx, fy)
        for _ in range(12):
            self.particles.append(
                Particle(
                    px + GRID_SIZE // 2,
                    py + GRID_SIZE // 2,
                    COLORS["particle_food"],
                )
            )
        if not self.food.spawn(self.snake.body):
            # No free cell left: the player filled the board and wins.
            self._end_game(victory=True)

    def _end_game(self, victory: bool) -> None:
        self.victory = victory
        self.is_new_high = self.score > self.high_score
        if self.is_new_high:
            self.high_score = self.score
            save_high_score(self.high_score, self.high_score_path)
        self.state = GameState.GAME_OVER

    def update_particles(self) -> None:
        """Advance particles by one frame and drop the faded ones."""
        self.particles = [p for p in self.particles if p.update()]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def draw_playfield(surface: pygame.Surface) -> None:
    """Background and grid lines of the board (header area excluded)."""
    surface.fill(COLORS["bg"])
    for gx in range(GRID_WIDTH + 1):
        x = gx * GRID_SIZE
        pygame.draw.line(surface, COLORS["grid"], (x, BOARD_TOP), (x, HEIGHT))
    for gy in range(GRID_HEIGHT + 1):
        y = BOARD_TOP + gy * GRID_SIZE
        pygame.draw.line(surface, COLORS["grid"], (0, y), (WIDTH, y))


def draw_header(surface: pygame.Surface, score: int, high_score: int) -> None:
    """HUD strip: title left, score centred, best score right."""
    pygame.draw.rect(surface, COLORS["bg_light"], (0, 0, WIDTH, HEADER_HEIGHT))
    pygame.draw.line(
        surface, COLORS["grid"], (0, HEADER_HEIGHT - 1), (WIDTH, HEADER_HEIGHT - 1), 2
    )
    middle = HEADER_HEIGHT // 2

    title = HEADER_FONT.render("SNAKE", True, COLORS["snake_head"])
    surface.blit(title, title.get_rect(midleft=(20, middle)))

    score_text = SMALL_FONT.render(f"Score: {score}", True, COLORS["text"])
    surface.blit(score_text, score_text.get_rect(center=(WIDTH // 2, middle)))

    best_text = SMALL_FONT.render(f"Best: {high_score}", True, COLORS["accent"])
    surface.blit(best_text, best_text.get_rect(midright=(WIDTH - 20, middle)))


def _center_text(
    surface: pygame.Surface,
    text_font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    y: int,
    shadow: tuple[int, int, int] | None = None,
) -> None:
    """Blit *text* horizontally centred at height *y*, optionally shadowed."""
    if shadow is not None:
        shadowed = text_font.render(text, True, shadow)
        surface.blit(shadowed, shadowed.get_rect(center=(WIDTH // 2 + 3, y + 3)))
    rendered = text_font.render(text, True, color)
    surface.blit(rendered, rendered.get_rect(center=(WIDTH // 2, y)))


def draw_start_screen(surface: pygame.Surface, high_score: int) -> None:
    """Title, prompt and controls on the start screen."""
    _center_text(
        surface,
        TITLE_FONT,
        "SNAKE",
        COLORS["snake_head"],
        HEIGHT // 2 - 80,
        shadow=COLORS["snake_shadow"],
    )
    _center_text(
        surface,
        HEADER_FONT,
        "Press any arrow key to start",
        COLORS["text"],
        HEIGHT // 2,
    )
    _center_text(
        surface,
        UI_FONT,
        "Arrow Keys or WASD to move  |  P to pause",
        COLORS["dim_text"],
        HEIGHT // 2 + 50,
    )
    if high_score > 0:
        _center_text(
            surface,
            HEADER_FONT,
            f"High Score: {high_score}",
            COLORS["accent"],
            HEIGHT // 2 + 100,
        )


def _draw_dim_overlay(surface: pygame.Surface, alpha: int) -> None:
    """Blit a translucent full-screen panel so text stays readable."""
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, alpha))
    surface.blit(overlay, (0, 0))


def draw_pause_overlay(surface: pygame.Surface) -> None:
    """Semi-transparent pause panel."""
    _draw_dim_overlay(surface, 150)
    _center_text(surface, TITLE_FONT, "PAUSED", COLORS["accent"], HEIGHT // 2)
    _center_text(
        surface, SMALL_FONT, "Press P to resume", COLORS["text"], HEIGHT // 2 + 40
    )


def draw_game_over_screen(
    surface: pygame.Surface,
    score: int,
    high_score: int,
    is_new_high: bool,
    victory: bool,
) -> None:
    """End-of-run panel: score, optional new-high banner, restart hint."""
    _draw_dim_overlay(surface, 200)
    title = "BOARD CLEARED!" if victory else "GAME OVER"
    color = COLORS["warning"] if victory else COLORS["food"]
    _center_text(surface, TITLE_FONT, title, color, HEIGHT // 2 - 60)
    _center_text(surface, HEADER_FONT, f"Score: {score}", COLORS["text"], HEIGHT // 2)
    if is_new_high:
        _center_text(
            surface, HEADER_FONT, "New High Score!", COLORS["accent"], HEIGHT // 2 + 40
        )
    _center_text(
        surface,
        SMALL_FONT,
        "Press SPACE to restart",
        COLORS["dim_text"],
        HEIGHT // 2 + 90,
    )


def draw(surface: pygame.Surface, game: Game) -> None:
    """Render the whole frame for the current game state."""
    if game.state is GameState.START:
        draw_playfield(surface)
        draw_header(surface, game.score, game.high_score)
        draw_start_screen(surface, game.high_score)
        return

    draw_playfield(surface)
    game.food.draw(surface)
    game.snake.draw(surface)
    for particle in game.particles:
        particle.draw(surface)
    draw_header(surface, game.score, game.high_score)

    if game.state is GameState.PAUSED:
        draw_pause_overlay(surface)
    elif game.state is GameState.GAME_OVER:
        draw_game_over_screen(
            surface, game.score, game.high_score, game.is_new_high, game.victory
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def create_window() -> tuple[pygame.Surface, pygame.time.Clock]:
    """Initialise pygame (fonts included) and open the game window."""
    try:
        pygame.init()
        _create_fonts()  # previous pygame.quit() invalidated the old fonts
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake")
    except pygame.error as exc:
        sys.exit(
            f"Unable to open a display: {exc}\n"
            "pySnake needs a desktop session (or SDL_VIDEODRIVER=dummy for tests)."
        )
    return screen, pygame.time.Clock()


def main(max_frames: int | None = None) -> Game:
    """Run the game until the window is closed (or *max_frames* elapse).

    Returns the final :class:`Game`, which automated smoke tests use to
    assert that the loop really ran.
    """
    screen, clock = create_window()
    game = Game()
    frames = 0
    running = True
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False  # ESC quits from any state
                elif event.type == pygame.KEYDOWN:
                    game.handle_key(event.key)
            if not running:
                break

            if game.state is GameState.PLAYING:
                game.tick()
                game.update_particles()

            draw(screen, game)
            pygame.display.flip()
            clock.tick(game.speed if game.state is GameState.PLAYING else UI_FPS)

            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
    finally:
        pygame.quit()
    return game


if __name__ == "__main__":
    main()
