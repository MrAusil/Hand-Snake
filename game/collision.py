"""Pure collision predicates (no pygame, easy to test)."""
from __future__ import annotations

from typing import Tuple

from game.food import Food
from game.snake import Snake

Cell = Tuple[int, int]


def hits_wall(cell: Cell, cols: int, rows: int) -> bool:
    """True if ``cell`` lies outside the ``cols`` x ``rows`` arena."""
    x, y = cell
    return not (0 <= x < cols and 0 <= y < rows)


def hits_self(snake: Snake) -> bool:
    return snake.check_self_collision()


def hits_food(cell: Cell, food: Food) -> bool:
    return food.is_eaten_by(cell)
