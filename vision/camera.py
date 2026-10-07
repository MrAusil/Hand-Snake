"""Webcam access via OpenCV (no game logic in here)."""
from __future__ import annotations

import sys
from typing import List, Optional, Sequence, Tuple

import numpy as np

try:  # OpenCV is a hard requirement, but a missing install must not crash the UI
    import cv2
except ImportError:  # pragma: no cover - exercised only on broken installs
    cv2 = None  # type: ignore[assignment]

from config import settings as cfg
from utils.logger import get_logger

log = get_logger("camera")


class Camera:
    """Opens a webcam, falls back to other indexes, returns mirrored frames.

    ``read()`` returns a BGR ``numpy`` array of ``frame_size`` (already
    mirrored), or ``None`` for an unreadable frame.
    """

    WARMUP_READS = 15

    def __init__(self, index: int = cfg.CAMERA_INDEX,
                 frame_size: Tuple[int, int] = cfg.CAMERA_FRAME_SIZE,
                 mirror: bool = cfg.MIRROR_CAMERA,
                 fallback_indexes: Sequence[int] = cfg.CAMERA_FALLBACK_INDEXES) -> None:
        self.index = index
        self.frame_size = frame_size
        self.mirror = mirror
        self.fallback_indexes = tuple(fallback_indexes)
        self.active_index: Optional[int] = None
        self.error = ""
        self._cap = None

    # ------------------------------------------------------------------ opening
    def _candidate_indexes(self) -> List[int]:
        return [self.index] + [i for i in self.fallback_indexes if i != self.index]

    @staticmethod
    def _backends() -> List[int]:
        # DirectShow opens far faster than MSMF on Windows.
        if sys.platform.startswith("win"):
            return [cv2.CAP_DSHOW, cv2.CAP_ANY]
        return [cv2.CAP_ANY]

    def _warm_up(self, cap) -> bool:
        """Some cameras need a few reads before delivering a valid frame."""
        for _ in range(self.WARMUP_READS):
            ok, frame = cap.read()
            if ok and frame is not None and frame.size > 0:
                return True
        return False

    def _try_open(self, index: int):
        for backend in self._backends():
            cap = None
            try:
                cap = cv2.VideoCapture(index, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.CAMERA_CAPTURE_SIZE[0])
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.CAMERA_CAPTURE_SIZE[1])
                    cap.set(cv2.CAP_PROP_FPS, cfg.CAMERA_TARGET_FPS)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # always the freshest frame
                    if self._warm_up(cap):
                        return cap
            except cv2.error as exc:
                log.debug("OpenCV error opening camera %d: %s", index, exc)
            if cap is not None:
                cap.release()
        return None

    def open(self) -> bool:
        """Open the preferred camera, then fall back to the others."""
        self.release()
        if cv2 is None:
            self.error = "OpenCV (opencv-python) is not installed."
            log.error(self.error)
            return False
        tried = self._candidate_indexes()
        for index in tried:
            cap = self._try_open(index)
            if cap is not None:
                self._cap = cap
                self.active_index = index
                self.error = ""
                if index != self.index:
                    log.warning("Camera %d unavailable, using camera %d instead", self.index, index)
                log.info("Camera initialized (index %d)", index)
                return True
        self.error = "No working camera found (tried indexes %s)." % ", ".join(map(str, tried))
        log.error("Camera initialization failed: %s", self.error)
        return False

    # ------------------------------------------------------------------ reading
    def is_available(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> Optional[np.ndarray]:
        """Return the next mirrored, resized BGR frame or ``None``."""
        if not self.is_available():
            return None
        try:
            ok, frame = self._cap.read()
            if not ok or frame is None or frame.size == 0 or frame.ndim != 3:
                return None
            if self.mirror:
                frame = cv2.flip(frame, 1)
            if (frame.shape[1], frame.shape[0]) != tuple(self.frame_size):
                frame = cv2.resize(frame, tuple(self.frame_size), interpolation=cv2.INTER_AREA)
            return frame
        except cv2.error as exc:
            log.warning("Camera frame unavailable: %s", exc)
            return None

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except cv2.error:
                pass
            self._cap = None
            self.active_index = None
            log.info("Camera released")
