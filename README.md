# pySnake

A polished Snake game in two flavours:

- **Desktop** — Python + [pygame](https://www.pygame.org/), with particle effects, progressive difficulty and a persistent high score.
- **Web** — plain HTML/CSS/JavaScript in a single `index.html`, with touch controls for mobile.

Both versions share the same dark neon style and the same set of game states: start screen, pause, game over with restart, and a "board cleared" victory when the snake fills every cell.

## Features

| Feature | Desktop | Web |
|---------|---------|-----|
| Start / pause / game-over / restart screens | ✓ | ✓ |
| Progressive difficulty | ✓ | ✓ |
| Particle effects when eating | ✓ | ✓ |
| Persistent high score | `highscore.json` | `localStorage` |
| Direction-safe input (no accidental reversal) | ✓ | ✓ |
| Board-cleared victory state | ✓ | ✓ |
| Mobile controls (D-pad, tap to start) | – | ✓ |
| Automated tests | ✓ | – |

## Desktop version

### Requirements

- Python 3.9 or newer
- pygame 2.5+

### Installation

```bash
pip install -r requirements.txt
```

### Run

```bash
python snake.py
```

### Controls

| Key | Action |
|-----|--------|
| Arrow Keys / WASD | Start the game and steer (a direction key also resumes from pause) |
| P | Pause / resume |
| SPACE or ENTER | Restart after game over |
| ESC | Quit |

Notes:

- The snake cannot reverse into its own neck, so reversal key presses are safely ignored.
- Speed increases by 2 moves/second for every 50 points, starting at 12 and capped at 25.
- Each food is worth 10 points. The best score is stored in `highscore.json` next to `snake.py` (the file is created automatically and ignored by git).

## Web version

### Run

Open `index.html` in any modern browser — no build step and no dependencies.

### Controls

| Input | Action |
|-------|--------|
| Arrow Keys / WASD | Start the game and steer (a direction key also resumes from pause) |
| P | Pause / resume |
| SPACE or ENTER | Restart after game over |
| Tap the start screen | Start (moves up) |
| Tap the game-over screen | Restart |
| D-pad buttons / swipe | Steer on touch devices |

Notes:

- Speed increases every 50 points (130 ms per step, speeding up to a 60 ms floor).
- The game auto-pauses when you switch tabs.
- The best score is stored in the browser's `localStorage`.

## Testing

Install the development dependencies and run pytest from the repository root:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The suite in `tests/test_snake.py` runs fully headless and covers movement and collision rules (walls, self, tail-vacating), food spawning, scoring, difficulty scaling, high-score persistence (including corrupt files), every game-state transition, and two smoke tests that drive the real pygame loop with SDL's dummy video driver.

## Project structure

```
snake.py             Desktop game (pygame) — logic, rendering and entry point
index.html           Web game (HTML/CSS/JS in one file)
tests/test_snake.py  Automated tests for the desktop game logic
pytest.ini           Pytest configuration
requirements.txt     Runtime dependencies (desktop)
requirements-dev.txt Test dependencies
```

## License

MIT
