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
    COLORS,
    MAX_FRAME_TIME,
    RENDER_FPS,
    GameConfig,
)
from .logic import EventKind, Game, GameEvent, GameState
from .ui import Renderer, fit_rect

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
}

VOLUME_STEP = 0.1
VOLUME_DOWN_KEYS = {pygame.K_LEFTBRACKET, pygame.K_MINUS, pygame.K_KP_MINUS}
VOLUME_UP_KEYS = {
    pygame.K_RIGHTBRACKET,
    getattr(pygame, "K_PLUS", pygame.K_EQUALS),
    pygame.K_EQUALS,
    pygame.K_KP_PLUS,
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
        EventKind.ACHIEVEMENT: (1568.0, 0.16, 0.22),
        EventKind.GAME_OVER: (190.0, 0.30, 0.24),
        EventKind.VICTORY: (990.0, 0.25, 0.24),
    }

    def __init__(self, enabled: bool = True, volume: float = 0.8) -> None:
        self.enabled = False
        self.available = False
        self.volume = max(0.0, min(1.0, volume))
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
            self._apply_volume()
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

    def _apply_volume(self) -> None:
        for sound in self._sounds.values():
            sound.set_volume(self.volume)

    def change_volume(self, delta: float) -> float:
        """Adjust the effect volume, clamped to 0..1, and return it."""
        self.volume = max(0.0, min(1.0, round(self.volume + delta, 2)))
        self._apply_volume()
        return self.volume

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
    elif key == pygame.K_r:
        if game.state is GameState.GAME_OVER:
            game.restart()
        elif game.state in (GameState.PLAYING, GameState.PAUSED):
            game.restart_run()
    elif key in RESTART_KEYS:
        if game.state is GameState.GAME_OVER:
            game.restart()
        elif game.state is GameState.START:
            game.start()
    elif key in DIFFICULTY_KEYS and game.state is GameState.START:
        game.set_difficulty(DIFFICULTY_KEYS[key])
    elif key == pygame.K_g:
        renderer.grid_visible = not renderer.grid_visible
    elif key == pygame.K_m:
        sound.toggle()
    elif key in VOLUME_DOWN_KEYS:
        sound.change_volume(-VOLUME_STEP)
    elif key in VOLUME_UP_KEYS:
        sound.change_volume(VOLUME_STEP)
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


def _open_window(config: GameConfig, fullscreen: bool) -> pygame.Surface:
    """Create the display surface, either windowed or fullscreen."""
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    return pygame.display.set_mode((config.width, config.height), pygame.RESIZABLE)


def _present(screen: pygame.Surface, canvas: pygame.Surface) -> None:
    """Scale *canvas* into *screen*, keeping the aspect ratio and centring it."""
    window_size = screen.get_size()
    rect = fit_rect(window_size, canvas.get_size())
    if rect.size == canvas.get_size():
        screen.blit(canvas, rect)
        return
    screen.fill(COLORS["bg"])
    screen.blit(pygame.transform.smoothscale(canvas, rect.size), rect)


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
    fullscreen = config.fullscreen
    try:
        pygame.init()
        screen = _open_window(config, fullscreen)
    except pygame.error as exc:
        pygame.quit()
        raise SystemExit(
            f"Unable to open a display: {exc}\n"
            "pySnake needs a desktop session. On a headless machine set "
            "SDL_VIDEODRIVER=dummy for automated tests."
        ) from exc

    mode = "wrap" if config.wrap else "classic"
    pygame.display.set_caption(
        f"pySnake - {config.difficulty_preset.label.title()} "
        f"({config.cols}x{config.rows}, {mode})"
    )
    game = Game(config)
    # The game always renders at its logical size; the window scales that
    # surface with a preserved aspect ratio, so resizing stays crisp and the
    # HUD layout never has to change.
    canvas = pygame.Surface((config.width, config.height))
    renderer = Renderer(canvas, config)
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
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    screen = _open_window(config, fullscreen)
                elif event.type == pygame.KEYDOWN:
                    if not _handle_key(event.key, game, renderer, sound):
                        running = False
                elif event.type == pygame.VIDEORESIZE and not fullscreen:
                    size = (max(320, event.w), max(240, event.h))
                    screen = pygame.display.set_mode(size, pygame.RESIZABLE)
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
            renderer.draw(
                game,
                sound_enabled=sound.enabled,
                volume=sound.volume,
            )
            _present(screen, canvas)
            pygame.display.flip()

            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
    finally:
        # Never lose a record score just because the window was closed mid-run.
        game.abandon()
        pygame.quit()

    return game
