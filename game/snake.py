"""Snake model: grid position, direction queue, growth, self-collision."""
from __future__ import annotations

from collections import deque
from enum import Enum
from itertools import islice
from typing import Deque, Optional, Tuple

from config.settings import INITIAL_SNAKE_LENGTH, Palette

Cell = Tuple[int, int]


class Direction(Enum):
    """Unit grid vectors (x grows right, y grows down)."""
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def dx(self) -> int:
        return self.value[0]

    @property
    def dy(self) -> int:
        return self.value[1]

    def opposite(self) -> "Direction":
        return Direction((-self.dx, -self.dy))


class Snake:
    """A snake on a grid. ``body[0]`` is always the head.

    Direction changes go through a small queue so two quick turns between
    ticks (e.g. UP then LEFT while moving RIGHT) are both honoured, while any
    180-degree reversal is rejected *here*, at the game-logic level.
    """

    MAX_QUEUED_TURNS = 3

    def __init__(self, start: Cell, length: int = INITIAL_SNAKE_LENGTH,
                 direction: Direction = Direction.RIGHT) -> None:
        self._start = start
        self._start_length = max(1, length)
        self._start_direction = direction
        self.body: Deque[Cell] = deque()
        self.direction = direction
        self._turns: Deque[Direction] = deque()
        self._pending_growth = 0
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        sx, sy = self._start
        d = self._start_direction
        self.body = deque((sx - d.dx * i, sy - d.dy * i) for i in range(self._start_length))
        self.direction = d
        self._turns = deque()
        self._pending_growth = 0

    @property
    def head(self) -> Cell:
        return self.body[0]

    @property
    def length(self) -> int:
        return len(self.body)

    def occupies(self, cell: Cell) -> bool:
        return cell in self.body

    # ------------------------------------------------------------------ control
    def set_direction(self, new: Optional[Direction]) -> bool:
        """Queue a turn. Returns True if accepted.

        Rejected: ``None``, the direction we are already heading, and the
        direct opposite (an instant 180-degree reversal).
        """
        if new is None:
            return False
        reference = self._turns[-1] if self._turns else self.direction
        if new == reference or new == reference.opposite():
            return False
        if len(self._turns) >= self.MAX_QUEUED_TURNS:
            return False
        self._turns.append(new)
        return True

    def next_head(self) -> Cell:
        """Cell the head will enter on the next ``move()``."""
        d = self._turns[0] if self._turns else self.direction
        hx, hy = self.head
        return (hx + d.dx, hy + d.dy)

    def move(self) -> Cell:
        """Advance one cell; the tail stays put while growth is pending."""
        if self._turns:
            self.direction = self._turns.popleft()
        new_head = (self.head[0] + self.direction.dx, self.head[1] + self.direction.dy)
        self.body.appendleft(new_head)
        if self._pending_growth > 0:
            self._pending_growth -= 1
        else:
            self.body.pop()
        return new_head

    def grow(self, amount: int = 1) -> None:
        """Make the snake ``amount`` cells longer on its next moves."""
        self._pending_growth += max(0, amount)

    def check_self_collision(self) -> bool:
        """True if the head overlaps any other body segment."""
        return self.head in islice(self.body, 1, None)

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, origin: Tuple[int, int], cell: int, bounds: Tuple[int, int]) -> None:
        """Draw the snake as pixel blocks; segments outside ``bounds`` are skipped."""
        import pygame

        cols, rows = bounds
        ox, oy = origin
        for index, (cx, cy) in enumerate(self.body):
            if not (0 <= cx < cols and 0 <= cy < rows):
                continue
            rect = pygame.Rect(ox + cx * cell + 1, oy + cy * cell + 1, cell - 2, cell - 2)
            pygame.draw.rect(surface, Palette.INK, rect)
            if index == 0:  # head: two light "eye" pixels facing the heading
                eye = max(2, cell // 6)
                fx, fy = self.direction.dx, self.direction.dy
                px, py = -fy, fx  # perpendicular
                mid_x, mid_y = rect.centerx + fx * cell // 5, rect.centery + fy * cell // 5
                for side in (-1, 1):
                    ex = mid_x + px * side * cell // 5 - eye // 2
                    ey = mid_y + py * side * cell // 5 - eye // 2
                    pygame.draw.rect(surface, Palette.LCD, (ex, ey, eye, eye))
            else:  # body: tiny inner highlight for a chunky LCD feel
                inner = rect.inflate(-cell // 2, -cell // 2)
                pygame.draw.rect(surface, Palette.LCD_DOT, inner, 1)
