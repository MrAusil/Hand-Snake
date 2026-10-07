"""How-to-play screen."""
from __future__ import annotations

from typing import Callable, Optional

import pygame

from config.settings import Palette
from ui.renderer import Renderer
from ui.widgets import ButtonList


class HowToPlayScreen:
    def __init__(self, renderer: Renderer, on_navigate: Optional[Callable[[], None]] = None) -> None:
        self.r = renderer
        self.buttons = ButtonList(renderer, [("BACK", "back")], 640, 628, width=260, height=48,
                                  on_navigate=on_navigate)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "back"
        return self.buttons.handle_event(event)

    def draw(self) -> None:
        r = self.r
        r.clear()
        r.text("HOW TO PLAY", (640, 28), 6, Palette.ACCENT, "midtop")

        left = pygame.Rect(40, 110, 600, 490)
        right = pygame.Rect(660, 110, 580, 490)
        r.panel(left)
        r.panel(right)

        r.text("GAME", (left.x + 20, left.y + 18), 3, Palette.WARN)
        steps = ["1. ALLOW CAMERA ACCESS.", "2. PLACE YOUR HAND IN FRONT",
                 "   OF THE CAMERA.", "3. MOVE YOUR HAND TO CONTROL",
                 "   THE SNAKE.", "4. EAT FOOD TO INCREASE YOUR",
                 "   SCORE.", "5. AVOID WALLS AND YOUR OWN BODY.",
                 "", "A SWIPE IS A QUICK MOVE. SLOW DRIFT", "AND SMALL JITTER ARE IGNORED.",
                 "IF YOUR HAND LEAVES THE FRAME THE", "SNAKE KEEPS ITS LAST DIRECTION."]
        for i, line in enumerate(steps):
            r.text(line, (left.x + 20, left.y + 62 + i * 30), 2, Palette.TEXT if i < 8 else Palette.TEXT_DIM)

        r.text("HAND CONTROLS", (right.x + 20, right.y + 18), 3, Palette.WARN)
        for i, line in enumerate(["\u2190  MOVE HAND LEFT", "\u2192  MOVE HAND RIGHT",
                                  "\u2191  MOVE HAND UP", "\u2193  MOVE HAND DOWN"]):
            r.text(line, (right.x + 20, right.y + 62 + i * 32), 2, Palette.TEXT)

        r.text("KEYBOARD FALLBACK", (right.x + 20, right.y + 218), 3, Palette.WARN)
        for i, line in enumerate(["ARROW KEYS / WASD = MOVE", "P = PAUSE", "R = RESTART",
                                  "ESC = MENU", "F11 = FULLSCREEN", "SPACE = SKIP HAND WAIT"]):
            r.text(line, (right.x + 20, right.y + 262 + i * 32), 2, Palette.TEXT)
        self.buttons.draw()
