"""Game engine: pure game rules (snake + food + score + speed + timing).

The engine knows nothing about pygame rendering, the webcam or MediaPipe.
It only receives direction commands and a time delta.
"""
from __future__ import annotations

import random
from enum import Enum, auto
from typing import List, Optional

from config import settings as cfg
from game.collision import hits_food, hits_self, hits_wall
from game.food import Food
from game.score import ScoreKeeper
from game.snake import Direction, Snake


class EngineEvent(Enum):
    ATE = auto()
    DIED = auto()
    WON = auto()      # the board is completely filled


class DeathReason(Enum):
    WALL = "wall"
    SELF = "self"


class GameEngine:
    """Fixed-rate stepping on a grid, driven by ``update(dt)``."""

    def __init__(self, cols: int = cfg.ARENA_COLS, rows: int = cfg.ARENA_ROWS,
                 score: Optional[ScoreKeeper] = None, speed_multiplier: float = 1.0,
                 rng: Optional[random.Random] = None) -> None:
        self.cols = cols
        self.rows = rows
        self.score = score if score is not None else ScoreKeeper(None)
        self.speed_multiplier = speed_multiplier
        self.snake = Snake((cols // 4, rows // 2))
        self.food = Food(cols, rows, rng)
        self.alive = True
        self.won = False
        self.death_reason: Optional[DeathReason] = None
        self._accumulator = 0.0
        self.reset()

    # ------------------------------------------------------------------ lifecycle
    def reset(self) -> None:
        self.snake.reset()
        self.score.reset()
        self.alive = True
        self.won = False
        self.death_reason = None
        self._accumulator = 0.0
        self.food.spawn(self.snake.body)

    # ------------------------------------------------------------------ properties
    @property
    def speed(self) -> float:
        """Cells per second: grows with the score and is hard-capped."""
        base = cfg.INITIAL_SPEED + self.score.score / cfg.SCORE_PER_SPEED_STEP
        return min(cfg.MAX_SPEED, base * self.speed_multiplier)

    @property
    def length(self) -> int:
        return self.snake.length

    # ------------------------------------------------------------------ input
    def set_direction(self, direction: Optional[Direction]) -> bool:
        return self.alive and self.snake.set_direction(direction)

    # ------------------------------------------------------------------ simulation
    def update(self, dt: float) -> List[EngineEvent]:
        """Advance by ``dt`` seconds; returns the events that happened."""
        if not self.alive:
            return []
        self._accumulator += min(max(dt, 0.0), cfg.MAX_FRAME_DT)
        interval = 1.0 / self.speed
        events: List[EngineEvent] = []
        steps = 0
        while self._accumulator >= interval and self.alive and steps < cfg.MAX_STEPS_PER_FRAME:
            self._accumulator -= interval
            events.extend(self.step())
            steps += 1
        if steps >= cfg.MAX_STEPS_PER_FRAME:
            self._accumulator = min(self._accumulator, interval)  # drop the backlog
        return events

    def step(self) -> List[EngineEvent]:
        """Advance exactly one grid cell."""
        snake = self.snake
        ate = hits_food(snake.next_head(), self.food)
        if ate:
            snake.grow()
        snake.move()

        if hits_wall(snake.head, self.cols, self.rows):
            return self._die(DeathReason.WALL)
        if hits_self(snake):
            return self._die(DeathReason.SELF)

        events: List[EngineEvent] = []
        if ate:
            self.score.add(cfg.FOOD_SCORE)
            events.append(EngineEvent.ATE)
            if self.food.spawn(snake.body) is None:
                self.alive = False
                self.won = True
                events.append(EngineEvent.WON)
        return events

    def _die(self, reason: DeathReason) -> List[EngineEvent]:
        self.alive = False
        self.death_reason = reason
        return [EngineEvent.DIED]
