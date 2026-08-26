# 🟠 Equalizer Grid Simulation

A visual Python experiment that distributes values across a two-dimensional grid and renders every cell with `turtle` graphics.

## Files

- `equalizer.py` — defines the `equalizer` class and its grid-update rule.
- `turtle.py` — creates random starting values, repeatedly updates the grid, and draws the result.

## Simulation model

`equalizer` keeps two `(n + 2) × (n + 2)` matrices:

- `l` stores the current grid values.
- `k` starts as a copy and accumulates the next grid state.

For every internal grid cell, `comparator()` compares the value with each of its four neighbors. When the current cell is at least as large as a neighbor, it transfers one quarter of the current cell value to that neighbor and removes the same amount from the current cell in `k`.

The border padding (`n + 2` rather than `n`) allows neighbor checks above, below, left, and right without accessing outside the allocated matrices.

## Visualization

`turtle.py` asks for the grid size, fills the grid with random values from 0 to 100, then draws each cell as a colored circle:

- Larger values produce larger circles.
- The red color intensity is controlled by the cell value.
- The displayed number is the current value in that cell.

The script updates the grid 200 times, redrawing after every update so the distribution can be observed visually.

## Run

```bash
pip install numpy
python turtle.py
```

> [!NOTE]
> The script is a visualization experiment, not a physically calibrated diffusion solver. It uses a simple quarter-transfer rule and can produce values above 100 before the drawing code clips only the visual color scale.
