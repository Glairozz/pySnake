# pySnake

A polished Snake game written in pure Python with [pygame](https://www.pygame.org/).
It keeps the classic rules, adds a proper start/pause/game-over flow, three
difficulty levels, temporary bonus food, wrap-around edges, a persistent
top-five leaderboard, generated sound effects and configurable board sizes —
with no external art or audio assets.

The game rules are completely independent of pygame and are covered by an
automated test suite that runs headlessly on Linux, macOS and Windows.

## Features

- Smooth rendering at 60 FPS with movement on a separate fixed-tick schedule,
  so speed stays consistent on fast and slow machines.
- Responsive input with a two-turn buffer. Rapid turns are preserved, while
  180° reversals are always rejected.
- Start screen, pause/resume, game-over screen, instant restart and a "board
  cleared" victory state.
- Three difficulty levels (Easy, Normal, Hard) that increase speed as the
  score grows.
- Classic solid walls or an optional wrap-around board (`--wrap`) where the
  snake reappears on the opposite edge.
- Food never spawns inside the snake. Wall and self-collision detection is
  accurate, including the classic "follow your own tail" rule.
- Golden bonus food appears every five regular foods, is worth 30 points and
  expires after a limited number of moves.
- A persistent top-five leaderboard, high score and play statistics, saved in
  an atomically written JSON file.
- Toggleable grid and sound effects with adjustable volume. Sounds are
  synthesised at runtime, so there are no audio files to download.
- Resizable window with aspect-ratio-preserving letterboxing, plus a
  fullscreen toggle (`F11`).
- Configurable board dimensions, cell size, difficulty, edge mode and random
  seed via command-line options.
- The game auto-pauses when the window loses focus.
- Score, best score, difficulty, leaderboard and progress feedback are always
  visible.

## Requirements

- Python 3.9 or newer (3.11 recommended)
- pygame 2.5 or newer

## Installation

A virtual environment is recommended:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
python snake.py
```

The default board is 24 × 24 cells with a 600 × 650 window. The window is
resizable, and `F11` toggles fullscreen; the board scales without distortion.

## Controls

| Key | Action |
|-----|--------|
| Arrow keys / WASD | Start the game, steer, or resume from pause |
| `SPACE` / `ENTER` | Start from the start screen, or restart after game over |
| `P` | Pause / resume |
| `R` | Restart the current run immediately (also works after game over) |
| `1`, `2`, `3` | Choose Easy, Normal or Hard on the start screen |
| `G` | Show / hide the grid |
| `M` | Mute / unmute sound effects |
| `[` / `]` (or `-` / `+`) | Lower / raise the sound-effect volume |
| `F11` | Toggle fullscreen |
| `ESC` | Quit |

Notes:

- A direction key that would reverse the snake into its own neck is ignored.
- Up to two turns can be buffered, so two quick key presses both execute.
- The game pauses automatically when the window loses focus.
- The window can be resized freely; the board keeps its aspect ratio and is
  centred with letterbox bars when necessary.

## Gameplay

| Item | Value |
|------|-------|
| Regular food | 10 points, grows the snake by one segment |
| Golden bonus food | 30 points, appears every 5 regular foods, expires after 50 moves |
| High score | Saved after game over, restart or quitting mid-run |
| Leaderboard | The best 5 scores persist between sessions |
| Board cleared | Reaching every cell ends the run in victory |

### Edge modes

By default the board has solid walls, so touching an edge ends the run.
Pass `--wrap` to play on a wrap-around board: leaving one edge immediately
reappears on the opposite edge. Wrapping never teleports the snake into its
own body — self-collisions are still detected normally, and the board can
still be cleared for a victory.

### Difficulty levels

| Level | Starting speed | Maximum speed | Speed-up |
|-------|----------------|---------------|----------|
| Easy | 8 moves/s | 18 moves/s | +1 move/s every 50 points |
| Normal | 12 moves/s | 25 moves/s | +2 moves/s every 50 points |
| Hard | 16 moves/s | 32 moves/s | +2 moves/s every 30 points |

Choose a level with `1`, `2` or `3` on the start screen, or with
`--difficulty` on the command line. The selected level applies for the whole
session and is kept when you restart.

## Configuration

Run `python snake.py --help` for the complete list. Common options:

```bash
# Start on Hard with a reproducible food sequence
python snake.py --difficulty hard --seed 42

# A wider, shorter board with smaller cells
python snake.py --cols 30 --rows 20 --cell-size 22

# Store scores somewhere writable and start with a clean look
python snake.py --data-file scores/highscore.json --no-grid

# Disable the golden bonus food or start muted
python snake.py --no-bonus --mute

# Play on a wrap-around board in fullscreen
python snake.py --wrap --fullscreen
```

| Option | Description |
|--------|-------------|
| `--cols N` | Board width in cells, 8–60 (default 24) |
| `--rows N` | Board height in cells, 8–60 (default 24) |
| `--cell-size N` | Pixels per cell, 12–40 (default 25) |
| `--difficulty {easy,normal,hard}` | Initial difficulty (default `normal`) |
| `--seed N` | Seed the random generator for reproducible food placement |
| `--data-file PATH` | High-score/statistics file (default `highscore.json` next to `snake.py`) |
| `--no-grid` | Start with the grid hidden (toggle with `G`) |
| `--no-bonus` | Disable golden bonus food |
| `--wrap` | Wrap around the edges instead of hitting solid walls |
| `--fullscreen` | Start in fullscreen (toggle with `F11`) |
| `--mute` | Start with sound muted (toggle with `M`) |

Board dimensions are fixed for the session. The window is validated before it
opens; impossible dimensions produce a clear error instead of a broken window.

## Saved data

By default the game stores its data in `highscore.json` next to `snake.py`:

```json
{
  "high_score": 240,
  "games_played": 12,
  "last_score": 80,
  "best_length": 18,
  "top_scores": [240, 180, 120, 90, 80]
}
```

- The file is written to a temporary file and moved into place atomically, so
  an interrupted write cannot leave a partially written score file.
- Missing, unreadable, corrupt or hand-edited files are handled gracefully;
  invalid fields fall back to safe defaults and the game still starts.
- Scores are sanitised, sorted best-first and trimmed to the best five. A run
  that is abandoned with `R` still reaches the leaderboard, but it does not
  increment `games_played`.
- Older files containing only `{"high_score": 120}` are still supported.
- Use `--data-file` if the game directory is read-only or you want separate
  score files for different configurations.

## Testing

Install the development dependencies and run pytest from the repository root:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The tests run headlessly: the game-logic tests need only the standard library,
and the smoke tests select SDL's dummy video and audio drivers. They cover:

- movement in every direction, turn buffering and rejected reversals
- solid-wall and wrap-around edges, body collisions and the vacating-tail rule
- food spawning, full boards, scoring, bonus food and expiry
- all state transitions, restart, instant restart, victory and game over
- high-score, leaderboard and statistics persistence, including corrupt files
- window scaling, sound volume, configuration validation and pygame/CLI smoke
  tests

Continuous integration runs the full suite on Python 3.9, 3.11 and 3.12, plus
Ruff linting and formatting checks, via GitHub Actions.

Run a single group, for example:

```bash
python -m pytest tests/test_logic.py -q
```

## Project structure

```text
snake.py              Command-line entry point and argument parsing
pysnake/
  config.py           Configuration, difficulty presets, colours, limits
  logic.py            Pure game rules, entities and state machine (no pygame)
  storage.py          Atomic high-score/statistics persistence
  ui.py               pygame renderer, overlays and particles
  app.py              Main loop, keyboard handling and generated sounds
tests/
  test_logic.py       Gameplay and state-machine tests
  test_storage.py     Persistence and invalid-data tests
  test_app.py         Headless pygame smoke tests and CLI tests
pytest.ini            Pytest configuration
pyproject.toml        Ruff lint/format configuration
requirements.txt      Runtime dependency (pygame)
requirements-dev.txt  Test and lint dependencies
.github/workflows/    GitHub Actions continuous integration
index.html            Legacy optional browser demo (not part of the Python game)
```

## Troubleshooting

**`pygame is required to run pySnake`**
Install the runtime dependency with `pip install -r requirements.txt`. Make sure
you installed it into the same Python environment you use to run `snake.py`.

**`Unable to open a display`**
pySnake needs a desktop session with a graphical display. On a headless server,
the automated tests still work because they use `SDL_VIDEODRIVER=dummy`; the
interactive game itself needs a display.

**No sound / audio warnings at startup**
Audio is optional. If pygame cannot initialise the sound device (common on
headless systems or systems without an audio server), the game disables sound
and continues normally. Use `M` to check the in-game sound state.

**High score is not saved**
The default location may be read-only (for example, when running from a
read-only directory). Point the game at a writable file:

```bash
python snake.py --data-file ~/pysnake-scores.json
```

**The window is too large or too small**
Adjust `--cols`, `--rows` and `--cell-size`. The game refuses combinations
larger than 2400 pixels in either dimension rather than opening an unusable
window. Once running, drag the window edges to resize it or press `F11` for
fullscreen; scaling keeps the board centred and undistorted.

**The game feels too fast or too slow**
Choose a different difficulty on the start screen (`1`, `2`, `3`) or restart
with `--difficulty easy` / `--difficulty hard`.

## License

MIT
