"""Automated tests for the pySnake game logic.

All tests run headlessly — no display is required.  The two smoke tests at
the bottom exercise the real pygame loop with SDL's dummy video driver.
"""

from __future__ import annotations

import json
import random

import pygame
import pytest

from snake import (
    BASE_SPEED,
    BOARD_TOP,
    GRID_HEIGHT,
    GRID_SIZE,
    GRID_WIDTH,
    HEADER_HEIGHT,
    HEIGHT,
    MAX_SPEED,
    WIDTH,
    Food,
    Game,
    GameState,
    Snake,
    load_high_score,
    save_high_score,
    speed_for_score,
)

ALL_CELLS = {(x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT)}


@pytest.fixture
def game(tmp_path) -> Game:
    """A fresh game whose high score is stored in a temporary directory."""
    return Game(high_score_path=str(tmp_path / "highscore.json"))


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def test_board_fits_below_header():
    """The play field must start under the HUD and fill the window exactly."""
    assert BOARD_TOP == HEADER_HEIGHT
    assert GRID_WIDTH * GRID_SIZE == WIDTH
    assert BOARD_TOP + GRID_HEIGHT * GRID_SIZE == HEIGHT


# ---------------------------------------------------------------------------
# Snake movement and collisions
# ---------------------------------------------------------------------------


def test_initial_layout_is_valid():
    snake = Snake()
    assert len(snake.body) == 3
    assert snake.direction == (0, -1)
    assert snake.head == (GRID_WIDTH // 2, GRID_HEIGHT // 2 - 1)
    # The neck sits directly below the head: facing up is the safe start.
    assert snake.body[1] == (snake.head[0], snake.head[1] + 1)
    assert set(snake.body) <= ALL_CELLS


def test_move_advances_head_and_keeps_length():
    snake = Snake()
    old_head = snake.head
    assert snake.move() is True
    assert snake.head == (old_head[0], old_head[1] - 1)
    assert len(snake.body) == 3


def test_grow_flag_extends_snake_once():
    snake = Snake()
    snake.grow = True
    snake.move()
    assert len(snake.body) == 4
    # The flag is consumed by a single move.
    snake.move()
    assert len(snake.body) == 4


def test_reverse_turn_is_rejected():
    snake = Snake()
    assert snake.change_direction(0, 1) is False  # 180° reversal
    assert snake.next_direction == (0, -1)


def test_non_unit_vector_is_rejected():
    snake = Snake()
    assert snake.change_direction(2, 3) is False
    assert snake.next_direction == (0, -1)


def test_valid_turn_is_queued_then_applied():
    snake = Snake()
    assert snake.change_direction(1, 0) is True
    assert snake.head == (GRID_WIDTH // 2, GRID_HEIGHT // 2 - 1)  # still queued
    old_head = snake.head
    snake.move()
    assert snake.direction == (1, 0)
    assert snake.head == (old_head[0] + 1, old_head[1])


def test_rapid_turns_cannot_kill_the_snake():
    """Reversals stay refused no matter how keys are spammed inside a tick."""
    snake = Snake()
    assert snake.change_direction(0, 1) is False  # reverse of heading (up)
    assert snake.change_direction(1, 0) is True  # queue a legal turn
    assert snake.change_direction(0, 1) is False  # still heading up → refused
    assert snake.next_direction == (1, 0)  # the queued turn survives the spam
    assert snake.move() is True
    assert len(set(snake.body)) == len(snake.body)


def test_input_spam_never_creates_self_overlap():
    """Property test: random turn spam may kill on walls, never on itself."""
    rng = random.Random(42)
    snake = Snake()
    turns = [(0, -1), (0, 1), (-1, 0), (1, 0)]
    for _ in range(500):
        snake.change_direction(*rng.choice(turns))
        if not snake.move():
            snake.reset()
        else:
            assert len(set(snake.body)) == len(snake.body)


def test_wall_collision_is_detected():
    snake = Snake()
    snake.body = [(0, 0), (1, 0), (2, 0)]
    snake.direction = snake.next_direction = (-1, 0)
    assert snake.move() is False


def test_body_collision_is_detected():
    """Running into a non-tail body segment ends the move."""
    snake = Snake()
    snake.body = [(0, 0), (0, 1), (1, 1), (1, 0), (2, 0)]
    snake.direction = snake.next_direction = (1, 0)
    assert snake.move() is False  # (1, 0) is body[3], not the vacating tail


def test_moving_into_vacating_tail_is_allowed():
    """Following your own tail is legal — the tail moves away first."""
    snake = Snake()
    snake.body = [(1, 0), (1, 1), (0, 1), (0, 0)]
    snake.direction = snake.next_direction = (-1, 0)
    assert snake.move() is True
    assert len(snake.body) == 4
    assert len(set(snake.body)) == 4  # no duplicated cells


# ---------------------------------------------------------------------------
# Food
# ---------------------------------------------------------------------------


def test_food_avoids_occupied_cells():
    food = Food()
    only_free = (3, 4)
    assert food.spawn(ALL_CELLS - {only_free}) is True
    assert food.position == only_free


def test_food_spawn_fails_on_full_board():
    food = Food()
    assert food.spawn(ALL_CELLS) is False


def test_initial_food_not_under_the_snake():
    snake = Snake()
    food = Food(snake.body)
    assert food.position not in snake.body


# ---------------------------------------------------------------------------
# Difficulty
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, BASE_SPEED),
        (49, BASE_SPEED),
        (50, BASE_SPEED + 2),
        (100, BASE_SPEED + 4),
        (500, MAX_SPEED),
        (10_000, MAX_SPEED),
    ],
)
def test_speed_increases_with_score(score, expected):
    assert speed_for_score(score) == expected


