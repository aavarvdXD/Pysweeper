# Pysweeper
A modern, feature-rich Minesweeper clone built with Python and Pygame for people with internet issues like me.
---

## Features
- **Multiple Difficulty Levels**: Easy (9×9, 10 mines), Medium (16×16, 40 mines), Hard (30×16, 99 mines), and Custom (24×16, 21% density)
- **Responsive UI**: Automatically scales to window size with support for resizing
- **Timer & Best Times**: Track your completion time with persistent best scores saved per difficulty
- **Smart First Click**: Optional zero-spread mode guarantees your first click is always a zero cell
- **Chording**: Click both mouse buttons on revealed numbers to quickly clear adjacent cells
- **Flag Counter**: Visual indicator showing remaining flags
- **Dark Theme**: Modern dark color scheme with clean aesthetics
- **Persistent Scores**: Best times are saved locally to minesweeper_scores.json

---
## Requirements
- Python 3.x
- PyGame 2.6.1

---
## Installation
For pygame:
```bash
pip install pygame
```

Usage:
```bash
python main.py
```
---
## Rules
1. The grid contains hidden mines
2. Numbers indicate how many mines are adjacent to that cell
3. Reveal all grids without mines to win
4. Revealing a mine ends the game
