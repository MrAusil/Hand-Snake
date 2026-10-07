"""MediaPipe hand tracking wrapper (the only module that touches MediaPipe)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from config import settings as cfg
from utils.logger import get_logger

log = get_logger("tracker")

Point = Tuple[float, float]

PALM_LANDMARKS = (0, 5, 9, 13, 17)  # wrist + the four finger knuckles
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)


class HandTrackerError(RuntimeError):
    """MediaPipe could not be imported or initialised."""


@dataclass(frozen=True)
class HandResult:
    """Normalised (0..1) tracking output for one frame."""
    detected: bool
    center: Optional[Point] = None
    landmarks: Tuple[Point, ...] = ()

    def as_dict(self) -> Dict[str, object]:
        return {"detected": self.detected, "center": self.center, "landmarks": list(self.landmarks)}


NO_HAND = HandResult(False, None, ())


def palm_center(landmarks: Sequence[Point]) -> Point:
    """Average of wrist + knuckles: far steadier than the fingertip."""
    pts = [landmarks[i] for i in PALM_LANDMARKS]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


class HandTracker:
    """Detects a single hand and returns normalised landmarks."""

    def __init__(self, detection_confidence: float = cfg.HAND_DETECTION_CONFIDENCE,
                 tracking_confidence: float = cfg.HAND_TRACKING_CONFIDENCE,
                 model_complexity: int = cfg.HAND_MODEL_COMPLEXITY) -> None:
        try:
            import mediapipe as mp
        except Exception as exc:  # ImportError, or a broken native install
            raise HandTrackerError(f"MediaPipe could not be imported: {exc}") from exc
        if not hasattr(mp, "solutions"):
            raise HandTrackerError(
                "This MediaPipe version has no 'solutions' API. "
                "Install a compatible one: pip install \"mediapipe>=0.10.14,<0.10.22\"")
        try:
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=1, model_complexity=model_complexity,
                min_detection_confidence=detection_confidence,
                min_tracking_confidence=tracking_confidence)
        except Exception as exc:
            raise HandTrackerError(f"MediaPipe could not be initialised: {exc}") from exc
        log.info("MediaPipe initialized")

    def process(self, rgb_frame: np.ndarray) -> HandResult:
        """Run detection on an RGB frame. Never raises on bad input."""
        if self._hands is None or rgb_frame is None or rgb_frame.ndim != 3:
            return NO_HAND
        try:
            rgb_frame.flags.writeable = False  # lets MediaPipe skip a copy
            output = self._hands.process(rgb_frame)
        except Exception as exc:
            log.warning("Hand tracking failed on a frame: %s", exc)
            return NO_HAND
        finally:
            try:
                rgb_frame.flags.writeable = True
            except ValueError:
                pass
        if not output.multi_hand_landmarks:
            return NO_HAND
        points = tuple((lm.x, lm.y) for lm in output.multi_hand_landmarks[0].landmark)
        return HandResult(True, palm_center(points), points)

    def close(self) -> None:
        if getattr(self, "_hands", None) is not None:
            self._hands.close()
            self._hands = None
            log.info("MediaPipe released")

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
