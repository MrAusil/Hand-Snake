"""Turns a stream of hand positions into direction commands.

Pipeline::

    raw palm position -> EMA smoothing -> displacement over a short window
        -> threshold + dominant axis + hysteresis -> cooldown
        -> return-stroke suppression -> Direction command

It receives *normalised, already mirrored* coordinates (see ``Camera``), so
``dx > 0`` always means the user's hand physically moved to their right.
This class knows nothing about MediaPipe, OpenCV or pygame.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Tuple

from config import settings as cfg
from game.snake import Direction
from utils.helpers import clamp

Position = Tuple[float, float]


class GestureController:
    """Stateful movement-to-direction decoder."""

    def __init__(self, threshold: float = cfg.HAND_MOVEMENT_THRESHOLD,
                 smoothing: float = cfg.SMOOTHING_FACTOR,
                 cooldown: float = cfg.DIRECTION_COOLDOWN,
                 window: float = cfg.GESTURE_WINDOW,
                 dominance: float = cfg.DIRECTION_DOMINANCE_RATIO,
                 return_suppress: float = cfg.RETURN_STROKE_SUPPRESS,
                 sensitivity: float = cfg.DEFAULT_SENSITIVITY) -> None:
        self.threshold = threshold
        self.smoothing = clamp(smoothing, 0.0, 0.99)
        self.cooldown = cooldown
        self.window = window
        self.dominance = dominance
        self.return_suppress = return_suppress
        self.sensitivity = clamp(sensitivity, 0.1, 1.0)
        self.reset()

    # ------------------------------------------------------------------ config
    def set_sensitivity(self, value: float) -> None:
        self.sensitivity = clamp(value, 0.1, 1.0)

    @property
    def effective_threshold(self) -> float:
        """Higher sensitivity => smaller movement needed (scale 1.4x .. 0.5x)."""
        return self.threshold * (1.5 - self.sensitivity)

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        """Forget all tracking state (call when a game starts/resumes)."""
        self._smoothed: Optional[Position] = None
        self._history: Deque[Tuple[float, float, float]] = deque()
        self._last_emit = float("-inf")
        self._last_command: Optional[Direction] = None
        self._direction: Optional[Direction] = None
        self._displacement: Position = (0.0, 0.0)

    @property
    def direction(self) -> Optional[Direction]:
        """Last command issued (sticky: survives the hand leaving the frame)."""
        return self._direction

    def get_direction(self) -> Optional[Direction]:
        return self._direction

    @property
    def displacement(self) -> Position:
        """Current movement vector (for on-screen feedback)."""
        return self._displacement

    # ------------------------------------------------------------------ main entry
    def update(self, position: Optional[Position], timestamp: float) -> Optional[Direction]:
        """Feed one frame. Returns a *new* command, or ``None``.

        ``position`` is ``None`` when no hand is visible: tracking state is
        cleared (so re-entering the frame is not read as a huge swipe) but the
        last direction is kept.
        """
        if position is None:
            self._smoothed = None
            self._history.clear()
            self._displacement = (0.0, 0.0)
            return None

        x, y = position
        if self._smoothed is None:
            self._smoothed = (x, y)
            self._history.clear()
        else:
            a = self.smoothing
            self._smoothed = (a * self._smoothed[0] + (1 - a) * x,
                              a * self._smoothed[1] + (1 - a) * y)
        sx, sy = self._smoothed

        self._history.append((timestamp, sx, sy))
        while len(self._history) > 1 and self._history[0][0] < timestamp - self.window:
            self._history.popleft()
        _, ox, oy = self._history[0]
        dx, dy = sx - ox, sy - oy
        self._displacement = (dx, dy)

        if timestamp - self._last_emit < self.cooldown:
            return None

        adx, ady = abs(dx), abs(dy)
        if max(adx, ady) < self.effective_threshold:
            return None  # too small: jitter / slow drift

        major, minor = (adx, ady) if adx >= ady else (ady, adx)
        if major < self.dominance * minor:
            return None  # ambiguous diagonal: wait for a clearer swipe

        if adx >= ady:
            candidate = Direction.RIGHT if dx > 0 else Direction.LEFT
        else:
            candidate = Direction.DOWN if dy > 0 else Direction.UP

        if (self._last_command is not None and candidate is self._last_command.opposite()
                and timestamp - self._last_emit < self.return_suppress):
            # The hand is just coming back after a swipe: re-anchor, ignore.
            self._history.clear()
            self._history.append((timestamp, sx, sy))
            return None

        self._direction = candidate
        self._last_command = candidate
        self._last_emit = timestamp
        self._history.clear()
        self._history.append((timestamp, sx, sy))
        self._displacement = (0.0, 0.0)
        return candidate
