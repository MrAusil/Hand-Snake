"""Reusable keyboard + mouse button list."""
from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

import pygame

from config.settings import Palette
from ui.renderer import Renderer


class ButtonList:
    """Vertical list of buttons: arrows/W/S + Enter, or hover + click."""

    def __init__(self, renderer: Renderer, items: Sequence[Tuple[str, str]], center_x: int, top: int,
                 width: int = 380, height: int = 52, gap: int = 14, scale: int = 3,
                 on_navigate: Optional[Callable[[], None]] = None) -> None:
        self.renderer = renderer
        self.items = list(items)
        self.scale = scale
        self.on_navigate = on_navigate
        self.selected = 0
        self.rects: List[pygame.Rect] = [
            pygame.Rect(center_x - width // 2, top + i * (height + gap), width, height)
            for i in range(len(self.items))
        ]

    def reset(self) -> None:
        self.selected = 0

    def _move(self, step: int) -> None:
        self.selected = (self.selected + step) % len(self.items)
        if self.on_navigate:
            self.on_navigate()

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Return the action string of an activated button, else ``None``."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self._move(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._move(1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.items[self.selected][1]
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos) and i != self.selected:
                    self.selected = i
                    if self.on_navigate:
                        self.on_navigate()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.selected = i
                    return self.items[i][1]
        return None

    def draw(self) -> None:
        r = self.renderer
        for i, ((label, _), rect) in enumerate(zip(self.items, self.rects)):
            if i == self.selected:
                pygame.draw.rect(r.surface, Palette.TEXT, rect)
                r.text(label, rect.center, self.scale, Palette.INK, "center")
            else:
                pygame.draw.rect(r.surface, Palette.PANEL, rect)
                pygame.draw.rect(r.surface, Palette.PANEL_BORDER, rect, 3)
                r.text(label, rect.center, self.scale, Palette.TEXT, "center")
