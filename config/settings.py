"""Central configuration for HAND SNAKE.

Every tunable number lives here. ``UserSettings`` holds the options a player
can change in the Settings screen and persists them to ``data/settings.json``.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, asdict
from pathlib import Path
from typing import Any, Callable

from utils.helpers import clamp, read_json, write_json_atomic

# --------------------------------------------------------------------------- paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
HIGHSCORE_FILE = DATA_DIR / "highscore.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
LOG_FILE = DATA_DIR / "handsnake.log"

# --------------------------------------------------------------------------- window
GAME_TITLE = "HAND SNAKE"
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# --------------------------------------------------------------------------- arena / grid
GRID_SIZE = 20                      # pixels per cell
ARENA_X = 40
ARENA_Y = 80
ARENA_WIDTH = 880                   # pixels
ARENA_HEIGHT = 560                  # pixels
ARENA_COLS = ARENA_WIDTH // GRID_SIZE   # 44
ARENA_ROWS = ARENA_HEIGHT // GRID_SIZE  # 28

PANEL_X = 950                       # right-hand side panel
PANEL_WIDTH = 290

# --------------------------------------------------------------------------- gameplay
INITIAL_SNAKE_LENGTH = 3
FOOD_SCORE = 10
INITIAL_SPEED = 8.0                 # cells per second
MAX_SPEED = 16.0                    # hard cap (cells per second)
SCORE_PER_SPEED_STEP = 100          # speed = INITIAL_SPEED + score / this
MAX_STEPS_PER_FRAME = 3             # never "fast forward" after a lag spike
MAX_FRAME_DT = 0.1                  # clamp dt so hitches do not teleport the snake
COUNTDOWN_SECONDS = 3
GO_FLASH_SECONDS = 0.5
NO_HAND_PAUSE_TIMEOUT = 4.0         # seconds without a hand before auto-pause
HAND_CONFIRM_TIME = 0.4             # hand must be seen this long to start/resume
HAND_LOST_WARNING_AFTER = 1.0       # seconds before the "hand lost" banner shows
GAME_OVER_FLASH_SECONDS = 0.9
GAME_OVER_INPUT_DELAY = 0.5         # ignore buttons right after dying

# --------------------------------------------------------------------------- camera
CAMERA_INDEX = 0
MAX_CAMERA_INDEX = 3
CAMERA_FALLBACK_INDEXES = (0, 1, 2, 3)
CAMERA_CAPTURE_SIZE = (640, 480)    # requested from the device
CAMERA_FRAME_SIZE = (320, 240)      # processed + previewed (4:3)
CAMERA_TARGET_FPS = 30
# The frame is mirrored once, in Camera.read(). Everything downstream
# (landmarks, preview, gestures) lives in this mirrored space, so a physical
# move to the right is always +x. Keep this True.
MIRROR_CAMERA = True
MAX_BAD_FRAMES = 90                 # ~3 s of unreadable frames => camera lost

# --------------------------------------------------------------------------- hand tracking
HAND_DETECTION_CONFIDENCE = 0.6
HAND_TRACKING_CONFIDENCE = 0.5
HAND_MODEL_COMPLEXITY = 0           # 0 = fastest, 1 = more accurate

# --------------------------------------------------------------------------- gesture control
HAND_MOVEMENT_THRESHOLD = 0.05      # normalised displacement needed for a command
SMOOTHING_FACTOR = 0.65             # EMA memory: higher = smoother, laggier
DIRECTION_COOLDOWN = 0.15           # seconds between two commands
GESTURE_WINDOW = 0.35               # seconds over which displacement is measured
DIRECTION_DOMINANCE_RATIO = 1.4     # dominant axis must beat the other by this
RETURN_STROKE_SUPPRESS = 0.4        # ignore the hand "coming back" after a swipe
DEFAULT_SENSITIVITY = 0.5           # threshold scale = 1.5 - sensitivity

# --------------------------------------------------------------------------- colours
class Palette:
    """Muted Nokia-LCD greens."""
    BG = (16, 26, 17)
    PANEL = (30, 46, 30)
    PANEL_BORDER = (70, 100, 60)
    LCD = (163, 190, 114)
    LCD_DOT = (150, 177, 102)
    INK = (26, 38, 22)
    TEXT = (176, 208, 128)
    TEXT_DIM = (104, 134, 84)
    ACCENT = (214, 236, 150)
    OK = (150, 220, 100)
    WARN = (222, 190, 90)
    BAD = (222, 112, 84)
    VEIL = (10, 16, 10)


# --------------------------------------------------------------------------- user settings
GAME_SPEED_OPTIONS = (0.75, 1.0, 1.25)
GAME_SPEED_LABELS = {0.75: "SLOW", 1.0: "NORMAL", 1.25: "FAST"}


def _coerce(kind: Callable[[Any], Any], value: Any, default: Any) -> Any:
    try:
        return kind(value)
    except (TypeError, ValueError):
        return default


@dataclass
class UserSettings:
    """Options editable in the Settings screen (persisted as JSON)."""

    camera_index: int = CAMERA_INDEX
    sensitivity: float = DEFAULT_SENSITIVITY
    show_camera: bool = True
    show_landmarks: bool = True
    game_speed: float = 1.0
    sound: bool = True
    fullscreen: bool = False
    first_run: bool = True

    def sanitize(self) -> "UserSettings":
        """Coerce every field to a valid type/range (handles hand-edited files)."""
        self.camera_index = int(clamp(_coerce(int, self.camera_index, 0), 0, MAX_CAMERA_INDEX))
        self.sensitivity = round(clamp(_coerce(float, self.sensitivity, DEFAULT_SENSITIVITY), 0.1, 1.0), 2)
        speed = _coerce(float, self.game_speed, 1.0)
        self.game_speed = min(GAME_SPEED_OPTIONS, key=lambda option: abs(option - speed))
        for name in ("show_camera", "show_landmarks", "sound", "fullscreen", "first_run"):
            setattr(self, name, bool(getattr(self, name)))
        return self

    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> "UserSettings":
        raw = read_json(path, {})
        if not isinstance(raw, dict):
            raw = {}
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known}).sanitize()

    def save(self, path: Path = SETTINGS_FILE) -> bool:
        return write_json_atomic(path, asdict(self.sanitize()))
