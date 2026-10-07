"""Food: random spawning on free cells + pixel-style rendering."""
from __future__ import annotations

import random
from typing import Iterable, Optional, Tuple

from config.settings import Palette

Cell = Tuple[int, int]

# 5x5 "pixel" sprites; the food alternates between them to blink gently.
_SPRITES = (
    (".#.#.", "#####", ".###.", "#####", ".#.#."),
    ("..#..", ".###.", "#####", ".###.", "..#.."),
)


class Food:
    """A single food item that lives on the grid."""

    def __init__(self, cols: int, rows: int, rng: Optional[random.Random] = None) -> None:
        self.cols = cols
        self.rows = rows
        self._rng = rng or random.Random()
        self.position: Optional[Cell] = None

    def spawn(self, occupied: Iterable[Cell]) -> Optional[Cell]:
        """Place food on a random free cell. Returns None if the board is full."""
        blocked = set(occupied)
        total = self.cols * self.rows
        if len(blocked) >= total:
            self.position = None
            return None
        # Fast path: random probing works while the board is mostly empty.
        for _ in range(40):
            cell = (self._rng.randrange(self.cols), self._rng.randrange(self.rows))
            if cell not in blocked:
                self.position = cell
                return cell
        free = [(x, y) for x in range(self.cols) for y in range(self.rows) if (x, y) not in blocked]
        if not free:
            self.position = None
            return None
        self.position = self._rng.choice(free)
        return self.position

    def is_eaten_by(self, cell: Cell) -> bool:
        return self.position is not None and cell == self.position

    def draw(self, surface, origin: Tuple[int, int], cell: int, ticks: int = 0) -> None:
        if self.position is None:
            return
        import pygame

        sprite = _SPRITES[(ticks // 400) % len(_SPRITES)]
        px = cell // 5
        left = origin[0] + self.position[0] * cell + (cell - px * 5) // 2
        top = origin[1] + self.position[1] * cell + (cell - px * 5) // 2
        for row, line in enumerate(sprite):
            for col, char in enumerate(line):
                if char == "#":
                    pygame.draw.rect(surface, Palette.INK, (left + col * px, top + row * px, px, px))
