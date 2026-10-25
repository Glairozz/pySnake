"""Smoke tests for the pygame application and the command-line interface."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

import snake
from pysnake.app import SoundBank, run_game
from pysnake.config import DIFFICULTIES, GameConfig
from pysnake.logic import GameState


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
