"""Application controller: state machine, input fusion, update + render loop."""
from __future__ import annotations

import time
from enum import Enum, auto
from typing import Callable, Dict, Optional

import pygame

from config import settings as cfg
from config.settings import Palette, UserSettings
from game.engine import EngineEvent, GameEngine
from game.score import ScoreKeeper
from game.snake import Direction
from ui.camera_setup import CAMERA_HELP, CameraSetupScreen
from ui.game_over import GameOverScreen
from ui.how_to_play import HowToPlayScreen
from ui.hud import PAUSE_BUTTON_RECT, Hud, ViewState
from ui.menu import MainMenu, PauseMenu
from ui.renderer import Renderer
from ui.settings_screen import SettingsScreen
from utils.logger import get_logger
from utils.sound import SoundManager
from vision.gesture_controller import GestureController
from vision.worker import CameraStatus, VisionSnapshot, VisionWorker

log = get_logger("game")

KEY_DIRECTIONS = {
    pygame.K_UP: Direction.UP, pygame.K_w: Direction.UP,
    pygame.K_DOWN: Direction.DOWN, pygame.K_s: Direction.DOWN,
    pygame.K_LEFT: Direction.LEFT, pygame.K_a: Direction.LEFT,
    pygame.K_RIGHT: Direction.RIGHT, pygame.K_d: Direction.RIGHT,
}


class State(Enum):
    CAMERA_SETUP = auto()
    MENU = auto()
    HOW_TO_PLAY = auto()
    SETTINGS = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()


class Phase(Enum):
    """Sub-states of PLAYING."""
    WAIT_CAMERA = auto()
    COUNTDOWN = auto()
    RUNNING = auto()


