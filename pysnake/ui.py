"""Pygame rendering and visual effects for pySnake."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from .config import COLORS, DIFFICULTIES, DIFFICULTY_KEYS, GameConfig
from .logic import BonusFood, EventKind, Food, Game, GameEvent, GameState, Snake

# ---------------------------------------------------------------------------
# Particles
# ---------------------------------------------------------------------------


@dataclass
class Particle:
    """A short-lived circle used for food-eaten sparkles."""

    x: float
    y: float
    vx: float
    vy: float
    life: float
    decay: float
    size: float
    color: tuple[int, int, int]

    def update(self, dt: float) -> bool:
        """Advance the particle by *dt* seconds; return False when faded."""
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= max(0.0, 1.0 - 1.8 * dt)
        self.vy *= max(0.0, 1.0 - 1.8 * dt)
        self.life -= self.decay * dt
        return self.life > 0.0

    def draw(self, surface: pygame.Surface) -> None:
        fade = max(0.0, min(1.0, self.life))
        color = tuple(int(channel * fade) for channel in self.color)
        radius = max(1, int(self.size * (0.4 + 0.6 * fade)))
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), radius)


class ParticleSystem:
    """Owns all active particles; independent of the game rules."""

    def __init__(self, config: GameConfig) -> None:
        self.config = config
        self.particles: list[Particle] = []
        self._rng = random.Random()

    def burst(
        self,
        cell: tuple[int, int],
        color: tuple[int, int, int],
        count: int = 12,
    ) -> None:
        """Create a small burst at the centre of *cell*."""
        x, y = self.config.cell_center(*cell)
        for _ in range(count):
            angle = self._rng.uniform(0.0, math.tau)
            speed = self._rng.uniform(35.0, 135.0)
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    life=1.0,
                    decay=self._rng.uniform(1.7, 2.8),
                    size=self._rng.uniform(2.0, max(3.0, self.config.cell_size / 5)),
                    color=color,
                )
            )

    def update(self, dt: float) -> None:
        self.particles = [
            particle for particle in self.particles if particle.update(dt)
        ]

    def draw(self, surface: pygame.Surface) -> None:
        for particle in self.particles:
            particle.draw(surface)

    def clear(self) -> None:
        self.particles.clear()


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class Renderer:
    """Draws a :class:`Game` to a pygame surface."""

    def __init__(self, surface: pygame.Surface, config: GameConfig) -> None:
        self.surface = surface
        self.config = config
        self.grid_visible = config.show_grid
        self.particles = ParticleSystem(config)
        self._overlays: dict[int, pygame.Surface] = {}
        self._create_fonts()

    # -- setup --------------------------------------------------------------

    def _create_fonts(self) -> None:
        """Create readable fonts whose sizes follow the window width."""
        pygame.font.init()
        width = self.config.width
        self.title_font = pygame.font.Font(None, max(26, min(64, int(width * 0.09))))
        self.heading_font = pygame.font.Font(None, max(20, min(42, int(width * 0.055))))
        self.body_font = pygame.font.Font(None, max(14, min(28, int(width * 0.035))))
        self.small_font = pygame.font.Font(None, max(11, min(20, int(width * 0.026))))

    def handle_events(self, events: list[GameEvent]) -> None:
        """Turn gameplay events into particles."""
        for event in events:
            if event.position is None:
                continue
            if event.kind is EventKind.ATE_FOOD:
                self.particles.burst(event.position, COLORS["food"], 12)
            elif event.kind is EventKind.ATE_BONUS:
                self.particles.burst(event.position, COLORS["bonus"], 18)
            elif event.kind in {EventKind.GAME_OVER, EventKind.VICTORY}:
                color = (
                    COLORS["warning"]
                    if event.kind is EventKind.VICTORY
                    else COLORS["food"]
                )
                self.particles.burst(event.position, color, 10)

    def update(self, dt: float) -> None:
        self.particles.update(dt)

    # -- text helpers -------------------------------------------------------

    def _fit(self, image: pygame.Surface, max_width: int) -> pygame.Surface:
        if image.get_width() <= max_width or max_width <= 0:
            return image
        ratio = max_width / image.get_width()
        size = (max_width, max(1, int(image.get_height() * ratio)))
        return pygame.transform.smoothscale(image, size)

    def _text(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        center: tuple[int, int],
        *,
        shadow: tuple[int, int, int] | None = None,
        max_width: int | None = None,
    ) -> None:
        limit = max_width if max_width is not None else self.config.width - 24
        if shadow is not None:
            shadow_image = self._fit(font.render(text, True, shadow), limit)
            rect = shadow_image.get_rect(center=(center[0] + 2, center[1] + 2))
            self.surface.blit(shadow_image, rect)
        image = self._fit(font.render(text, True, color), limit)
        self.surface.blit(image, image.get_rect(center=center))

    def _text_left(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        position: tuple[int, int],
        *,
        max_width: int | None = None,
    ) -> None:
        limit = max_width if max_width is not None else self.config.width - 24
        image = self._fit(font.render(text, True, color), limit)
        self.surface.blit(image, image.get_rect(midleft=position))

    def _overlay(self, alpha: int) -> pygame.Surface:
        cached = self._overlays.get(alpha)
        if cached is None:
            cached = pygame.Surface(
                (self.config.width, self.config.height), pygame.SRCALPHA
            )
            cached.fill((5, 5, 12, alpha))
            self._overlays[alpha] = cached
        return cached

    # -- frame --------------------------------------------------------------

    def draw(self, game: Game, *, sound_enabled: bool = True) -> None:
        """Render the complete frame for *game*."""
        self._draw_board()
        self._draw_food(game.food)
        if game.bonus is not None:
            self._draw_bonus(game.bonus)
        self._draw_snake(game.snake)
        self.particles.draw(self.surface)
        self._draw_header(game)

        if game.state is GameState.START:
            self._draw_start_screen(game, sound_enabled)
        elif game.state is GameState.PAUSED:
            self._draw_pause_screen(game, sound_enabled)
        elif game.state is GameState.GAME_OVER:
            self._draw_game_over_screen(game)

    # -- board --------------------------------------------------------------

    def _draw_board(self) -> None:
        config = self.config
        self.surface.fill(COLORS["bg"])
        board_rect = pygame.Rect(
            0,
            config.board_top,
            config.width,
            config.rows * config.cell_size,
        )
        pygame.draw.rect(self.surface, COLORS["board"], board_rect)

        if self.grid_visible:
            for column in range(config.cols + 1):
                x = column * config.cell_size
                pygame.draw.line(
                    self.surface,
                    COLORS["grid"],
                    (x, config.board_top),
                    (x, config.height),
                )
            for row in range(config.rows + 1):
                y = config.board_top + row * config.cell_size
                pygame.draw.line(
                    self.surface,
                    COLORS["grid"],
                    (0, y),
                    (config.width, y),
                )

        pygame.draw.rect(self.surface, COLORS["grid_bright"], board_rect, 2)

    # -- entities -----------------------------------------------------------

    def _draw_snake(self, snake: Snake) -> None:
        size = self.config.cell_size
        inset = max(2, size // 8)
        radius = max(2, size // 4)
        length = len(snake.body)

        for index in range(length - 1, 0, -1):
            gx, gy = snake.body[index]
            x, y = self.config.cell_origin(gx, gy)
            fade = index / max(1, length - 1)
            body_color = tuple(
                int(channel * (1.0 - 0.22 * fade)) for channel in COLORS["snake_body"]
            )
            pygame.draw.rect(
                self.surface,
                body_color,
                (x + inset, y + inset, size - inset * 2, size - inset * 2),
                border_radius=radius,
            )
            shadow_height = max(2, size // 7)
            pygame.draw.rect(
                self.surface,
                COLORS["snake_shadow"],
                (
                    x + inset,
                    y + size - inset - shadow_height,
                    size - inset * 2,
                    shadow_height,
                ),
                border_radius=max(1, shadow_height // 2),
            )

        head_x, head_y = self.config.cell_origin(*snake.head)
        pygame.draw.rect(
            self.surface,
            COLORS["snake_head"],
            (head_x + 2, head_y + 2, size - 4, size - 4),
            border_radius=max(3, size // 3),
        )
        inner_inset = max(3, size // 7)
        pygame.draw.rect(
            self.surface,
            COLORS["snake_head_inner"],
            (
                head_x + inner_inset,
                head_y + inner_inset,
                size - inner_inset * 2,
                size - inner_inset * 2,
            ),
            border_radius=max(2, size // 4),
        )

        center_x, center_y = self.config.cell_center(*snake.head)
        dx, dy = snake.direction
        side = size * 0.20
        forward = size * 0.18
        eye_radius = max(1, size // 9)
        if dx:
            eye_x = center_x + dx * forward
            eyes = [(eye_x, center_y - side), (eye_x, center_y + side)]
        else:
            eye_y = center_y + dy * forward
            eyes = [(center_x - side, eye_y), (center_x + side, eye_y)]
        for eye in eyes:
            pygame.draw.circle(
                self.surface,
                COLORS["eye"],
                (int(eye[0]), int(eye[1])),
                eye_radius,
            )

    def _draw_food(self, food: Food) -> None:
        size = self.config.cell_size
        x, y = self.config.cell_origin(*food.position)
        pulse = abs(pygame.time.get_ticks() % 900 - 450) / 450.0

        glow = pygame.Surface((size + 12, size + 12), pygame.SRCALPHA)
        pygame.draw.rect(
            glow,
            (*COLORS["food_glow"], int(45 + pulse * 35)),
            (6, 6, size, size),
            border_radius=max(4, size // 2),
        )
        self.surface.blit(glow, (x - 6, y - 6))

        inset = max(2, size // 7)
        pygame.draw.rect(
            self.surface,
            COLORS["food"],
            (x + inset, y + inset, size - inset * 2, size - inset * 2),
            border_radius=max(3, size // 4),
        )
        inner = max(1, size - inset * 4)
        pygame.draw.rect(
            self.surface,
            COLORS["food_inner"],
            (x + inset * 2, y + inset * 2, inner, inner),
            border_radius=max(1, size // 7),
        )

    def _draw_bonus(self, bonus: BonusFood) -> None:
        size = self.config.cell_size
        x, y = self.config.cell_origin(*bonus.position)
        center_x, center_y = self.config.cell_center(*bonus.position)
        pulse = abs(pygame.time.get_ticks() % 700 - 350) / 350.0
        radius = size * (0.30 + 0.04 * pulse)

        glow = pygame.Surface((size + 16, size + 16), pygame.SRCALPHA)
        pygame.draw.circle(
            glow,
            (*COLORS["bonus_glow"], int(40 + pulse * 45)),
            (size // 2 + 8, size // 2 + 8),
            int(radius + 7),
        )
        self.surface.blit(glow, (x - 8, y - 8))

        diamond = [
            (center_x, center_y - radius),
            (center_x + radius, center_y),
            (center_x, center_y + radius),
            (center_x - radius, center_y),
        ]
        pygame.draw.polygon(self.surface, COLORS["bonus"], diamond)
        inner = radius * 0.48
        pygame.draw.polygon(
            self.surface,
            COLORS["bonus_inner"],
            [
                (center_x, center_y - inner),
                (center_x + inner, center_y),
                (center_x, center_y + inner),
                (center_x - inner, center_y),
            ],
        )

        # A small bar shows how long the bonus will remain on the board.
        ratio = max(0.0, min(1.0, bonus.ticks_left / self.config.bonus_lifetime))
        bar_height = max(2, size // 12)
        bar_margin = max(2, size // 8)
        bar_width = size - bar_margin * 2
        bar_y = y + size - bar_margin - bar_height
        pygame.draw.rect(
            self.surface,
            COLORS["bg"],
            (x + bar_margin, bar_y, bar_width, bar_height),
            border_radius=bar_height // 2,
        )
        pygame.draw.rect(
            self.surface,
            COLORS["bonus"],
            (x + bar_margin, bar_y, int(bar_width * ratio), bar_height),
            border_radius=bar_height // 2,
        )

    # -- HUD ----------------------------------------------------------------

    def _draw_header(self, game: Game) -> None:
        config = self.config
        height = config.header_height
        middle = height // 2
        pygame.draw.rect(self.surface, COLORS["bg_light"], (0, 0, config.width, height))
        pygame.draw.line(
            self.surface,
            COLORS["grid_bright"],
            (0, height - 2),
            (config.width, height - 2),
            2,
        )

        if config.width >= 520:
            self._text_left(
                "SNAKE",
                self.heading_font,
                COLORS["snake_head"],
                (16, middle),
                max_width=config.width // 3,
            )
            score_font = self.heading_font
            best_font = self.body_font
        else:
            score_font = self.body_font
            best_font = self.small_font

        score_color = COLORS["text"]
        self._text(
            f"Score {game.score}",
            score_font,
            score_color,
            (config.width // 2, middle),
            max_width=config.width // 3,
        )
        best_color = (
            COLORS["warning"] if game.score > game.high_score else COLORS["accent"]
        )
        self._text(
            f"Best {game.high_score}",
            best_font,
            best_color,
            (config.width - 16, middle),
            max_width=config.width // 3,
        )

    # -- start screen -------------------------------------------------------

    def _draw_start_screen(self, game: Game, sound_enabled: bool) -> None:
        config = self.config
        self.surface.blit(self._overlay(185), (0, 0))

        # Lay the screen out as a centred vertical stack instead of fixed
        # percentages, so short windows and small boards stay readable.
        scale = max(0.65, min(1.25, config.height / 650.0))
        title_h = self.title_font.get_height()
        prompt_h = self.heading_font.get_height()
        body_h = self.body_font.get_height()
        small_h = self.small_font.get_height()
        compact = config.height < 360
        diff_h = body_h if compact else body_h + 6 + small_h
        gaps = [
            int(24 * scale),
            int(14 * scale),
            int(6 * scale),
            int(18 * scale),
            int(14 * scale),
        ]
        if compact:
            gaps = [max(3, gap // 2) for gap in gaps]
        total = title_h + prompt_h + diff_h + body_h
        total += small_h if not compact else 0
        total += sum(gaps)
        y = max(6, (config.height - total) // 2)
        center_x = config.width // 2

        self._text(
            "SNAKE",
            self.title_font,
            COLORS["snake_head"],
            (center_x, y + title_h // 2),
            shadow=COLORS["snake_shadow"],
        )
        y += title_h + gaps[0]

        self._text(
            "Press an arrow key or WASD to begin",
            self.heading_font,
            COLORS["text"],
            (center_x, y + prompt_h // 2),
        )
        y += prompt_h + gaps[1]

        self._draw_difficulty_selector(
            game,
            y + body_h // 2,
            description_center=y + body_h + 6 + small_h // 2,
            show_description=not compact,
        )
        y += diff_h + gaps[2]

        best_line = f"Best {game.high_score}"
        if game.stats.games_played:
            best_line += (
                f"    Last {game.stats.last_score}    Games {game.stats.games_played}"
            )
        self._text(
            best_line,
            self.body_font,
            COLORS["accent"],
            (center_x, y + body_h // 2),
        )
        y += body_h + gaps[3]

        if compact:
            return

        sound_text = "on" if sound_enabled else "off"
        controls = f"P pause   G grid   M sound ({sound_text})   ESC quit"
        self._text(
            controls,
            self.small_font,
            COLORS["dim_text"],
            (center_x, y + small_h // 2),
        )
        y += small_h + gaps[4]

        footer = "Food +10"
        if config.bonus_food:
            footer += f"   Golden food +{config.bonus_points}"
        self._text(
            footer,
            self.small_font,
            COLORS["dim_text"],
            (center_x, y + small_h // 2),
        )

    def _draw_difficulty_selector(
        self,
        game: Game,
        y: int,
        *,
        description_center: int | None = None,
        show_description: bool = True,
    ) -> None:
        labels = []
        for index, key in enumerate(DIFFICULTY_KEYS):
            preset = DIFFICULTIES[key]
            labels.append((key, f"{index + 1}  {preset.label}"))

        gap = max(10, self.config.width // 35)
        images: list[tuple[str, pygame.Surface]] = []
        for key, label in labels:
            color = (
                COLORS["accent"] if key == game.difficulty.key else COLORS["dim_text"]
            )
            images.append((key, self.body_font.render(label, True, color)))

        total = sum(image.get_width() for _, image in images) + gap * (len(images) - 1)
        max_width = self.config.width - 30
        if total > max_width:
            ratio = max_width / total
            scaled = []
            for key, image in images:
                size = (
                    max(1, int(image.get_width() * ratio)),
                    max(1, int(image.get_height() * ratio)),
                )
                scaled.append((key, pygame.transform.smoothscale(image, size)))
            images = scaled
            gap = max(4, int(gap * ratio))
            total = sum(image.get_width() for _, image in images) + gap * (
                len(images) - 1
            )

        x = max(5, (self.config.width - total) // 2)
        for key, image in images:
            rect = image.get_rect(midleft=(x, y))
            self.surface.blit(image, rect)
            if key == game.difficulty.key:
                pygame.draw.line(
                    self.surface,
                    COLORS["accent"],
                    (rect.left, rect.bottom + 2),
                    (rect.right, rect.bottom + 2),
                    2,
                )
            x = rect.right + gap

        if not show_description:
            return

        preset = game.difficulty
        description = (
            f"{preset.label.title()} · {preset.base_speed}–{preset.max_speed} moves/s"
        )
        if description_center is None:
            description_center = y + max(22, self.body_font.get_height() + 8)
        self._text(
            description,
            self.small_font,
            COLORS["dim_text"],
            (self.config.width // 2, description_center),
        )

    # -- pause screen -------------------------------------------------------

    def _draw_pause_screen(self, game: Game, sound_enabled: bool) -> None:
        config = self.config
        self.surface.blit(self._overlay(165), (0, 0))
        self._text(
            "PAUSED",
            self.title_font,
            COLORS["accent"],
            (config.width // 2, int(config.height * 0.36)),
        )
        self._text(
            "P or a direction key to resume",
            self.body_font,
            COLORS["text"],
            (config.width // 2, int(config.height * 0.48)),
        )
        status = (
            f"Grid: {'on' if self.grid_visible else 'off'}    "
            f"Sound: {'on' if sound_enabled else 'off'}    "
            f"Difficulty: {game.difficulty.label.title()}"
        )
        self._text(
            status,
            self.small_font,
            COLORS["dim_text"],
            (config.width // 2, int(config.height * 0.57)),
        )
        self._text(
            "ESC quits the game",
            self.small_font,
            COLORS["dim_text"],
            (config.width // 2, int(config.height * 0.66)),
        )

    # -- game over ----------------------------------------------------------

    def _draw_game_over_screen(self, game: Game) -> None:
        config = self.config
        self.surface.blit(self._overlay(205), (0, 0))
        title = "BOARD CLEARED!" if game.victory else "GAME OVER"
        title_color = COLORS["warning"] if game.victory else COLORS["food"]
        self._text(
            title,
            self.title_font,
            title_color,
            (config.width // 2, int(config.height * 0.29)),
            shadow=COLORS["bg"],
        )
        self._text(
            f"Score {game.score}",
            self.heading_font,
            COLORS["text"],
            (config.width // 2, int(config.height * 0.42)),
        )
        if game.is_new_high:
            self._text(
                "NEW HIGH SCORE!",
                self.body_font,
                COLORS["accent"],
                (config.width // 2, int(config.height * 0.50)),
            )

        details = f"Best {game.high_score}"
        if game.stats.games_played:
            details += f"    Games {game.stats.games_played}"
        if game.stats.best_length:
            details += f"    Longest {game.stats.best_length}"
        self._text(
            details,
            self.small_font,
            COLORS["dim_text"],
            (config.width // 2, int(config.height * 0.58)),
        )
        self._text(
            "Press SPACE or ENTER to play again",
            self.body_font,
            COLORS["text"],
            (config.width // 2, int(config.height * 0.71)),
        )
        self._text(
            "ESC quits the game",
            self.small_font,
            COLORS["dim_text"],
            (config.width // 2, int(config.height * 0.80)),
        )