def test_speed_never_exceeds_cap():
    assert speed_for_score(10_000) <= MAX_SPEED


# ---------------------------------------------------------------------------
# High score persistence
# ---------------------------------------------------------------------------


def test_high_score_roundtrip(tmp_path):
    path = str(tmp_path / "hs.json")
    save_high_score(120, path)
    assert load_high_score(path) == 120


def test_missing_high_score_file_returns_zero(tmp_path):
    assert load_high_score(str(tmp_path / "missing.json")) == 0


def test_corrupt_high_score_file_returns_zero(tmp_path):
    path = tmp_path / "hs.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_high_score(str(path)) == 0


def test_invalid_high_score_values_are_clamped(tmp_path):
    path = tmp_path / "hs.json"
    path.write_text(json.dumps({"high_score": "not-a-number"}), encoding="utf-8")
    assert load_high_score(str(path)) == 0
    path.write_text(json.dumps({"high_score": -5}), encoding="utf-8")
    assert load_high_score(str(path)) == 0


# ---------------------------------------------------------------------------
# Game state machine
# ---------------------------------------------------------------------------


def test_game_starts_on_accepted_direction(game):
    assert game.state is GameState.START
    game.handle_key(pygame.K_UP)
    assert game.state is GameState.PLAYING
    assert game.snake.direction == (0, -1)


def test_game_does_not_start_with_down_key(game):
    """Regression: starting downwards used to kill the snake instantly."""
    head_before = game.snake.head
    game.handle_key(pygame.K_DOWN)
    assert game.state is GameState.START
    assert game.snake.head == head_before
    # Another direction still starts the game (applied on the first move).
    game.handle_key(pygame.K_a)
    assert game.state is GameState.PLAYING
    assert game.snake.next_direction == (-1, 0)


def test_unknown_key_is_ignored(game):
    game.handle_key(pygame.K_q)
    assert game.state is GameState.START


def test_pause_and_resume_with_p(game):
    game.handle_key(pygame.K_UP)
    game.handle_key(pygame.K_p)
    assert game.state is GameState.PAUSED

    head_before = game.snake.head
    game.tick()  # ticks while paused must not move the snake
    assert game.snake.head == head_before

    game.handle_key(pygame.K_p)
    assert game.state is GameState.PLAYING


def test_direction_key_resumes_from_pause(game):
    game.handle_key(pygame.K_UP)
    game.handle_key(pygame.K_p)
    assert game.state is GameState.PAUSED
    game.handle_key(pygame.K_d)
    assert game.state is GameState.PLAYING
    assert game.snake.next_direction == (1, 0)


def test_scoring_growth_and_particles(game):
    game.handle_key(pygame.K_UP)
    head_x, head_y = game.snake.head
    game.food.position = (head_x, head_y - 1)  # directly in the path

    game.tick()
    assert game.score == 10
    assert game.snake.grow is True  # growth is applied on the next move
    assert game.food.position not in game.snake.body
    assert len(game.particles) == 12  # eat burst

    game.tick()
    assert len(game.snake.body) == 4  # the body extended here

    game.update_particles()
    assert all(p.life < 1.0 for p in game.particles)


def test_speed_property_follows_score(game):
    game.handle_key(pygame.K_UP)
    assert game.speed == BASE_SPEED
    game.score = 50
    assert game.speed == BASE_SPEED + 2


def test_game_over_on_wall_hit(game):
    game.handle_key(pygame.K_UP)
    while game.state is GameState.PLAYING:
        game.tick()
    assert game.state is GameState.GAME_OVER
    assert game.victory is False


def test_high_score_saved_on_game_over(tmp_path):
    path = str(tmp_path / "hs.json")
    game = Game(high_score_path=path)
    game.handle_key(pygame.K_UP)
    game.score = 30
    while game.state is GameState.PLAYING:
        game.tick()
    assert game.is_new_high is True
    assert game.high_score == 30
    assert load_high_score(path) == 30


def test_restart_after_game_over(game):
    game.handle_key(pygame.K_UP)
    while game.state is GameState.PLAYING:
        game.tick()
    game.handle_key(pygame.K_SPACE)
    assert game.state is GameState.PLAYING
    assert game.score == 0
    assert len(game.snake.body) == 3
    assert game.victory is False
    assert game.food.position not in game.snake.body


def test_victory_when_board_fills_up(game, monkeypatch):
    game.handle_key(pygame.K_UP)
    head_x, head_y = game.snake.head
    game.food.position = (head_x, head_y - 1)
    monkeypatch.setattr(game.food, "spawn", lambda occupied=(): False)
    game.tick()
    assert game.state is GameState.GAME_OVER
    assert game.victory is True


# ---------------------------------------------------------------------------
# Smoke tests: the real pygame loop on SDL's dummy video driver
# ---------------------------------------------------------------------------


def _use_dummy_display(monkeypatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.event.clear()  # drop events left over from other tests


def test_main_shows_start_screen(monkeypatch):
    from snake import main

    _use_dummy_display(monkeypatch)
    game = main(max_frames=30)
    assert game.state is GameState.START
    assert game.score == 0


def test_main_runs_a_full_game_until_game_over(monkeypatch):
    from snake import main

    _use_dummy_display(monkeypatch)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    game = main(max_frames=40)
    # Driving straight up from the centre reaches the wall, then the game
    # sits on the game-over screen for the remaining frames.
    assert game.state is GameState.GAME_OVER
    assert game.score == 0
