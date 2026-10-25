"""Pygame application loop, keyboard handling and generated sound effects.

The loop renders at a steady :data:`pysnake.config.RENDER_FPS` while the rules
advance on a separate fixed-tick schedule.  This keeps snake movement
consistent even if the display frame rate fluctuates, and keeps menus and
particles smooth.
"""

from __future__ import annotations

import array
import math
from typing import ClassVar

import pygame

from .config import (
    MAX_FRAME_TIME,
    RENDER_FPS,
    GameConfig,
)
from .logic import EventKind, Game, GameEvent, GameState
from .ui import Renderer

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

RESTART_KEYS = {
    pygame.K_SPACE,
    pygame.K_RETURN,
    pygame.K_r,
}

DIFFICULTY_KEYS = {
    pygame.K_1: "easy",
    pygame.K_KP1: "easy",
    pygame.K_2: "normal",
    pygame.K_KP2: "normal",
    pygame.K_3: "hard",
    pygame.K_KP3: "hard",
}


# ---------------------------------------------------------------------------
# Sound
# ---------------------------------------------------------------------------


class SoundBank:
    """Tiny synthesised sound effects; silently disabled when audio is absent."""

    _FREQUENCIES: ClassVar[dict[EventKind, tuple[float, float, float]]] = {
        # kind: (frequency Hz, duration seconds, volume 0..1)
        EventKind.STARTED: (660.0, 0.06, 0.18),
        EventKind.ATE_FOOD: (880.0, 0.07, 0.22),
        EventKind.ATE_BONUS: (1320.0, 0.12, 0.24),
        EventKind.BONUS_EXPIRED: (260.0, 0.07, 0.10),
        EventKind.PAUSED: (520.0, 0.05, 0.16),
        EventKind.RESUMED: (620.0, 0.05, 0.16),
        EventKind.NEW_HIGH_SCORE: (1046.0, 0.18, 0.24),
        EventKind.GAME_OVER: (190.0, 0.30, 0.24),
        EventKind.VICTORY: (990.0, 0.25, 0.24),
    }

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = False
        self.available = False
        self._sounds: dict[EventKind, pygame.mixer.Sound] = {}
        self._build()
        self.enabled = enabled and self.available

    def _build(self) -> None:
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            mixer_settings = pygame.mixer.get_init()
            if mixer_settings is None:
                raise pygame.error("mixer unavailable")
            _, sample_format, _ = mixer_settings
            if sample_format != -16:
                raise pygame.error("unsupported audio format")
            self._sounds = {
                kind: self._tone(frequency, duration, volume)
                for kind, (frequency, duration, volume) in self._FREQUENCIES.items()
            }
            self.available = True
        except (pygame.error, OSError, ValueError):
            self.enabled = False
            self.available = False
            self._sounds.clear()

    @staticmethod
    def _tone(frequency: float, duration: float, volume: float) -> pygame.mixer.Sound:
        """Generate a short sine tone with a simple attack/decay envelope."""
        settings = pygame.mixer.get_init()
        if settings is None:
            raise pygame.error("mixer unavailable")
        sample_rate, _, channels = settings
        frame_count = max(1, int(sample_rate * duration))
        samples = array.array("h")
        for index in range(frame_count):
            progress = index / frame_count
            attack = min(1.0, progress / 0.06)
            envelope = attack * (1.0 - progress) ** 1.6
            value = int(
                32767
                * volume
                * envelope
                * math.sin(math.tau * frequency * index / sample_rate)
            )
            for _ in range(channels):
                samples.append(value)
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def toggle(self) -> bool:
        """Toggle muting and return the new enabled state."""
        if not self.available:
            self.enabled = False
            return False
        self.enabled = not self.enabled
        return self.enabled

    def handle_events(self, events: list[GameEvent]) -> None:
        """Play a sound for each relevant game event."""
        if not self.enabled:
            return
        for event in events:
            sound = self._sounds.get(event.kind)
            if sound is not None:
                sound.play()


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


def _handle_key(
    key: int,
    game: Game,
    renderer: Renderer,
    sound: SoundBank,
) -> bool:
    """Apply one key press; return False when the game should quit."""
    if key == pygame.K_ESCAPE:
        return False

    direction = DIRECTION_KEYS.get(key)
    if direction is not None:
        game.turn(direction)
        return True

    if key == pygame.K_p:
        game.toggle_pause()
    elif key in RESTART_KEYS and game.state is GameState.GAME_OVER:
        game.restart()
    elif key in DIFFICULTY_KEYS and game.state is GameState.START:
        game.set_difficulty(DIFFICULTY_KEYS[key])
    elif key == pygame.K_g:
        renderer.grid_visible = not renderer.grid_visible
    elif key == pygame.K_m:
        sound.toggle()
    return True


def _advance_game(game: Game, dt: float, accumulator: float) -> float:
    """Run as many fixed ticks as *dt* allows, returning the new accumulator."""
    accumulator += dt
    interval = 1.0 / game.speed
    while accumulator >= interval and game.state is GameState.PLAYING:
        game.tick()
        accumulator -= interval
        interval = 1.0 / game.speed
    if game.state is not GameState.PLAYING:
        return 0.0
    return accumulator


def run_game(
    config: GameConfig | None = None,
    max_frames: int | None = None,
) -> Game:
    """Open a window and play until closed (or *max_frames* frames elapse).

    Returns the final :class:`Game`, which lets automated smoke tests inspect
    the result of a real loop.
    """
    config = config or GameConfig()
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=512)
    try:
        pygame.init()
        screen = pygame.display.set_mode((config.width, config.height))
    except pygame.error as exc:
        pygame.quit()
        raise SystemExit(
            f"Unable to open a display: {exc}\n"
            "pySnake needs a desktop session. On a headless machine set "
            "SDL_VIDEODRIVER=dummy for automated tests."
        ) from exc

    pygame.display.set_caption(
        f"pySnake - {config.difficulty_preset.label.title()} "
        f"({config.cols}x{config.rows})"
    )
    game = Game(config)
    renderer = Renderer(screen, config)
    sound = SoundBank(config.sound)
    clock = pygame.time.Clock()

    running = True
    frames = 0
    accumulator = 0.0
    focus_lost_event = getattr(pygame, "WINDOWFOCUSLOST", None)

    try:
        while running:
            dt = min(clock.tick(RENDER_FPS) / 1000.0, MAX_FRAME_TIME)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if not _handle_key(event.key, game, renderer, sound):
                        running = False
                elif (
                    focus_lost_event is not None
                    and event.type == focus_lost_event
                    and game.state is GameState.PLAYING
                ):
                    game.toggle_pause()
            if not running:
                break

            if game.state is GameState.PLAYING:
                accumulator = _advance_game(game, dt, accumulator)
            else:
                accumulator = 0.0

            events = game.drain_events()
            renderer.handle_events(events)
            sound.handle_events(events)
            renderer.update(dt)
            renderer.draw(game, sound_enabled=sound.enabled)
            pygame.display.flip()

            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
    finally:
        # Never lose a record score just because the window was closed mid-run.
        game.abandon()
        pygame.quit()

    return game