class Game:
    """Owns every subsystem. ``vision_factory`` lets tests inject a fake camera pipeline."""

    def __init__(self, vision_factory: Optional[Callable[[int], object]] = None) -> None:
        log.info("Starting %s", cfg.GAME_TITLE)
        pygame.display.init()
        self.settings = UserSettings.load()
        self.screen = self._create_window()
        pygame.display.set_caption(cfg.GAME_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self._cleaned = False

        self.renderer = Renderer(self.screen)
        self.hud = Hud(self.renderer)
        self.sound = SoundManager(self.settings.sound)
        self.score = ScoreKeeper(cfg.HIGHSCORE_FILE)
        self.engine = GameEngine(score=self.score, speed_multiplier=self.settings.game_speed)
        self.gesture = GestureController(sensitivity=self.settings.sensitivity)
        self._vision_factory = vision_factory or (lambda index: VisionWorker(index))
        self.vision = None
        self.snap = VisionSnapshot()

        nav = lambda: self.sound.play("click")  # noqa: E731
        self.main_menu = MainMenu(self.renderer, nav)
        self.pause_menu = PauseMenu(self.renderer, nav)
        self.how_to_play = HowToPlayScreen(self.renderer, nav)
        self.settings_screen = SettingsScreen(self.renderer, self.settings, nav)
        self.camera_setup = CameraSetupScreen(self.renderer, self.hud, nav)
        self.game_over_screen = GameOverScreen(self.renderer, nav)

        self.state = State.CAMERA_SETUP if self.settings.first_run else State.MENU
        self.setup_return = State.MENU
        self.phase = Phase.WAIT_CAMERA
        self.keyboard_mode = False
        self.paused_by_hand = False
        self.last_command: Optional[Direction] = None
        self.last_command_time = float("-inf")
        self._phase_timer = 0.0
        self._hand_confirm = 0.0
        self._hand_seen_at = time.monotonic()
        self._last_frame_id = -1
        self._last_count = -1
        self._time = 0.0

        self._event_handlers: Dict[State, Callable[[pygame.event.Event], None]] = {
            State.CAMERA_SETUP: self._on_setup_event, State.MENU: self._on_menu_event,
            State.HOW_TO_PLAY: self._on_how_event, State.SETTINGS: self._on_settings_event,
            State.PLAYING: self._on_playing_event, State.PAUSED: self._on_paused_event,
            State.GAME_OVER: self._on_game_over_event}
        if self.state is State.CAMERA_SETUP:
            self.setup_return = State.MENU

    # ------------------------------------------------------------------ window
    def _create_window(self) -> pygame.Surface:
        flags = pygame.SCALED | pygame.RESIZABLE
        if self.settings.fullscreen:
            flags |= pygame.FULLSCREEN
        try:
            return pygame.display.set_mode((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), flags)
        except pygame.error:
            log.warning("Scaled window unavailable, using a plain window")
            return pygame.display.set_mode((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))

    def _is_fullscreen(self) -> bool:
        return bool(pygame.display.get_surface().get_flags() & pygame.FULLSCREEN)

    def _toggle_fullscreen(self) -> None:
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error as exc:
            log.warning("Fullscreen toggle failed: %s", exc)
        self.settings.fullscreen = self._is_fullscreen()
        self.settings.save()

    # ------------------------------------------------------------------ vision lifecycle
    def _start_vision(self, restart: bool = False) -> None:
        if restart:
            self._stop_vision()
        if self.vision is None or not self.vision.is_running:
            self.vision = self._vision_factory(self.settings.camera_index)
            self.vision.start()
            self.gesture.reset()
            self._last_frame_id = -1

    def _stop_vision(self) -> None:
        if self.vision is not None:
            self.vision.stop()
            self.vision = None
        self.snap = VisionSnapshot()

    def _feed_gesture(self) -> Optional[Direction]:
        """Pass each *new* camera frame to the gesture controller once."""
        snap = self.snap
        if snap.frame_id == self._last_frame_id or snap.status != CameraStatus.ACTIVE:
            return None
        self._last_frame_id = snap.frame_id
        if snap.hand_detected:
            self._hand_seen_at = time.monotonic()
        command = self.gesture.update(snap.center if snap.hand_detected else None, snap.timestamp)
        if command is not None:
            self.last_command, self.last_command_time = command, time.monotonic()
        return command

    def _view_state(self) -> ViewState:
        return ViewState(
            snapshot=self.snap, last_command=self.last_command,
            last_command_age=time.monotonic() - self.last_command_time,
            displacement=self.gesture.displacement, keyboard_mode=self.keyboard_mode,
            fps=self.clock.get_fps(), show_camera=self.settings.show_camera,
            show_landmarks=self.settings.show_landmarks, sensitivity=self.settings.sensitivity)

    # ------------------------------------------------------------------ main loop
    def run(self) -> None:
        try:
            while self.running:
                dt = self.clock.tick(cfg.FPS) / 1000.0
                self.handle_events()
                self.update(dt)
                self.render()
        finally:
            self.cleanup()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self._toggle_fullscreen()
            else:
                self._event_handlers[self.state](event)

    # ------------------------------------------------------------------ actions
    def _on_action(self, action: Optional[str]) -> None:
        if not action:
            return
        if not action.startswith(("changed", "sens")):
            self.sound.play("click")
        if action == "start":
            self._begin_game()
        elif action == "how":
            self.state = State.HOW_TO_PLAY
        elif action == "settings":
            self.settings_screen.reset()
            self.state = State.SETTINGS
        elif action == "quit":
            self.running = False
        elif action == "back":
            self.state = State.MENU
        elif action in ("restart", "again"):
            self._begin_game()
        elif action == "resume":
            self._resume()
        elif action == "menu":
            self._to_menu()
        elif action == "camera_test":
            if self.state is State.SETTINGS:
                self.setup_return = State.SETTINGS
                self.camera_setup.reset()
                self.state = State.CAMERA_SETUP
            self._start_vision(restart=True)
        elif action == "test_camera":
            self._start_vision(restart=True)
        elif action == "continue":
            self.settings.first_run = False
            self.settings.save()
            self._stop_vision()
            self.state = self.setup_return
            self.setup_return = State.MENU
        elif action == "sens+":
            self._nudge_sensitivity(0.1)
        elif action == "sens-":
            self._nudge_sensitivity(-0.1)
        elif action.startswith("changed:"):
            self._apply_setting(action.split(":", 1)[1])

    def _nudge_sensitivity(self, delta: float) -> None:
        self.settings.sensitivity = round(min(1.0, max(0.1, self.settings.sensitivity + delta)), 2)
        self._apply_setting("sensitivity")

    def _apply_setting(self, key: str) -> None:
        s = self.settings
        if key == "sound":
            self.sound.enabled = s.sound
            self.sound.play("click")
        elif key == "sensitivity":
            self.gesture.set_sensitivity(s.sensitivity)
        elif key == "game_speed":
            self.engine.speed_multiplier = s.game_speed
        elif key == "camera_index":
            if self.vision is not None:
                self._start_vision(restart=True)
        elif key == "fullscreen" and self._is_fullscreen() != s.fullscreen:
            try:
                pygame.display.toggle_fullscreen()
            except pygame.error as exc:
                log.warning("Fullscreen toggle failed: %s", exc)
            s.fullscreen = self._is_fullscreen()
        s.save()

    def _begin_game(self) -> None:
        self.engine.speed_multiplier = self.settings.game_speed
        self.engine.reset()
        self.gesture.reset()
        self.keyboard_mode = False
        self.paused_by_hand = False
        self.last_command = None
        self._start_vision()
        self.state, self.phase = State.PLAYING, Phase.WAIT_CAMERA
        self._phase_timer = self._hand_confirm = 0.0
        log.info("Game started")

    def _to_menu(self) -> None:
        self._stop_vision()
        self.main_menu.buttons.reset()
        self.state = State.MENU

    def _pause(self, by_hand: bool = False) -> None:
        self.paused_by_hand = by_hand
        self._hand_confirm = 0.0
        self.pause_menu.reset()
        self.state = State.PAUSED
        log.info("Game paused%s", " (hand lost)" if by_hand else "")

    def _resume(self) -> None:
        self.gesture.reset()
        self._last_frame_id = -1
        self.paused_by_hand = False
        self.state, self.phase = State.PLAYING, Phase.COUNTDOWN
        self._phase_timer = 0.0
        self._last_count = -1

    def _start_countdown(self) -> None:
        self.phase, self._phase_timer, self._last_count = Phase.COUNTDOWN, 0.0, -1
        self.gesture.reset()
        self._last_frame_id = -1

    def _game_over(self) -> None:
        self.state = State.GAME_OVER
        self.game_over_screen.start(self.score.score, self.score.high_score, self.engine.length,
                                    self.score.new_record, self.engine.won)
        self.score.save()
        self.sound.play("highscore" if self.score.new_record else "gameover")
        log.info("Game over: score=%d length=%d (%s)", self.score.score, self.engine.length,
                 "won" if self.engine.won else self.engine.death_reason.value if self.engine.death_reason else "?")

    # ------------------------------------------------------------------ event handlers
    def _on_setup_event(self, event) -> None:
        self._on_action(self.camera_setup.handle_event(event))

    def _on_menu_event(self, event) -> None:
        self._on_action(self.main_menu.handle_event(event))

    def _on_how_event(self, event) -> None:
        self._on_action(self.how_to_play.handle_event(event))

    def _on_settings_event(self, event) -> None:
        self._on_action(self.settings_screen.handle_event(event))

    def _on_paused_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            self._on_action("restart")
        else:
            self._on_action(self.pause_menu.handle_event(event))

    def _on_game_over_event(self, event) -> None:
        self._on_action(self.game_over_screen.handle_event(event))

    def _on_playing_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and PAUSE_BUTTON_RECT.collidepoint(event.pos):
            self.sound.play("click")
            self._pause()
            return
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        if key == pygame.K_p or key == pygame.K_ESCAPE:
            self._pause()
        elif key == pygame.K_r:
            self._on_action("restart")
        elif key in KEY_DIRECTIONS:
            self.keyboard_mode = True
            if self.phase is Phase.WAIT_CAMERA:
                self._start_countdown()
            elif self.phase is Phase.RUNNING:
                self.engine.set_direction(KEY_DIRECTIONS[key])
        elif key in (pygame.K_SPACE, pygame.K_RETURN) and self.phase is Phase.WAIT_CAMERA:
            self._start_countdown()

    # ------------------------------------------------------------------ update
    def update(self, dt: float) -> None:
        self._time += dt
        self.snap = self.vision.snapshot() if self.vision is not None else VisionSnapshot()
        if self.state is State.PLAYING:
            self._update_playing(dt)
        elif self.state is State.PAUSED:
            self._update_paused(dt)
        elif self.state is State.GAME_OVER:
            self.game_over_screen.update(dt)
        elif self.state is State.CAMERA_SETUP:
            self._feed_gesture()

    def _update_playing(self, dt: float) -> None:
        command = self._feed_gesture()
        snap = self.snap
        if self.phase is Phase.WAIT_CAMERA:
            self._update_waiting(dt)
        elif self.phase is Phase.COUNTDOWN:
            self._update_countdown(dt)
        else:
            if command is not None:
                self.engine.set_direction(command)
            hand_lost_for = time.monotonic() - self._hand_seen_at
            if (not self.keyboard_mode and snap.status == CameraStatus.ACTIVE and not snap.hand_detected
                    and hand_lost_for > cfg.NO_HAND_PAUSE_TIMEOUT):
                self._pause(by_hand=True)
                return
            for event in self.engine.update(dt):
                if event is EngineEvent.ATE:
                    self.sound.play("eat")
                elif event in (EngineEvent.DIED, EngineEvent.WON):
                    self._game_over()

    def _update_waiting(self, dt: float) -> None:
        self._phase_timer += dt
        snap = self.snap
        if snap.status == CameraStatus.ERROR:
            if self._phase_timer > 4.0:
                self.keyboard_mode = True
                self._start_countdown()
        elif snap.status == CameraStatus.ACTIVE and snap.hand_detected:
            self._hand_confirm += dt
            if self._hand_confirm >= cfg.HAND_CONFIRM_TIME:
                self._start_countdown()
        else:
            self._hand_confirm = 0.0

    def _update_countdown(self, dt: float) -> None:
        self._phase_timer += dt
        count = int(self._phase_timer)
        if count != self._last_count:
            self._last_count = count
            if count < cfg.COUNTDOWN_SECONDS:
                self.sound.play("tick")
            elif count == cfg.COUNTDOWN_SECONDS:
                self.sound.play("go")
        if self._phase_timer >= cfg.COUNTDOWN_SECONDS + cfg.GO_FLASH_SECONDS:
            self.phase = Phase.RUNNING
            self._hand_seen_at = time.monotonic()
            self.gesture.reset()
            self._last_frame_id = -1

    def _update_paused(self, dt: float) -> None:
        self._feed_gesture()  # keeps status fresh; commands are ignored while paused
        if self.paused_by_hand and self.snap.hand_detected:
            self._hand_confirm += dt
            if self._hand_confirm >= cfg.HAND_CONFIRM_TIME + 0.3:
                self._resume()
        else:
            self._hand_confirm = 0.0

    # ------------------------------------------------------------------ rendering
    def render(self) -> None:
        r, view = self.renderer, self._view_state()
        if self.state is State.MENU:
            self.main_menu.draw(self._time)
        elif self.state is State.HOW_TO_PLAY:
            self.how_to_play.draw()
        elif self.state is State.SETTINGS:
            self.settings_screen.draw()
        elif self.state is State.CAMERA_SETUP:
            self.camera_setup.draw(view)
        else:
            hide_snake = self.state is State.GAME_OVER and not self.game_over_screen.snake_visible
            self._draw_play_scene(view, hide_snake)
            if self.state is State.PLAYING:
                self._draw_play_overlay(view)
            elif self.state is State.PAUSED:
                self.pause_menu.draw(self.paused_by_hand)
            else:
                self.game_over_screen.draw()
        r.draw_scanlines()
        pygame.display.flip()

    def _draw_play_scene(self, view: ViewState, hide_snake: bool = False) -> None:
        r = self.renderer
        r.clear()
        self.hud.draw_top_bar(self.score.score)
        r.draw_arena_background()
        origin = r.arena_origin
        self.engine.food.draw(r.surface, origin, cfg.GRID_SIZE, pygame.time.get_ticks())
        if not hide_snake:
            r.surface.set_clip(r.arena_rect)
            self.engine.snake.draw(r.surface, origin, cfg.GRID_SIZE, (cfg.ARENA_COLS, cfg.ARENA_ROWS))
            r.surface.set_clip(None)
        hover = self.state is State.PLAYING and PAUSE_BUTTON_RECT.collidepoint(pygame.mouse.get_pos())
        self.hud.draw_side_panel(view, self.score.high_score, self.engine.length, self.engine.speed, hover)
        self.hud.draw_status_bar(view)

    def _draw_play_overlay(self, view: ViewState) -> None:
        r, snap = self.renderer, self.snap
        center = r.arena_rect.center
        if self.phase is Phase.WAIT_CAMERA:
            box = pygame.Rect(0, 0, 700, 300)
            box.center = center
            r.panel(box, Palette.BG, Palette.TEXT, 3)
            if snap.status == CameraStatus.ERROR:
                for i, line in enumerate(CAMERA_HELP):
                    r.text(line, (box.x + 30, box.y + 24 + i * 30), 2, Palette.BAD if i == 0 else Palette.TEXT)
                r.text("STARTING IN KEYBOARD MODE...  (ANY ARROW KEY = GO NOW)", (box.centerx, box.bottom - 30), 1,
                       Palette.TEXT_DIM, "midtop")
            else:
                text = "STARTING CAMERA..." if snap.status != CameraStatus.ACTIVE else "SHOW YOUR HAND TO BEGIN"
                r.text(text, (box.centerx, box.y + 80), 4, Palette.ACCENT, "midtop")
                r.text("HOLD IT STEADY IN THE CAMERA FRAME", (box.centerx, box.y + 150), 2, Palette.TEXT, "midtop")
                r.text("NO CAMERA? PRESS ANY ARROW KEY OR SPACE", (box.centerx, box.y + 190), 2, Palette.TEXT_DIM, "midtop")
                if snap.status == CameraStatus.ACTIVE and self._hand_confirm > 0:
                    r.bar(pygame.Rect(box.x + 200, box.y + 240, 300, 16),
                          self._hand_confirm / cfg.HAND_CONFIRM_TIME, 10)
        elif self.phase is Phase.COUNTDOWN:
            remaining = cfg.COUNTDOWN_SECONDS - int(self._phase_timer)
            label = str(remaining) if remaining > 0 else "GO!"
            r.text(label, (center[0] + 5, center[1] + 5), 18, Palette.INK, "center")
            r.text(label, center, 18, Palette.ACCENT, "center")
        elif (snap.status == CameraStatus.ACTIVE and not snap.hand_detected and not self.keyboard_mode
              and time.monotonic() - self._hand_seen_at > cfg.HAND_LOST_WARNING_AFTER):
            if int(self._time * 3) % 2 == 0:
                banner = pygame.Rect(0, 0, 560, 44)
                banner.midtop = (center[0], r.arena_rect.y + 12)
                r.panel(banner, Palette.INK, Palette.WARN, 2)
                r.text("HAND LOST - HOLDING COURSE", banner.center, 2, Palette.WARN, "center")

    # ------------------------------------------------------------------ shutdown
    def cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        log.info("Shutting down")
        self._stop_vision()
        self.settings.save()
        self.score.save()
        self.sound.close()
        pygame.quit()
