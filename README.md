# pySnake

A polished Snake game written in pure Python with [pygame](https://www.pygame.org/).
It keeps the classic rules, adds a proper start/pause/game-over flow, three
difficulty levels, combo multipliers, temporary bonus food, wrap-around edges,
an optional obstacle mode, a persistent top-five leaderboard, unlockable
achievements, generated sound effects and configurable board sizes — with no
external art or audio assets.

The game rules are completely independent of pygame and are covered by an
automated test suite that runs headlessly on Linux, macOS and Windows.

## Features

- Smooth rendering at 60 FPS with movement on a separate fixed-tick schedule,
  so speed stays consistent on fast and slow machines. The snake glides
  between cells instead of stepping, so motion looks fluid at every speed.
- Responsive input with a two-turn buffer. Rapid turns are preserved, while
  180° reversals are always rejected.
- Start screen, pause/resume, game-over screen, instant restart and a "board
  cleared" victory state.
- Three difficulty levels (Easy, Normal, Hard) that increase speed as the
  score grows.
- Combo scoring: chain foods within a move window for up to 3× points, with a
  live combo meter and floating score popups.
- Eleven persistent achievements, from the first bite to clearing the board.
- Classic solid walls or an optional wrap-around board (`--wrap`) where the
  snake reappears on the opposite edge.
- An optional obstacle mode (`--obstacles`) that scatters deadly blocks
  across the board. The snake's starting column is always kept clear, food
  never spawns inside a block, and the layout is re-rolled every run.
- Food never spawns inside the snake or on top of the golden bonus. Wall and
  self-collision detection is accurate, including the classic "follow your own
  tail" rule.
- Golden bonus food appears every five regular foods, is worth 30 points and
  expires after a limited number of moves.
- A persistent top-five leaderboard, high score and play statistics, saved in
  an atomically written JSON file.
- Toggleable grid and sound effects with adjustable volume. Sounds are
  synthesised at runtime, so there are no audio files to download.
- A slim HUD bar shows progress towards the next speed-up, and the header shows
  the current speed.
- Resizable window with aspect-ratio-preserving letterboxing, plus a
  fullscreen toggle (`F11`).
- A death or board-clearing victory is punctuated with a flash and a brief
  screen shake.
- Configurable board dimensions, cell size, starting length, difficulty, edge
  mode, obstacle count, bonus settings, volume and random seed via
  command-line options.
- The game auto-pauses when the window loses focus or is minimised.
- Score, best score, difficulty, leaderboard and progress feedback are always
  visible.
- A detailed game-over summary shows foods eaten, golden foods, best combo,
  moves, final length and speed.
- The legacy browser demo in `index.html` now also supports combos, golden
  bonus food, difficulty selection and a run summary.

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
| Regular food | 10 points × combo multiplier, grows the snake by one segment |
| Golden bonus food | 30 points, appears every 5 regular foods, expires after 50 moves |
| Combo | Up to 3× points for chaining foods within 60 moves |
| Obstacle block | Deadly on contact, never blocks the starting column |
| High score | Saved after game over, restart or quitting mid-run |
| Leaderboard | The best 5 scores persist between sessions |
| Achievements | 11 milestones persist across every run |
| Board cleared | Reaching every free cell ends the run in victory |

### Combos

Eating a regular food starts a combo. Eat another regular food before the
combo window (60 moves by default) expires and the multiplier rises from 1×
to 2×, then 3× (the cap). The window counts moves strictly between foods, so a
food eaten on the final allowed move still keeps the combo alive. The current
combo and its remaining window are shown above the board, and each food awards
a floating score popup. Golden bonus food always gives its flat 30 points and
does not break or extend a combo.

Use `--combo-window N` to make combos more or less forgiving, and
`--combo-cap N` to change the maximum multiplier.

### Achievements

| Achievement | Requirement |
|-------------|-------------|
| First Bite | Eat your first food |
| Combo Master | Reach the maximum combo multiplier (`--combo-cap`) |
| Century | Score 100 points |
| Long Body | Grow to 15 segments |
| Bonus Hunter | Eat three golden foods |
| Survivor | Survive 500 moves |
| Wrap Walker | Wrap around an edge (`--wrap`) |
| Full Throttle | Reach the maximum speed for the selected difficulty |
| Veteran | Finish 10 games |
| Daredevil | Eat 10 foods on an obstacle board (`--obstacles`) |
| Board Clearer | Fill the entire board |

Unlocks are saved immediately and announced with an in-game toast. The start
and game-over screens show how many of the eleven you have collected.

### Edge modes

By default the board has solid walls, so touching an edge ends the run.
Pass `--wrap` to play on a wrap-around board: leaving one edge immediately
reappears on the opposite edge. Wrapping never teleports the snake into its
own body — self-collisions are still detected normally, and the board can
still be cleared for a victory.

### Obstacle mode

Pass `--obstacles` to scatter deadly stone blocks across the board and
`--obstacle-count N` to choose how many (default 20, capped at a quarter of
the board). Touching a block ends the run exactly like a wall, and blocks can
be combined with `--wrap` for extra chaos. The rules stay fair:

- The snake's entire starting column is always kept clear, so every run
  begins with a guaranteed escape route.
- Regular food and golden bonus food never spawn inside a block.
- A fresh layout is generated for every run (deterministic for a given
  `--seed`).
- Victory still means filling every cell that is not a block.

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

# Tune the golden food and start at 40% volume
python snake.py --bonus-every 8 --bonus-lifetime 30 --bonus-points 50 --volume 0.4

# Start with a longer snake
python snake.py --start-length 5

# Play on a wrap-around board in fullscreen
python snake.py --wrap --fullscreen

# Dodge obstacle blocks on a wrap-around board
python snake.py --obstacles --obstacle-count 30 --wrap

# Make combos friendlier and cap the multiplier at 2x
python snake.py --combo-window 100 --combo-cap 2
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
| `--bonus-every N` | Regular foods between golden spawns (default 5) |
| `--bonus-lifetime N` | Moves before golden food expires (default 50) |
| `--bonus-points N` | Points awarded by golden food (default 30) |
| `--start-length N` | Initial snake length (default 3) |
| `--combo-window N` | Moves allowed between foods to keep a combo (default 60) |
| `--combo-cap N` | Maximum combo score multiplier (default 3) |
| `--wrap` | Wrap around the edges instead of hitting solid walls |
| `--obstacles` | Scatter deadly obstacle blocks across the board |
| `--obstacle-count N` | Obstacle blocks used with `--obstacles` (default 20, at most a quarter of the board) |
| `--fullscreen` | Start in fullscreen (toggle with `F11`) |
| `--mute` | Start with sound muted (toggle with `M`) |
| `--volume F` | Initial sound volume from 0.0 to 1.0 (default 0.8) |

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
  "best_combo": 3,
  "top_scores": [240, 180, 120, 90, 80],
  "achievements": ["first_bite", "combo_master", "century"]
}
```

- The file is written to a temporary file and moved into place atomically, so
  an interrupted write cannot leave a partially written score file.
- Missing, unreadable, corrupt or hand-edited files are handled gracefully;
  invalid fields fall back to safe defaults and the game still starts.
- Scores are sanitised, sorted best-first and trimmed to the best five. A run
  that is abandoned with `R` still reaches the leaderboard, but it does not
  increment `games_played`; the longest body and best combo records are still
  updated.
- Achievements are stored as stable keys. Unknown or duplicate entries are
  discarded when the file is loaded, and unlocks are written immediately.
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
- obstacle placement, obstacle collisions, obstacle/wrap combinations and
  obstacle-board victories
- food spawning, full boards, scoring, bonus food and expiry
- combo scaling, expiry, last-move chaining, bonus interaction and score events
- achievement unlocking, persistence and sanitisation
- all state transitions, restart, instant restart, victory and game over
- smooth-rendering bookkeeping (previous body, pause/game-over freezing)
- high-score, leaderboard and statistics persistence, including corrupt files
- window scaling, sound volume, configuration validation and pygame/CLI smoke
  tests

Continuous integration runs the full suite on Python 3.9, 3.11, 3.12 and 3.13,
plus Ruff linting and formatting checks, via GitHub Actions.

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
index.html            Optional browser demo with combos, bonus food and difficulty levels
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
