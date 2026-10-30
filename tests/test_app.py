"""Smoke tests for the pygame application and the command-line interface."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

import snake
from pysnake.app import SoundBank, _handle_key, _present, run_game
from pysnake.config import DIFFICULTIES, GameConfig
from pysnake.logic import EventKind, Game, GameEvent, GameState
from pysnake.ui import Renderer, fit_rect


def use_dummy_drivers(monkeypatch) -> None:
    """Initialise SDL with dummy video/audio so tests never need a desktop."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    pygame.init()
    pygame.event.clear()


def test_run_game_shows_the_start_screen(tmp_path, monkeypatch):
    use_dummy_drivers(monkeypatch)
    config = GameConfig(data_file=tmp_path / "scores.json", sound=False)

    game = run_game(config, max_frames=5)

    assert game.state is GameState.START
    assert game.score == 0


def test_run_game_plays_until_game_over(tmp_path, monkeypatch):
    use_dummy_drivers(monkeypatch)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    # A small board reaches the wall quickly, keeping the test fast.
    config = GameConfig(cols=8, rows=8, data_file=tmp_path / "scores.json", sound=False)

    game = run_game(config, max_frames=120)

    assert game.state is GameState.GAME_OVER
    assert game.score == 0
    assert game.victory is False


def test_sound_bank_never_crashes_without_audio(monkeypatch):
    use_dummy_drivers(monkeypatch)
    bank = SoundBank(enabled=True)
    initial = bank.enabled
    result = bank.toggle()
    if bank.available:
        assert result is (not initial)
    else:
        assert result is False
    pygame.quit()


def _make_ui(tmp_path, monkeypatch):
    use_dummy_drivers(monkeypatch)
    config = GameConfig(data_file=tmp_path / "scores.json", sound=False)
    game = Game(config)
    renderer = Renderer(pygame.Surface((config.width, config.height)), config)
    sound = SoundBank(enabled=False)
    return game, renderer, sound


def test_r_key_restarts_a_live_run(tmp_path, monkeypatch):
    game, renderer, sound = _make_ui(tmp_path, monkeypatch)
    game.start()
    game.score = 40
    assert _handle_key(pygame.K_r, game, renderer, sound) is True
    assert game.state is GameState.PLAYING
    assert game.score == 0
    pygame.quit()


def test_space_starts_from_the_start_screen(tmp_path, monkeypatch):
    game, renderer, sound = _make_ui(tmp_path, monkeypatch)
    assert _handle_key(pygame.K_SPACE, game, renderer, sound) is True
    assert game.state is GameState.PLAYING
    pygame.quit()


def test_volume_keys_adjust_the_sound_bank(tmp_path, monkeypatch):
    game, renderer, sound = _make_ui(tmp_path, monkeypatch)
    sound.volume = 0.5
    assert _handle_key(pygame.K_RIGHTBRACKET, game, renderer, sound) is True
    assert sound.volume == 0.6
    assert _handle_key(pygame.K_LEFTBRACKET, game, renderer, sound) is True
    assert sound.volume == 0.5
    pygame.quit()


def test_renderer_turns_events_into_score_popups_and_toasts(tmp_path, monkeypatch):
    game, renderer, sound = _make_ui(tmp_path, monkeypatch)
    renderer.handle_events(
        [
            GameEvent(EventKind.ATE_FOOD, (1, 1), value=20, combo=2),
            GameEvent(EventKind.ACHIEVEMENT, text="first_bite"),
        ]
    )

    assert len(renderer.floating_text) == 1
    assert renderer.floating_text[0].text == "+20 x2"
    assert len(renderer.toasts) == 1
    assert "First Bite" in renderer.toasts[0].text

    game.start()
    game.combo = 2
    game.combo_ticks_left = 30
    renderer.draw(game, sound_enabled=True, volume=0.7)

    renderer.update(4.0)
    assert renderer.floating_text == []
    assert renderer.toasts == []
    pygame.quit()


def test_cli_arguments_build_a_valid_configuration():
    parser = snake.build_parser()
    args = parser.parse_args(
        [
            "--cols",
            "20",
            "--rows",
            "15",
            "--cell-size",
            "24",
            "--difficulty",
            "hard",
            "--seed",
            "42",
            "--no-grid",
            "--no-bonus",
            "--combo-window",
            "30",
            "--combo-cap",
            "4",
            "--wrap",
            "--fullscreen",
            "--mute",
            "--data-file",
            "custom-scores.json",
        ]
    )
    config = snake.config_from_args(args)

    assert config.cols == 20
    assert config.rows == 15
    assert config.cell_size == 24
    assert config.difficulty == "hard"
    assert config.difficulty_preset is DIFFICULTIES["hard"]
    assert config.seed == 42
    assert config.show_grid is False
    assert config.bonus_food is False
    assert config.combo_window == 30
    assert config.combo_multiplier_cap == 4
    assert config.wrap is True
    assert config.fullscreen is True
    assert config.sound is False
    assert config.data_file == Path("custom-scores.json")


def test_cli_rejects_an_impossible_board(capsys):
    with pytest.raises(SystemExit) as error:
        snake.main(["--cols", "2"])
    assert error.value.code == 2
    assert "columns must be between" in capsys.readouterr().err


def test_cli_help_works_without_opening_a_window(capsys):
    with pytest.raises(SystemExit) as error:
        snake.main(["--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "pure-Python Snake game" in output
    assert "--difficulty" in output
    assert "--seed" in output
    assert "--combo-window" in output
    assert "--wrap" in output
    assert "--fullscreen" in output


# ---------------------------------------------------------------------------
# Window scaling and volume
# ---------------------------------------------------------------------------


def test_fit_rect_letterboxes_and_centres_the_logical_surface():
    rect = fit_rect((1200, 800), (600, 650))
    assert (rect.width, rect.height) == (738, 800)
    assert rect.x == (1200 - 738) // 2
    assert rect.y == 0


def test_fit_rect_scales_up_a_smaller_window():
    rect = fit_rect((300, 300), (600, 650))
    assert (rect.width, rect.height) == (277, 300)
    assert rect.x == (300 - 277) // 2


def test_fit_rect_handles_a_matching_window_and_bad_sizes():
    assert fit_rect((600, 650), (600, 650)) == pygame.Rect(0, 0, 600, 650)
    assert fit_rect((0, 0), (600, 650)) == pygame.Rect(0, 0, 1, 1)


def test_present_letterboxes_scaled_content(monkeypatch):
    use_dummy_drivers(monkeypatch)
    canvas = pygame.Surface((600, 650))
    canvas.fill((10, 20, 30))
    screen = pygame.Surface((320, 240))
    screen.fill((0, 0, 0))

    _present(screen, canvas)

    # The corners are letterbox bars and the centre holds the scaled board.
    assert screen.get_at((0, 0))[:3] == (15, 15, 25)
    center = screen.get_at((160, 120))[:3]
    assert all(
        abs(channel - expected) <= 4 for channel, expected in zip(center, (10, 20, 30))
    )
    pygame.quit()


def test_sound_volume_is_clamped_and_toggle_preserves_it(monkeypatch):
    use_dummy_drivers(monkeypatch)
    bank = SoundBank(enabled=False, volume=0.8)
    assert bank.change_volume(0.5) == 1.0
    assert bank.change_volume(-10) == 0.0
    assert bank.change_volume(0.3) == 0.3
    assert bank.toggle() is bank.available
    assert bank.volume == 0.3
    pygame.quit()
