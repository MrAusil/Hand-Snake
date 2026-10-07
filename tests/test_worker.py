"""Vision pipeline with a fake camera + fake tracker (no hardware needed)."""
import time

import numpy as np
import pytest

from vision.hand_tracker import HandResult, HandTrackerError
from vision.worker import CameraStatus, VisionWorker


class FakeCamera:
    def __init__(self, index, ok=True, bad_after=None):
        self.index, self.ok, self.error = index, ok, "" if ok else "no camera here"
        self.active_index = index
        self.released = False
        self.reads = 0

    def open(self):
        return self.ok

    def read(self):
        time.sleep(0.005)
        self.reads += 1
        return np.zeros((240, 320, 3), np.uint8)

    def release(self):
        self.released = True


class FakeTracker:
    def __init__(self):
        self.n = 0
        self.closed = False

    def process(self, rgb):
        self.n += 1
        x = 0.1 + 0.01 * self.n
        return HandResult(True, (x, 0.5), ((x, 0.5),) * 21)

    def close(self):
        self.closed = True


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_snapshot_flows_and_resources_are_released():
    cams = []

    def cam_factory(i):
        cams.append(FakeCamera(i))
        return cams[-1]

    trackers = []

    def trk_factory():
        trackers.append(FakeTracker())
        return trackers[-1]

    w = VisionWorker(0, cam_factory, trk_factory)
    w.start()
    assert wait_for(lambda: w.snapshot().frame_id > 3)
    snap = w.snapshot()
    assert snap.status == CameraStatus.ACTIVE and snap.hand_detected
    assert snap.frame_size == (320, 240) and len(snap.frame_rgb) == 320 * 240 * 3
    w.stop()
    assert cams[0].released and trackers[0].closed
    assert w.snapshot().status == CameraStatus.OFF


def test_camera_failure_is_reported_not_raised():
    w = VisionWorker(0, lambda i: FakeCamera(i, ok=False), FakeTracker)
    w.start()
    assert wait_for(lambda: w.snapshot().status == CameraStatus.ERROR)
    assert "no camera" in w.snapshot().error
    w.stop()


def test_tracker_failure_is_reported_and_camera_released():
    cams = []

    def cam_factory(i):
        cams.append(FakeCamera(i))
        return cams[-1]

    def bad_tracker():
        raise HandTrackerError("MediaPipe could not be initialised: boom")

    w = VisionWorker(0, cam_factory, bad_tracker)
    w.start()
    assert wait_for(lambda: w.snapshot().status == CameraStatus.ERROR)
    assert "MediaPipe" in w.snapshot().error
    w.stop()
    assert cams[0].released


def test_invalid_frames_are_ignored():
    class Flaky(FakeCamera):
        def read(self):
            self.reads += 1
            return None if self.reads % 2 else np.zeros((240, 320, 3), np.uint8)

    w = VisionWorker(0, lambda i: Flaky(i), FakeTracker)
    w.start()
    assert wait_for(lambda: w.snapshot().frame_id > 3)
    assert w.snapshot().status == CameraStatus.ACTIVE
    w.stop()


def test_real_camera_class_fails_gracefully_without_device():
    pytest.importorskip("cv2")
    from vision.camera import Camera
    cam = Camera(index=90, fallback_indexes=())
    assert cam.open() is False
    assert cam.error and cam.read() is None
    cam.release()  # must not raise
