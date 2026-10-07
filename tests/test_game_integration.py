"""Headless end-to-end test of the Game controller with an injected fake vision pipeline."""
import pygame
import pytest

from config import settings as cfg
from game.game import Game, Phase, State
from game.snake import Direction
from vision.worker import CameraStatus, VisionSnapshot


class FakeVision:
    def __init__(self, index=0):
        self.snap = VisionSnapshot(status=CameraStatus.ACTIVE)
        self.running = False
        self.stopped = False

    def start(self):
        self.running = True

    def stop(self, timeout=3.0):
        self.running, self.stopped = False, True

    @property
    def is_running(self):
        return self.running

    def snapshot(self):
        return self.snap

    def show(self, fid, center, t):
        self.snap = VisionSnapshot(status=CameraStatus.ACTIVE, frame_id=fid, timestamp=t,
                                   hand_detected=center is not None, center=center)


@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(cfg, "HIGHSCORE_FILE", tmp_path / "hs.json")
    import config.settings as s
    monkeypatch.setattr(s.UserSettings, "save", lambda self, path=None: True)
    holder = {}

    def factory(index):
        holder["vision"] = FakeVision(index)
        return holder["vision"]

    g = Game(vision_factory=factory)
    g.score.path = tmp_path / "hs.json"
    g.settings.first_run = False
    g.state = State.MENU
    g.holder = holder
    yield g
    g.cleanup()


def press(game, key):
    game._event_handlers[game.state](pygame.event.Event(pygame.KEYDOWN, key=key))


def frames(game, n, dt=1 / 60):
    for _ in range(n):
        game.update(dt)
        game.render()


def start_running(game):
    game._on_action("start")
    vision = game.holder["vision"]
    vision.show(1, (0.5, 0.5), 0.0)
    frames(game, 40)                               # hand confirmed -> countdown
    assert game.phase is Phase.COUNTDOWN
    frames(game, int(60 * (cfg.COUNTDOWN_SECONDS + cfg.GO_FLASH_SECONDS)) + 5)
    assert game.phase is Phase.RUNNING
    return vision


def test_full_flow_hand_control_eat_and_die(game):
    vision = start_running(game)
    assert game.engine.snake.direction is Direction.RIGHT

    # hand swipes UP (y decreases) over several camera frames -> snake turns UP
    fid, t = 10, 1.0
    for i in range(8):
        vision.show(fid + i, (0.5, 0.6 - 0.04 * i), t + i / 30)
        frames(game, 2)
    assert game.last_command is Direction.UP
    frames(game, 20)
    assert game.engine.snake.direction is Direction.UP

    # illegal reversal is blocked by the engine even if commanded
    assert game.engine.set_direction(Direction.DOWN) is False

    # force food in front of the head and eat it
    hx, hy = game.engine.snake.head
    game.engine.food.position = (hx, hy - 1)
    before = game.score.score
    frames(game, 40)
    assert game.score.score == before + cfg.FOOD_SCORE

    # run into the wall -> game over, high score saved
    frames(game, 600)
    assert game.state is State.GAME_OVER
    assert game.score.high_score >= cfg.FOOD_SCORE
    assert game.score.path.exists()  # high score persisted to disk


def test_keyboard_fallback_and_pause_resume_restart(game):
    game._on_action("start")
    press(game, pygame.K_LEFT)                      # skips the wait phase
    assert game.phase is Phase.COUNTDOWN and game.keyboard_mode
    frames(game, 300)
    assert game.phase is Phase.RUNNING
    press(game, pygame.K_UP)
    frames(game, 20)
    assert game.engine.snake.direction is Direction.UP
    press(game, pygame.K_p)
    assert game.state is State.PAUSED
    frames(game, 10)
    press(game, pygame.K_p)
    assert game.state is State.PLAYING and game.phase is Phase.COUNTDOWN
    press(game, pygame.K_r)
    assert game.engine.length == cfg.INITIAL_SNAKE_LENGTH and game.engine.score.score == 0


def test_hand_loss_auto_pauses_and_hand_return_resumes(game, monkeypatch):
    vision = start_running(game)
    vision.show(50, None, 5.0)
    game._hand_seen_at -= cfg.NO_HAND_PAUSE_TIMEOUT + 1
    frames(game, 2)
    assert game.state is State.PAUSED and game.paused_by_hand
    vision.show(51, (0.5, 0.5), 6.0)
    for i in range(60):
        vision.show(52 + i, (0.5, 0.5), 6.0 + i / 30)
        frames(game, 1)
    assert game.state is State.PLAYING


def test_camera_error_falls_back_to_keyboard_without_crashing(game):
    game._on_action("start")
    game.holder["vision"].snap = VisionSnapshot(status=CameraStatus.ERROR, error="no camera")
    frames(game, 10)
    game._phase_timer = 5.0
    frames(game, 2)
    assert game.phase is Phase.COUNTDOWN and game.keyboard_mode


def test_menu_navigation_and_cleanup_release_camera(game):
    game._on_action("how")
    assert game.state is State.HOW_TO_PLAY
    frames(game, 2)
    game._on_action("back")
    game._on_action("settings")
    frames(game, 2)
    game._on_action("back")
    game._on_action("start")
    vision = game.holder["vision"]
    game._on_action("menu")
    assert vision.stopped and game.state is State.MENU
