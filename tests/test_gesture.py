from game.snake import Direction
from vision.gesture_controller import GestureController


def raw():
    """Controller without smoothing so single jumps are decisive."""
    return GestureController(threshold=0.05, smoothing=0.0, cooldown=0.15, sensitivity=0.5)


def swipe(c, start, end, t0=0.0, frames=5, dt=1 / 30):
    cmd, last = None, None
    for i in range(frames + 1):
        f = i / frames
        pos = (start[0] + (end[0] - start[0]) * f, start[1] + (end[1] - start[1]) * f)
        last = c.update(pos, t0 + i * dt)
        cmd = cmd or last
    return cmd


def test_large_positive_dx_is_right():
    assert swipe(raw(), (0.3, 0.5), (0.5, 0.5)) is Direction.RIGHT


def test_large_negative_dx_is_left():
    assert swipe(raw(), (0.6, 0.5), (0.4, 0.5)) is Direction.LEFT


def test_large_positive_dy_is_down():
    assert swipe(raw(), (0.5, 0.3), (0.5, 0.5)) is Direction.DOWN


def test_large_negative_dy_is_up():
    assert swipe(raw(), (0.5, 0.6), (0.5, 0.4)) is Direction.UP


def test_small_movement_is_ignored():
    c = raw()
    assert swipe(c, (0.5, 0.5), (0.51, 0.52)) is None
    assert c.direction is None


def test_ambiguous_diagonal_is_ignored():
    assert swipe(raw(), (0.4, 0.4), (0.5, 0.49)) is None


def test_default_smoothing_still_detects_a_real_swipe():
    c = GestureController()
    assert swipe(c, (0.3, 0.5), (0.7, 0.5), frames=10) is Direction.RIGHT


def test_slow_drift_is_ignored():
    c = GestureController()
    cmd = None
    for i in range(120):  # 0.2 of the frame over 4 s => far below swipe speed
        cmd = cmd or c.update((0.3 + i * 0.0017, 0.5), i / 30)
    assert cmd is None


def test_jitter_is_ignored():
    c = GestureController()
    cmd = None
    for i in range(90):
        cmd = cmd or c.update((0.5 + (0.008 if i % 2 else -0.008), 0.5), i / 30)
    assert cmd is None


def test_cooldown_blocks_rapid_second_command():
    c = raw()
    assert c.update((0.3, 0.5), 0.0) is None
    assert c.update((0.5, 0.5), 0.05) is Direction.RIGHT
    assert c.update((0.5, 0.3), 0.06) is None      # inside cooldown
    assert c.update((0.5, 0.1), 0.10) is None
    assert c.update((0.5, 0.3), 0.30) is Direction.UP


def test_return_stroke_is_suppressed():
    c = raw()
    c.update((0.3, 0.5), 0.0)
    assert c.update((0.5, 0.5), 0.05) is Direction.RIGHT
    # hand glides back to centre right afterwards: must NOT yield LEFT
    cmds = [c.update((0.5 - 0.02 * i, 0.5), 0.25 + i * 0.033) for i in range(8)]
    assert Direction.LEFT not in cmds
    assert c.direction is Direction.RIGHT


def test_deliberate_reversal_later_is_allowed():
    c = raw()
    c.update((0.3, 0.5), 0.0)
    c.update((0.5, 0.5), 0.05)
    c.update((0.5, 0.5), 1.0)
    assert c.update((0.3, 0.5), 1.1) is Direction.LEFT


def test_hand_loss_keeps_direction_and_clears_tracking():
    c = raw()
    c.update((0.3, 0.5), 0.0)
    c.update((0.5, 0.5), 0.05)
    assert c.update(None, 0.2) is None
    assert c.direction is Direction.RIGHT
    # reappearing far away must not be read as a swipe
    assert c.update((0.1, 0.1), 0.4) is None


def test_sensitivity_scales_threshold():
    low = GestureController(sensitivity=0.1).effective_threshold
    high = GestureController(sensitivity=1.0).effective_threshold
    assert high < low


def test_mirrored_space_right_is_physical_right():
    """x grows to the user's right in the mirrored frame => RIGHT."""
    assert swipe(raw(), (0.2, 0.5), (0.4, 0.5)) is Direction.RIGHT
