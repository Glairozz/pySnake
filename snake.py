"""pySnake - a polished, pure-Python Snake game built with pygame.

Run the game::

    python snake.py

The game logic lives in the :mod:`pysnake` package and has no pygame
dependency, so it can be tested without opening a window.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pysnake import DIFFICULTY_KEYS, GameConfig, __version__
from pysnake.config import (
    DEFAULT_CELL_SIZE,
    DEFAULT_COLS,
    DEFAULT_DATA_FILE,
    DEFAULT_ROWS,
    MAX_BOARD_SIZE,
    MAX_CELL_SIZE,
    MIN_BOARD_SIZE,
    MIN_CELL_SIZE,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for the game."""
    parser = argparse.ArgumentParser(
        prog="snake.py",
        description="A polished pure-Python Snake game.",
        epilog=(
            "Examples:\n"
            "  python snake.py\n"
            "  python snake.py --difficulty hard --seed 42\n"
            "  python snake.py --cols 30 --rows 20 --cell-size 22\n"
            "  python snake.py --wrap --fullscreen\n"
            "  python snake.py --data-file scores/highscore.json --no-grid\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=DEFAULT_COLS,
        help=(
            f"board width in cells ({MIN_BOARD_SIZE}-{MAX_BOARD_SIZE}, "
            "default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_ROWS,
        help=(
            f"board height in cells ({MIN_BOARD_SIZE}-{MAX_BOARD_SIZE}, "
            "default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--cell-size",
        type=int,
        default=DEFAULT_CELL_SIZE,
        help=f"pixels per cell ({MIN_CELL_SIZE}-{MAX_CELL_SIZE}, default: %(default)s)",
    )
    parser.add_argument(
        "--difficulty",
        choices=DIFFICULTY_KEYS,
        default="normal",
        help="starting speed preset (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="seed the random generator for reproducible food placement",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="high-score and statistics file (default: next to the game)",
    )
    parser.add_argument(
        "--no-grid",
        action="store_true",
        help="start with the grid hidden (toggle in-game with G)",
    )
    parser.add_argument(
        "--no-bonus",
        action="store_true",
        help="disable the temporary golden bonus food",
    )
    parser.add_argument(
        "--wrap",
        action="store_true",
        help="wrap around the edges instead of hitting solid walls",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="start in fullscreen (toggle in-game with F11)",
    )
    parser.add_argument(
        "--mute",
        action="store_true",
        help="start with sound effects muted (toggle in-game with M)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"pySnake {__version__}",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> GameConfig:
    """Turn parsed command-line arguments into a validated game config."""
    return GameConfig(
        cols=args.cols,
        rows=args.rows,
        cell_size=args.cell_size,
        difficulty=args.difficulty,
        seed=args.seed,
        show_grid=not args.no_grid,
        sound=not args.mute,
        bonus_food=not args.no_bonus,
        data_file=args.data_file,
        wrap=args.wrap,
        fullscreen=args.fullscreen,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Parse *argv*, open the window and run the game."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = config_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        from pysnake.app import run_game
    except ModuleNotFoundError as exc:
        if exc.name == "pygame":
            print(
                "pygame is required to run pySnake.\n"
                "Install the dependencies with:  pip install -r requirements.txt",
                file=sys.stderr,
            )
            return 1
        raise

    run_game(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
