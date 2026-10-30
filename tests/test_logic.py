"""Tests for pySnake's display-independent game rules."""

from __future__ import annotations

import random

import pytest

from pysnake.config import (
    DIFFICULTIES,
    MAX_QUEUED_TURNS,
    GameConfig,
    speed_for_score,
)
from pysnake.logic import (
    DIRECTIONS,
    BonusFood,
    EventKind,
    Food,
    Game,
    GameState,
    Snake,
    free_cells,
    random_free_cell,
)
from pysnake.storage import Stats, load_stats

SMALL_BOARD = GameConfig(cols=12, rows=12, seed=7)


def make_config(tmp_path, **overrides) -> GameConfig:
    settings = {
        "cols": 12,
        "rows": 12,
        "seed": 7,
        "data_file": tmp_path / "highscore.json",
    }
    settings.update(overrides)
    return GameConfig(**settings)


def place_snake(
    snake: Snake,
    body: list[tuple[int, int]],
    direction: tuple[int, int],
) -> None:
    """Put a snake in an exact position for collision tests."""
    snake.body = list(body)
    snake.direction = direction
    snake._pending.clear()
    snake.grow = False


# ---------------------------------------------------------------------------
# Snake movement
# ---------------------------------------------------------------------------


def test_initial_layout_is_valid():
    snake = Snake(SMALL_BOARD)
    assert len(snake.body) == SMALL_BOARD.start_length
    assert snake.direction == (0, -1)
    assert snake.head == (SMALL_BOARD.cols // 2, SMALL_BOARD.rows // 2 - 1)
    assert snake.body[1] == (snake.head[0], snake.head[1] + 1)
    assert len(set(snake.body)) == len(snake.body)


def test_small_board_has_a_valid_starting_snake():
    config = GameConfig(cols=8, rows=8)
    snake = Snake(config)
    assert len(set(snake.body)) == len(snake.body)
    assert all(0 <= x < config.cols and 0 <= y < config.rows for x, y in snake.body)


def test_snake_moves_up_by_default():
    snake = Snake(SMALL_BOARD)
    old_head = snake.head
    assert snake.move() is True
    assert snake.head == (old_head[0], old_head[1] - 1)
    assert len(snake.body) == SMALL_BOARD.start_length


def test_snake_can_move_in_every_direction():
    snake = Snake(SMALL_BOARD)
    old_head = snake.head

    assert snake.move() is True
    assert snake.head == (old_head[0], old_head[1] - 1)

    assert snake.change_direction(1, 0) is True
    assert snake.move() is True
    assert snake.head == (old_head[0] + 1, old_head[1] - 1)

    assert snake.change_direction(0, 1) is True
    assert snake.move() is True
    assert snake.head == (old_head[0] + 1, old_head[1])

    assert snake.change_direction(-1, 0) is True
    assert snake.move() is True
    assert snake.head == (old_head[0], old_head[1])


def test_two_quick_turns_are_queued_for_consecutive_ticks():
    snake = Snake(SMALL_BOARD)
    start = snake.head
    assert snake.change_direction(1, 0) is True  # right
    assert snake.change_direction(0, 1) is True  # then down
    assert snake.next_direction == (0, 1)

    assert snake.move() is True
    assert snake.head == (start[0] + 1, start[1])
    assert snake.move() is True
    assert snake.head == (start[0] + 1, start[1] + 1)


def test_turn_queue_has_a_safe_limit():
    snake = Snake(SMALL_BOARD)
    assert snake.change_direction(1, 0) is True
    assert snake.change_direction(0, 1) is True
    assert snake.change_direction(-1, 0) is False
    assert len(snake._pending) == MAX_QUEUED_TURNS


def test_reverse_turn_is_rejected():
    snake = Snake(SMALL_BOARD)
    assert snake.change_direction(0, 1) is False
    assert snake.next_direction == (0, -1)


def test_reverse_of_a_queued_turn_is_rejected():
    snake = Snake(SMALL_BOARD)
    assert snake.change_direction(1, 0) is True  # queue a right turn
    # Left is a reversal of the *queued* heading, even though it is not a
    # reversal of the current (up) heading.
    assert snake.change_direction(-1, 0) is False
    assert snake.next_direction == (1, 0)


def test_same_direction_is_not_queued_again():
    snake = Snake(SMALL_BOARD)
    assert snake.change_direction(0, -1) is False
    assert len(snake._pending) == 0


def test_non_unit_direction_is_rejected():
    snake = Snake(SMALL_BOARD)
    for direction in [(2, 3), (0, 0), (1, 1), (0.5, -1)]:
        assert snake.change_direction(*direction) is False
    assert snake.next_direction == (0, -1)


@pytest.mark.parametrize("direction", sorted(DIRECTIONS))
def test_wall_collision_is_detected_in_every_direction(direction):
    snake = Snake(SMALL_BOARD)
    col, row = SMALL_BOARD.cols // 2, SMALL_BOARD.rows // 2
    head = (
        0
        if direction == (-1, 0)
        else SMALL_BOARD.cols - 1
        if direction == (1, 0)
        else col,
        0
        if direction == (0, -1)
        else SMALL_BOARD.rows - 1
        if direction == (0, 1)
        else row,
    )
    dx, dy = direction
    # Build a short body behind the head so only the wall matters.
    body = [head, (head[0] - dx, head[1] - dy), (head[0] - 2 * dx, head[1] - 2 * dy)]
    place_snake(snake, body, direction)
    assert snake.move() is False


def test_body_collision_is_detected():
    snake = Snake(SMALL_BOARD)
    place_snake(
        snake,
        [(0, 0), (0, 1), (1, 1), (1, 0), (2, 0)],
        (1, 0),
    )
    assert snake.move() is False  # (1, 0) is body[3], not the vacating tail


def test_moving_into_the_vacating_tail_is_allowed():
    snake = Snake(SMALL_BOARD)
    place_snake(snake, [(1, 0), (1, 1), (0, 1), (0, 0)], (-1, 0))
    assert snake.move() is True
    assert len(snake.body) == 4
    assert len(set(snake.body)) == 4


def test_growing_snake_does_not_exempt_the_tail():
    snake = Snake(SMALL_BOARD)
    place_snake(snake, [(1, 0), (1, 1), (0, 1), (0, 0)], (-1, 0))
    snake.grow = True
    assert snake.move() is False
    assert len(snake.body) == 4
    assert snake.grow is True


def test_growth_flag_extends_the_snake_once():
    snake = Snake(SMALL_BOARD)
    snake.grow = True
    snake.move()
    assert len(snake.body) == SMALL_BOARD.start_length + 1
    snake.move()
    assert len(snake.body) == SMALL_BOARD.start_length + 1


def test_input_spam_never_creates_self_overlap():
    rng = random.Random(42)
    snake = Snake(SMALL_BOARD)
    for _ in range(500):
        snake.change_direction(*rng.choice(tuple(DIRECTIONS)))
        if not snake.move():
            snake.reset()
        else:
            assert len(set(snake.body)) == len(snake.body)


# ---------------------------------------------------------------------------
# Wrap-around mode
# ---------------------------------------------------------------------------


def test_wrap_mode_crosses_the_side_walls():
    config = GameConfig(cols=12, rows=12, wrap=True)
    snake = Snake(config)
    place_snake(snake, [(0, 5), (1, 5), (2, 5)], (-1, 0))
    assert snake.move() is True
    assert snake.head == (11, 5)

    place_snake(snake, [(11, 5), (10, 5), (9, 5)], (1, 0))
    assert snake.move() is True
    assert snake.head == (0, 5)


def test_wrap_mode_crosses_the_top_and_bottom_walls():
    config = GameConfig(cols=12, rows=12, wrap=True)
    snake = Snake(config)
    place_snake(snake, [(5, 0), (5, 1), (5, 2)], (0, -1))
    assert snake.move() is True
    assert snake.head == (5, 11)

    place_snake(snake, [(5, 11), (5, 10), (5, 9)], (0, 1))
    assert snake.move() is True
    assert snake.head == (5, 0)


def test_wrap_mode_still_detects_self_collisions():
    config = GameConfig(cols=12, rows=12, wrap=True)
    snake = Snake(config)
    place_snake(snake, [(0, 5), (11, 5), (10, 5)], (-1, 0))
    assert snake.move() is False


def test_wrap_is_opt_in():
    snake = Snake(GameConfig(cols=12, rows=12))
    place_snake(snake, [(0, 5), (1, 5), (2, 5)], (-1, 0))
    assert snake.move() is False


# ---------------------------------------------------------------------------
# Food and free-cell helpers
# ---------------------------------------------------------------------------


def test_food_avoids_occupied_cells():
    food = Food(SMALL_BOARD, random.Random(1))
    only_free = (3, 4)
    occupied = set(free_cells(SMALL_BOARD.cols, SMALL_BOARD.rows, [])) - {only_free}
    assert food.spawn(occupied) is True
    assert food.position == only_free


def test_food_spawn_fails_on_a_full_board():
    food = Food(SMALL_BOARD)
    occupied = free_cells(SMALL_BOARD.cols, SMALL_BOARD.rows, [])
    assert food.spawn(occupied) is False


def test_initial_food_is_not_under_the_snake(tmp_path):
    game = Game(make_config(tmp_path))
    assert game.food.position not in game.snake.body


def test_food_spawning_is_reproducible_with_a_seed():
    first = Food(SMALL_BOARD, random.Random(123))
    second = Food(SMALL_BOARD, random.Random(123))
    assert first.position == second.position


def test_random_free_cell_returns_none_when_full():
    occupied = free_cells(SMALL_BOARD.cols, SMALL_BOARD.rows, [])
    assert (
        random_free_cell(SMALL_BOARD.cols, SMALL_BOARD.rows, occupied, random.Random())
        is None
    )


def test_free_cells_excludes_occupied_cells():
    cells = free_cells(2, 2, [(0, 0), (1, 1)])
    assert cells == [(1, 0), (0, 1)]


# ---------------------------------------------------------------------------
# Scoring, bonus food and events
# ---------------------------------------------------------------------------


def test_eating_regular_food_updates_score_and_emits_event(tmp_path):
    game = Game(make_config(tmp_path))
    game.start()
    game.drain_events()
    head_x, head_y = game.snake.head
    game.food.position = (head_x, head_y - 1)

    game.tick()

    assert game.score == game.difficulty.points_per_food
    assert game.foods_eaten == 1
    assert game.snake.grow is True
    assert game.food.position not in game.snake.body
    events = game.drain_events()
    assert [event.kind for event in events] == [
        EventKind.ATE_FOOD,
        EventKind.ACHIEVEMENT,
    ]
    food_event = events[0]
    assert food_event.position == (head_x, head_y - 1)
    assert food_event.value == game.difficulty.points_per_food
    assert food_event.combo == 1
    assert events[1].text == "first_bite"


def test_eating_grows_the_snake_on_the_following_move(tmp_path):
    game = Game(make_config(tmp_path))
    game.start()
    head_x, head_y = game.snake.head
    game.food.position = (head_x, head_y - 1)
    game.tick()
    assert len(game.snake.body) == game.config.start_length

    game.tick()
    assert len(game.snake.body) == game.config.start_length + 1


def test_bonus_food_spawns_every_n_foods_and_avoids_the_board_occupants(tmp_path):
    config = make_config(tmp_path, bonus_every=2, bonus_lifetime=5)
    game = Game(config)
    game.start()

    for _ in range(2):
        head_x, head_y = game.snake.head
        game.food.position = (head_x, head_y - 1)
        game.tick()

    assert game.bonus is not None
    assert game.bonus.ticks_left == 5
    assert game.bonus.position not in game.snake.body
    assert game.bonus.position != game.food.position


def test_bonus_food_can_be_eaten_for_extra_points(tmp_path):
    config = make_config(tmp_path, bonus_every=1, bonus_points=30)
    game = Game(config)
    game.start()
    head_x, head_y = game.snake.head
    game.food.position = (head_x, head_y - 1)
    game.tick()
    game.drain_events()
    assert game.bonus is not None

    game.food.position = (0, 0)
    game.bonus.position = (game.snake.head[0], game.snake.head[1] - 1)
    game.tick()

    assert game.score == game.difficulty.points_per_food + 30
    assert game.bonus is None
    assert game.snake.grow is True
    assert [event.kind for event in game.drain_events()] == [EventKind.ATE_BONUS]


def test_bonus_food_expires(tmp_path):
    config = make_config(tmp_path, bonus_every=1, bonus_lifetime=5)
    game = Game(config)
    game.start()
    head_x, head_y = game.snake.head
    game.food.position = (head_x, head_y - 1)
    game.tick()
    game.drain_events()
    assert game.bonus is not None

    game.food.position = (0, 0)
    game.bonus.position = (config.cols - 1, config.rows - 1)
    game.bonus.ticks_left = 1
    game.tick()

    assert game.bonus is None
    assert [event.kind for event in game.drain_events()] == [EventKind.BONUS_EXPIRED]


def test_bonus_food_can_be_disabled(tmp_path):
    config = make_config(tmp_path, bonus_every=1, bonus_food=False)
    game = Game(config)
    game.start()
    head_x, head_y = game.snake.head
    game.food.position = (head_x, head_y - 1)
    game.tick()
    assert game.bonus is None


def test_drain_events_clears_the_queue(tmp_path):
    game = Game(make_config(tmp_path))
    game.start()
    assert game.drain_events()
    assert game.drain_events() == []


# ---------------------------------------------------------------------------
# Combos
# ---------------------------------------------------------------------------


def _eat_ahead(game: Game) -> None:
    head_x, head_y = game.snake.head
    game.food.position = (head_x, head_y - 1)
    game.tick()


def test_combo_scoring_escalates_and_caps(tmp_path):
    config = make_config(tmp_path, combo_window=10, combo_multiplier_cap=3)
    game = Game(config)
    game.start()
    game.drain_events()

    scores = []
    for _ in range(4):
        _eat_ahead(game)
        scores.append(game.score)

    assert scores == [10, 30, 60, 90]
    assert game.combo == 4
    assert game.max_combo == 4
    assert game.combo_multiplier == 3


def test_combo_expires_after_the_window(tmp_path):
    config = make_config(tmp_path, combo_window=3)
    game = Game(config)
    game.start()
    _eat_ahead(game)
    assert game.combo == 1

    game.food.position = (0, 0)
    for _ in range(3):
        game.tick()

    assert game.combo == 0
    assert game.combo_multiplier == 0


def test_combo_resets_when_the_window_runs_out_before_the_next_food(tmp_path):
    config = make_config(tmp_path, combo_window=2)
    game = Game(config)
    game.start()
    _eat_ahead(game)
    game.food.position = (0, 0)
    game.tick()
    game.tick()
    assert game.combo == 0

    _eat_ahead(game)
    assert game.combo == 1
    assert game.score == 20


def test_bonus_food_does_not_break_a_combo(tmp_path):
    config = make_config(tmp_path, bonus_every=1, combo_window=10)
    game = Game(config)
    game.start()
    _eat_ahead(game)
    assert game.bonus is not None
    assert game.combo == 1

    head_x, head_y = game.snake.head
    game.food.position = (0, 0)
    game.bonus.position = (head_x, head_y - 1)
    game.tick()

    assert game.combo == 1
    assert game.bonus_eaten == 1


def test_combo_event_reports_awarded_points_and_multiplier(tmp_path):
    config = make_config(tmp_path, combo_window=10)
    game = Game(config)
    game.start()
    _eat_ahead(game)
    game.drain_events()
    _eat_ahead(game)

    food_event = next(
        event for event in game.drain_events() if event.kind is EventKind.ATE_FOOD
    )
    assert food_event.value == 20
    assert food_event.combo == 2


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------


def test_first_food_unlocks_and_persists_an_achievement(tmp_path):
    config = make_config(tmp_path)
    game = Game(config)
    game.start()
    game.drain_events()
    _eat_ahead(game)

    assert "first_bite" in game.stats.achievements
    assert "first_bite" in load_stats(config.data_file).achievements
    kinds = [event.kind for event in game.drain_events()]
    assert EventKind.ACHIEVEMENT in kinds


def test_combo_master_unlocks_at_the_cap(tmp_path):
    config = make_config(tmp_path, combo_window=10, combo_multiplier_cap=3)
    game = Game(config)
    game.start()
    for _ in range(3):
        _eat_ahead(game)

    assert "combo_master" in game.stats.achievements


def test_score_length_and_wrap_achievements(tmp_path):
    config = make_config(tmp_path, wrap=True)
    game = Game(config)
    game.start()
    game.score = 99
    _eat_ahead(game)
    assert "century" in game.stats.achievements

    place_snake(
        game.snake,
        [(0, 0)] + [(x, 0) for x in range(1, 12)] + [(11, 1), (10, 1), (9, 1)],
        (0, 1),
    )
    game.tick()
    assert "long_body" in game.stats.achievements

    place_snake(game.snake, [(0, 5), (1, 5), (2, 5)], (-1, 0))
    game.tick()
    assert "wrap_walker" in game.stats.achievements


def test_survivor_achievement_unlocks_on_the_move_threshold(tmp_path):
    game = Game(make_config(tmp_path))
    game.start()
    game.moves = 499
    game.tick()
    assert "survivor" in game.stats.achievements


def test_bonus_hunter_achievement_needs_three_golden_foods(tmp_path):
    game = Game(make_config(tmp_path, bonus_every=1, combo_window=10))
    game.start()
    game.bonus_eaten = 2
    head_x, head_y = game.snake.head
    game.food.position = (0, 0)
    game.bonus = BonusFood((head_x, head_y - 1), 10)
    game.tick()
    assert game.bonus_eaten == 3
    assert "bonus_hunter" in game.stats.achievements


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def test_game_starts_on_the_start_screen(tmp_path):
    game = Game(make_config(tmp_path))
    assert game.state is GameState.START
    assert game.score == 0


def test_start_with_direction_and_reject_down_reversal(tmp_path):
    game = Game(make_config(tmp_path))
    assert game.start((0, 1)) is False  # snake initially faces up
    assert game.state is GameState.START
    assert game.start((0, -1)) is True
    assert game.state is GameState.PLAYING
    assert game.snake.next_direction == (0, -1)


def test_turn_starts_the_game_from_the_start_screen(tmp_path):
    game = Game(make_config(tmp_path))
    assert game.turn((-1, 0)) is True
    assert game.state is GameState.PLAYING
    assert game.snake.next_direction == (-1, 0)


def test_pause_stops_ticks_and_direction_resumes(tmp_path):
    game = Game(make_config(tmp_path))
    game.start()
    assert game.toggle_pause() is True
    assert game.state is GameState.PAUSED
    head_before = game.snake.head
    game.tick()
    assert game.snake.head == head_before

    assert game.turn((1, 0)) is True
    assert game.state is GameState.PLAYING
    assert game.snake.next_direction == (1, 0)


def test_difficulty_can_only_be_changed_on_the_start_screen(tmp_path):
    game = Game(make_config(tmp_path))
    assert game.set_difficulty("hard") is True
    assert game.difficulty is DIFFICULTIES["hard"]
    assert game.speed == DIFFICULTIES["hard"].base_speed
    assert game.set_difficulty("impossible") is False

    game.start()
    assert game.set_difficulty("easy") is False


@pytest.mark.parametrize(
    "preset,score,expected",
    [
        ("easy", 0, 8),
        ("easy", 49, 8),
        ("easy", 50, 9),
        ("easy", 10_000, 18),
        ("normal", 0, 12),
        ("normal", 49, 12),
        ("normal", 50, 14),
        ("normal", 10_000, 25),
        ("hard", 0, 16),
        ("hard", 30, 18),
        ("hard", 10_000, 32),
    ],
)
def test_speed_increases_with_score(preset, score, expected):
    assert speed_for_score(DIFFICULTIES[preset], score) == expected


def test_speed_never_exceeds_the_preset_cap():
    for preset in DIFFICULTIES.values():
        assert speed_for_score(preset, 10_000_000) <= preset.max_speed


def test_speed_progress_tracks_the_next_speed_up(tmp_path):
    game = Game(make_config(tmp_path))
    assert game.speed_progress == 0.0

    game.score = 25
    assert game.speed_progress == pytest.approx(0.5)

    game.score = 50
    assert game.speed_progress == 0.0

    game.score = 10_000
    assert game.speed_progress == 1.0


def test_wall_hit_ends_the_game(tmp_path):
    game = Game(make_config(tmp_path))
    game.start()
    place_snake(game.snake, [(0, 0), (1, 0), (2, 0)], (-1, 0))
    game.tick()
    assert game.state is GameState.GAME_OVER
    assert game.victory is False


def test_self_hit_ends_the_game(tmp_path):
    game = Game(make_config(tmp_path))
    game.start()
    place_snake(game.snake, [(0, 0), (0, 1), (1, 1), (1, 0), (2, 0)], (1, 0))
    game.tick()
    assert game.state is GameState.GAME_OVER
    assert game.victory is False


def test_game_over_saves_high_score_and_statistics(tmp_path):
    config = make_config(tmp_path)
    game = Game(config)
    game.start()
    game.score = 30
    place_snake(game.snake, [(0, 0), (1, 0), (2, 0)], (-1, 0))
    game.drain_events()
    game.tick()

    assert game.state is GameState.GAME_OVER
    assert game.is_new_high is True
    assert game.high_score == 30
    stats = load_stats(config.data_file)
    assert stats.high_score == 30
    assert stats.last_score == 30
    assert stats.games_played == 1
    assert stats.best_length == 3
    assert stats.top_scores == [30]
    kinds = [event.kind for event in game.drain_events()]
    assert EventKind.NEW_HIGH_SCORE in kinds
    assert EventKind.GAME_OVER in kinds


def test_lower_score_does_not_replace_high_score(tmp_path):
    config = make_config(tmp_path)
    game = Game(config, stats=Stats(high_score=100, games_played=3))
    game.start()
    game.score = 40
    place_snake(game.snake, [(0, 0), (1, 0), (2, 0)], (-1, 0))
    game.tick()
    assert game.is_new_high is False
    assert game.high_score == 100
    stats = load_stats(config.data_file)
    assert stats.high_score == 100
    assert stats.games_played == 4


def test_victory_when_the_board_fills_up(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    game = Game(config)
    game.start()
    head_x, head_y = game.snake.head
    game.food.position = (head_x, head_y - 1)
    monkeypatch.setattr(game.food, "spawn", lambda occupied=(): False)
    game.drain_events()
    game.tick()

    assert game.state is GameState.GAME_OVER
    assert game.victory is True
    assert "victory" in game.stats.achievements
    kinds = [event.kind for event in game.drain_events()]
    assert EventKind.VICTORY in kinds
    assert EventKind.ATE_FOOD in kinds
    assert EventKind.ACHIEVEMENT in kinds


def test_restart_resets_the_run_but_keeps_the_high_score(tmp_path):
    config = make_config(tmp_path)
    game = Game(config, stats=Stats(high_score=50))
    game.start()
    game.score = 20
    game.foods_eaten = 4
    place_snake(game.snake, [(0, 0), (1, 0), (2, 0)], (-1, 0))
    game.tick()
    assert game.state is GameState.GAME_OVER

    assert game.restart() is True
    assert game.state is GameState.PLAYING
    assert game.score == 0
    assert game.foods_eaten == 0
    assert game.victory is False
    assert game.is_new_high is False
    assert len(game.snake.body) == config.start_length
    assert game.food.position not in game.snake.body
    assert game.high_score == 50


def test_restart_is_rejected_while_playing(tmp_path):
    game = Game(make_config(tmp_path))
    game.start()
    assert game.restart() is False
    assert game.state is GameState.PLAYING


def test_restart_run_abandons_the_current_run_and_keeps_playing(tmp_path):
    game = Game(make_config(tmp_path))
    game.start()
    game.score = 40
    game.foods_eaten = 3
    assert game.restart_run() is True
    assert game.state is GameState.PLAYING
    assert game.score == 0
    assert game.foods_eaten == 0
    assert len(game.snake.body) == game.config.start_length


def test_restart_run_records_the_abandoned_score(tmp_path):
    config = make_config(tmp_path)
    game = Game(config)
    game.start()
    game.score = 60
    assert game.restart_run() is True
    stats = load_stats(config.data_file)
    assert stats.high_score == 60
    assert stats.top_scores == [60]
    assert stats.games_played == 0


def test_restart_run_is_rejected_outside_a_live_run(tmp_path):
    game = Game(make_config(tmp_path))
    assert game.restart_run() is False
    game.start()
    game.toggle_pause()
    assert game.restart_run() is True
    assert game.state is GameState.PLAYING


def test_abandon_persists_a_better_score_without_counting_a_game(tmp_path):
    config = make_config(tmp_path)
    game = Game(config)
    game.start()
    game.score = 70
    game.abandon()
    stats = load_stats(config.data_file)
    assert stats.high_score == 70
    assert stats.top_scores == [70]
    assert stats.games_played == 0


def test_same_seed_produces_the_same_initial_food(tmp_path):
    config = make_config(tmp_path, seed=99)
    first = Game(config)
    second = Game(config)
    assert first.food.position == second.food.position


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"cols": 2},
        {"rows": 2},
        {"cols": 61},
        {"rows": 61},
        {"cell_size": 2},
        {"cell_size": 99},
        {"difficulty": "nightmare"},
        {"start_length": 0},
        {"start_length": 99},
        {"header_height": 4},
        {"bonus_every": 0},
        {"combo_window": 0},
        {"combo_multiplier_cap": 0},
    ],
)
def test_invalid_configuration_is_rejected(overrides):
    with pytest.raises(ValueError):
        GameConfig(**overrides)


def test_string_data_file_is_normalised_to_path():
    config = GameConfig(data_file="scores.json")
    assert config.data_file.name == "scores.json"
