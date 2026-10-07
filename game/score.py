"""Score and persistent high score."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from utils.helpers import read_json, write_json_atomic
from utils.logger import get_logger

log = get_logger("score")


class ScoreKeeper:
    """Tracks the current score and the best score (stored as JSON).

    Pass ``path=None`` to disable persistence (used by tests).
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path
        self.score = 0
        self.high_score = 0
        self.new_record = False
        self.load()

    def load(self) -> None:
        if self.path is None:
            return
        data = read_json(self.path, {})
        try:
            self.high_score = max(0, int(data.get("high_score", 0)))
        except (AttributeError, TypeError, ValueError):
            self.high_score = 0

    def reset(self) -> None:
        """Start a new run (the high score is kept)."""
        self.score = 0
        self.new_record = False

    def add(self, points: int) -> None:
        self.score += points
        if self.score > self.high_score:
            self.high_score = self.score
            self.new_record = True

    def save(self) -> bool:
        """Persist the high score. Returns True if a file was written."""
        if self.path is None or not self.new_record:
            return False
        ok = write_json_atomic(self.path, {"high_score": self.high_score})
        if ok:
            log.info("New high score: %d", self.high_score)
        else:
            log.warning("Could not save high score to %s", self.path)
        return ok
