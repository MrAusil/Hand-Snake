"""Background vision thread: Camera -> HandTracker -> shared snapshot.

The main (pygame) thread never blocks on the camera or MediaPipe. It simply
asks for the newest immutable ``VisionSnapshot``.
"""
from __future__ import annotations

import dataclasses
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np

from config import settings as cfg
from utils.logger import get_logger
from vision.camera import Camera
from vision.hand_tracker import HandTracker, HandTrackerError, Point

log = get_logger("vision")


class CameraStatus:
    OFF = "OFF"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class VisionSnapshot:
    """Immutable copy of the latest vision state (safe to share across threads)."""
    status: str = CameraStatus.OFF
    error: str = ""
    frame_id: int = 0
    timestamp: float = 0.0
    hand_detected: bool = False
    center: Optional[Point] = None
    landmarks: Tuple[Point, ...] = ()
    frame_rgb: Optional[bytes] = None
    frame_size: Tuple[int, int] = (0, 0)
    fps: float = 0.0
    camera_index: Optional[int] = None


class VisionWorker:
    """Owns the camera + tracker lifecycle inside a daemon thread."""

    def __init__(self, camera_index: int = cfg.CAMERA_INDEX,
                 camera_factory: Optional[Callable[[int], object]] = None,
                 tracker_factory: Optional[Callable[[], object]] = None) -> None:
        self.camera_index = camera_index
        self._camera_factory = camera_factory or (lambda index: Camera(index))
        self._tracker_factory = tracker_factory or HandTracker
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._snapshot = VisionSnapshot()

    # ------------------------------------------------------------------ public API
    def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self._snapshot = VisionSnapshot(status=CameraStatus.STARTING)
        self._thread = threading.Thread(target=self._run, name="vision-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout)
            if thread.is_alive():
                log.warning("Vision thread did not stop within %.1fs (daemon, will exit with app)", timeout)
        self._publish(status=CameraStatus.OFF, hand_detected=False, center=None,
                      landmarks=(), frame_rgb=None, fps=0.0)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def snapshot(self) -> VisionSnapshot:
        with self._lock:
            return self._snapshot

    # ------------------------------------------------------------------ internals
    def _publish(self, **changes) -> None:
        with self._lock:
            self._snapshot = dataclasses.replace(self._snapshot, **changes)

    def _fail(self, message: str) -> None:
        log.error(message)
        self._publish(status=CameraStatus.ERROR, error=message, hand_detected=False,
                      center=None, landmarks=(), fps=0.0)

    def _run(self) -> None:
        camera = tracker = None
        try:
            camera = self._camera_factory(self.camera_index)
            if not camera.open():
                self._fail(getattr(camera, "error", "") or "Camera could not be opened.")
                return
            try:
                tracker = self._tracker_factory()
            except HandTrackerError as exc:
                self._fail(str(exc))
                return
            self._publish(status=CameraStatus.ACTIVE, error="",
                          camera_index=getattr(camera, "active_index", self.camera_index))
            self._loop(camera, tracker)
        except Exception as exc:  # never let the thread die silently
            log.exception("Vision worker crashed")
            self._fail(f"Vision error: {exc}")
        finally:
            if tracker is not None:
                tracker.close()
            if camera is not None:
                camera.release()

    def _loop(self, camera, tracker) -> None:
        frame_id = 0
        bad_frames = 0
        fps_count, fps_start = 0, time.monotonic()
        fps = 0.0
        last_detected = False
        last_log = 0.0
        while not self._stop.is_set():
            frame = camera.read()
            if frame is None:
                bad_frames += 1
                if bad_frames == 1:
                    log.warning("Camera frame unavailable")
                if bad_frames > cfg.MAX_BAD_FRAMES:
                    self._fail("The camera stopped delivering frames.")
                    return
                self._stop.wait(0.02)
                continue
            bad_frames = 0

            rgb = np.ascontiguousarray(frame[:, :, ::-1])  # BGR -> RGB
            result = tracker.process(rgb)
            now = time.monotonic()

            fps_count += 1
            if now - fps_start >= 1.0:
                fps, fps_count, fps_start = fps_count / (now - fps_start), 0, now

            if result.detected != last_detected and now - last_log > 2.0:
                log.info("Hand detected" if result.detected else "Hand lost")
                last_log = now
            last_detected = result.detected

            frame_id += 1
            self._publish(frame_id=frame_id, timestamp=now, hand_detected=result.detected,
                          center=result.center, landmarks=result.landmarks,
                          frame_rgb=rgb.tobytes(), frame_size=(rgb.shape[1], rgb.shape[0]), fps=fps)
