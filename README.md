# HAND SNAKE

Classic Nokia-style Snake, controlled by **real-time hand movement** through your webcam.
Pygame for the game, OpenCV for the camera, MediaPipe for hand tracking. Everything runs locally.

## Features

- Hand-gesture control (move your hand left / right / up / down)
- Real webcam input, MediaPipe hand tracking, run in a background thread (game stays ~60 FPS)
- Smoothed, debounced gesture decoding (threshold, dominant axis, cooldown, return-stroke suppression)
- Nokia-LCD look with a built-in pixel font and scanlines (no asset files)
- Score, persistent high score, difficulty scaling with a speed cap
- Keyboard fallback, pause, restart, clean state machine
- Live camera preview with palm ring, landmarks and movement vector
- Settings: camera device, preview, tracking overlay, sensitivity, game speed, sound, fullscreen
- First-run camera setup / test screen, synthesised retro sounds
- Camera, MediaPipe and hand-loss failures all handled gracefully
- Privacy: frames are processed locally, never uploaded or stored

## Installation

Python 3.11 or 3.12 recommended (3.9+ works).

```bash
git clone <repo>
cd hand-snake

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

Tests: `pip install -r requirements-dev.txt && python -m pytest`

## Controls

| Input | Action |
|---|---|
| Move hand left / right / up / down (a quick swipe) | Steer the snake |
| Arrow keys or WASD | Steer (fallback) |
| P | Pause / resume |
| R | Restart |
| ESC | Pause menu (in game) / back / main menu |
| F11 | Fullscreen |
| Space / any arrow | Skip "show your hand" wait |

**Tips:** keep your hand fully in frame, well lit, palm toward the camera, roughly an arm's length away.
Swipe decisively; slow drifting and tiny jitter are deliberately ignored. Use the Camera Setup screen
(Settings -> Camera Test) to tune **Sensitivity** while watching the detected movement.

## How the hand-control algorithm works

```
webcam -> Camera (mirror once, resize 320x240) -> MediaPipe Hands -> 21 landmarks
      -> palm centre (mean of wrist + 4 knuckles)          [vision thread]
      -> EMA smoothing (SMOOTHING_FACTOR)
      -> displacement over the last GESTURE_WINDOW (0.35 s)
      -> |move| >= HAND_MOVEMENT_THRESHOLD * (1.5 - sensitivity)?
      -> dominant axis, must beat the other by 1.4x (ignores diagonals)
      -> DIRECTION_COOLDOWN (0.15 s) + return-stroke suppression (0.4 s)
      -> Direction command -> Snake.set_direction()         [main thread]
```

- **Movement, not position:** only the *change* of position over a short window matters, so slow drift is ignored.
- **Mirroring:** the frame is flipped exactly once in `Camera.read()`. All downstream coordinates live in
  that mirrored space, so a physical move to your right is always `+x` -> RIGHT.
- **Return stroke:** after a RIGHT swipe your hand naturally moves back; a LEFT movement right after is ignored.
- **180-degree turns** are rejected in `Snake.set_direction()` (game logic), not just in the controller. A small
  turn queue lets two quick turns (UP then LEFT) both register.
- **Hand lost:** tracking state is cleared, the last direction is kept, a banner is shown, and after
  `NO_HAND_PAUSE_TIMEOUT` (4 s) the game pauses (and resumes by itself when the hand returns).
  Auto-pause is disabled once you use the keyboard in a run.

## Architecture

```
main.py                      entry point
config/settings.py           all constants, palette, UserSettings (JSON)
game/   snake, food, collision, score     pure rules (no pygame loop, no vision)
        engine.py            GameEngine: fixed-step simulation, speed, events
        game.py              Game: state machine, input fusion, update/render loop
vision/ camera.py            OpenCV capture, index fallback, mirror, resize
        hand_tracker.py      MediaPipe wrapper -> HandResult (normalised)
        gesture_controller.py movement -> Direction (knows nothing about MediaPipe)
        worker.py            vision thread + immutable VisionSnapshot
ui/     renderer, hud, menu, settings_screen, camera_setup, how_to_play, game_over, widgets, pixel_font
utils/  logger, helpers, sound
tests/  unit + headless integration tests (no webcam needed)
```

The game never imports MediaPipe. The vision thread publishes an immutable `VisionSnapshot`
under a lock; the main thread reads the newest one each frame and feeds each new camera frame
to the `GestureController` once. There is no `time.sleep()` in the game loop; timing uses
`pygame.time.Clock` and a fixed-step accumulator.

States: `CAMERA_SETUP, MENU, HOW_TO_PLAY, SETTINGS, PLAYING (wait -> countdown -> running), PAUSED, GAME_OVER`.

## Data files (created in `data/`)

`highscore.json`, `settings.json`, `handsnake.log`. They are git-ignored on purpose: they are personal
per-machine state and committing them would overwrite other players' records.

## Troubleshooting

- **"Camera could not be initialized"**: check the webcam is connected, closed in other apps (Zoom, Teams,
  browser), and that camera permission is enabled for your terminal/IDE (macOS: System Settings -> Privacy &
  Security -> Camera; Windows: Settings -> Privacy -> Camera). Try another device in Settings -> Camera Device.
  The keyboard still works.
- **`module 'mediapipe' has no attribute 'solutions'`**: you have a newer MediaPipe. Run
  `pip install "mediapipe>=0.10.14,<0.10.22"`.
- **Dependency conflicts** (numpy 2 vs mediapipe): use the pins in `requirements.txt` in a fresh venv.
  MediaPipe 0.10.x needs `numpy<2`; OpenCV >= 4.12 needs `numpy>=2`, hence the OpenCV cap.
- **Install fails on a new Python (3.13+)**: MediaPipe wheels lag behind; use Python 3.11 or 3.12.
- **Low FPS**: close other camera apps, improve lighting, turn off Hand Tracking Visual / Camera Preview,
  keep `HAND_MODEL_COMPLEXITY = 0` (default) in `config/settings.py`. The status bar shows render FPS.
- **Turns feel too sensitive / too sluggish**: adjust Sensitivity; fine-tune `HAND_MOVEMENT_THRESHOLD`,
  `SMOOTHING_FACTOR`, `DIRECTION_COOLDOWN` in `config/settings.py`.
- **No sound**: no audio device was found; the game continues silently.
- **Linux camera permission**: add your user to the `video` group.

## Compatibility notes

Pinned: `pygame>=2.5,<3`, `opencv-python>=4.8,<4.12`, `mediapipe>=0.10.14,<0.10.22`, `numpy>=1.26,<2`.
Verified here with mediapipe 0.10.21, numpy 1.26, OpenCV 4.11, pygame 2.6 on Python 3.12.
