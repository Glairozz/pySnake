"""Tests for the display-independent input mapping helpers."""

from __future__ import annotations

import pytest

from pysnake.controls import (
    JOYSTICK_DEADZONE,
    SWIPE_THRESHOLD,
    axis_direction,
    hat_direction,
    swipe_direction,
)
from pysnake.logic import DIRECTIONS


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (0.0, 0.0, None),
        (0.1, -0.1, None),
        (1.0, 0.0, (1, 0)),
        (-1.0, 0.0, (-1, 0)),
        (0.0, 1.0, (0, 1)),
        (0.0, -1.0, (0, -1)),
        (0.8, 0.7, (1, 0)),
        (-0.2, -0.9, (0, -1)),
    ],
)
def test_axis_direction_maps_sticks_to_cardinal_directions(x, y, expected):
    assert axis_direction(x, y) == expected


def test_axis_direction_respects_the_deadzone():
    assert axis_direction(JOYSTICK_DEADZONE - 0.01, 0.0) is None
    assert axis_direction(JOYSTICK_DEADZONE + 0.01, 0.0) == (1, 0)
    assert axis_direction(0.0, 0.9, deadzone=0.95) is None


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (0, 0, None),
        (1, 0, (1, 0)),
        (-1, 0, (-1, 0)),
        (0, 1, (0, 1)),
        (0, -1, (0, -1)),
        (1, -1, (1, 0)),
        (-1, 1, (-1, 0)),
    ],
)
def test_hat_direction_maps_the_dpad(x, y, expected):
    assert hat_direction(x, y) == expected


def test_swipe_direction_ignores_taps_and_picks_the_dominant_axis():
    assert swipe_direction(5, 5) is None
    assert swipe_direction(SWIPE_THRESHOLD - 1, 0) is None
    assert swipe_direction(SWIPE_THRESHOLD, 0) == (1, 0)
    assert swipe_direction(-80, 20) == (-1, 0)
    assert swipe_direction(10, 90) == (0, 1)
    assert swipe_direction(-10, -90) == (0, -1)
    # Ties favour the horizontal axis.
    assert swipe_direction(40, 40) == (1, 0)


def test_every_helper_only_returns_real_directions():
    results = {
        axis_direction(1.0, 0.0),
        axis_direction(-1.0, 0.0),
        axis_direction(0.0, 1.0),
        axis_direction(0.0, -1.0),
        hat_direction(1, 0),
        hat_direction(-1, 0),
        hat_direction(0, 1),
        hat_direction(0, -1),
        swipe_direction(100, 0),
        swipe_direction(-100, 0),
        swipe_direction(0, 100),
        swipe_direction(0, -100),
    }
    assert results == set(DIRECTIONS)
