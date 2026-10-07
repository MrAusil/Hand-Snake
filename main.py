"""HAND SNAKE - Nokia-style Snake controlled by your hand (webcam + MediaPipe)."""
from __future__ import annotations

import sys


def main() -> int:
    if sys.version_info < (3, 9):
        print("HAND SNAKE needs Python 3.9 or newer (3.11+ recommended).")
        return 1
    try:
        import numpy  # noqa: F401
        import pygame  # noqa: F401
    except ImportError as exc:
        print(f"Missing dependency: {exc.name}. Run: pip install -r requirements.txt")
        return 1

    from game.game import Game
    from utils.logger import get_logger

    log = get_logger()
    try:
        game = Game()
    except Exception:
        log.exception("Could not start the game")
        return 1
    try:
        game.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
