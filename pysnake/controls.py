"""Display-independent input mapping helpers for pySnake.

These small pure functions translate joystick axes, d-pad hats and swipe
gestures into cardinal directions.  Keeping them free of pygame makes the
mapping easy to unit-test without a controller or a touchscreen, exactly like
the game rules in :mod:`pysnake.logic`.
"""

from __future__ import annotations

from .logic import Direction

#: How far (in 0..1 units) a joystick axis must move before it counts as a turn.
JOYSTICK_DEADZONE = 0.45

#: Minimum swipe distance in pixels before a gesture becomes a turn.
SWIPE_THRESHOLD = 36.0


def _cardinal(dx: float, dy: float) -> Direction:
    """Return the cardinal direction that best matches a vector."""
    if abs(dx) >= abs(dy):
        return (1, 0) if dx > 0 else (-1, 0)
    return (0, 1) if dy > 0 else (0, -1)


def axis_direction(
    x: float,
    y: float,
    deadzone: float = JOYSTICK_DEADZONE,
) -> Direction | None:
    """Map a joystick axis pair to a cardinal direction, or None at rest."""
    if abs(x) < deadzone and abs(y) < deadzone:
        return None
    return _cardinal(x, y)


def hat_direction(x: int, y: int) -> Direction | None:
    """Map a d-pad hat value to a cardinal direction, or None when centred."""
    if x == 0 and y == 0:
        return None
    return _cardinal(x, y)


def swipe_direction(
    dx: float,
    dy: float,
    threshold: float = SWIPE_THRESHOLD,
) -> Direction | None:
    """Map a swipe vector to the dominant cardinal direction, or None.

    A gesture shorter than *threshold* pixels is treated as a tap and is
    ignored, so accidental touches never steer the snake.
    """
    if max(abs(dx), abs(dy)) < threshold:
        return None
    return _cardinal(dx, dy)
