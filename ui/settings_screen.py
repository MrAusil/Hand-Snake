"""Settings screen: toggles, choices and a sensitivity slider."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

import pygame

from config import settings as cfg
from config.settings import Palette, UserSettings
from ui.renderer import Renderer


@dataclass
class Row:
    key: str
    label: str
    kind: str                       # toggle | choice | slider | action
    options: Sequence = ()


ROWS: List[Row] = [
    Row("camera_index", "CAMERA DEVICE", "choice", tuple(range(cfg.MAX_CAMERA_INDEX + 1))),
    Row("show_camera", "CAMERA PREVIEW", "toggle"),
    Row("show_landmarks", "HAND TRACKING VISUAL", "toggle"),
    Row("sensitivity", "SENSITIVITY", "slider"),
    Row("game_speed", "GAME SPEED", "choice", cfg.GAME_SPEED_OPTIONS),
    Row("sound", "SOUND", "toggle"),
    Row("fullscreen", "FULLSCREEN", "toggle"),
    Row("camera_test", "CAMERA TEST", "action"),
    Row("back", "BACK", "action"),
]

ROW_X, ROW_W, ROW_H, ROW_TOP, ROW_GAP = 220, 840, 46, 96, 6


class SettingsScreen:
    def __init__(self, renderer: Renderer, settings: UserSettings,
                 on_navigate: Optional[Callable[[], None]] = None) -> None:
        self.r = renderer
        self.settings = settings
        self.on_navigate = on_navigate
        self.selected = 0
        self.rects = [pygame.Rect(ROW_X, ROW_TOP + i * (ROW_H + ROW_GAP), ROW_W, ROW_H) for i in range(len(ROWS))]

    def reset(self) -> None:
        self.selected = 0

    # ------------------------------------------------------------------ value editing
    def _adjust(self, row: Row, step: int) -> Optional[str]:
        s = self.settings
        if row.kind == "toggle":
            setattr(s, row.key, not getattr(s, row.key))
        elif row.kind == "slider":
            s.sensitivity = round(min(1.0, max(0.1, s.sensitivity + 0.1 * step)), 2)
        elif row.kind == "choice":
            current = getattr(s, row.key)
            idx = row.options.index(current) if current in row.options else 0
            setattr(s, row.key, row.options[(idx + step) % len(row.options)])
        else:
            return row.key  # action
        return f"changed:{row.key}"

    def _value_text(self, row: Row) -> str:
        v = getattr(self.settings, row.key, None)
        if row.kind == "toggle":
            return "ON" if v else "OFF"
        if row.key == "camera_index":
            return f"CAMERA {v}"
        if row.key == "game_speed":
            return cfg.GAME_SPEED_LABELS.get(v, str(v))
        return ""

    # ------------------------------------------------------------------ events
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN:
            row = ROWS[self.selected]
            if event.key == pygame.K_ESCAPE:
                return "back"
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(ROWS)
                self._navigated()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(ROWS)
                self._navigated()
            elif event.key in (pygame.K_LEFT, pygame.K_a) and row.kind != "action":
                return self._adjust(row, -1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d) and row.kind != "action":
                return self._adjust(row, 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self._adjust(row, 1)
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos) and i != self.selected:
                    self.selected = i
                    self._navigated()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.selected = i
                    row = ROWS[i]
                    if row.kind == "slider":
                        bar = self._slider_rect(rect)
                        if bar.inflate(20, 20).collidepoint(event.pos):
                            frac = (event.pos[0] - bar.x) / bar.width
                            self.settings.sensitivity = round(min(1.0, max(0.1, round(frac * 10) / 10)), 2)
                            return "changed:sensitivity"
                    return self._adjust(row, 1)
        return None

    def _navigated(self) -> None:
        if self.on_navigate:
            self.on_navigate()

    @staticmethod
    def _slider_rect(row_rect: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(row_rect.right - 300, row_rect.centery - 8, 280, 16)

    # ------------------------------------------------------------------ drawing
    def draw(self) -> None:
        r = self.r
        r.clear()
        r.text("SETTINGS", (640, 28), 6, Palette.ACCENT, "midtop")
        for i, (row, rect) in enumerate(zip(ROWS, self.rects)):
            active = i == self.selected
            fg = Palette.INK if active else Palette.TEXT
            if active:
                pygame.draw.rect(r.surface, Palette.TEXT, rect)
            else:
                r.panel(rect)
            if row.kind == "action":
                r.text(row.label, rect.center, 3, fg, "center")
                continue
            r.text(row.label, (rect.x + 18, rect.centery), 2, fg, "midleft")
            if row.kind == "slider":
                bar = self._slider_rect(rect)
                r.bar(bar, self.settings.sensitivity)
            else:
                text = self._value_text(row)
                r.text(f"< {text} >" if active else text, (rect.right - 18, rect.centery), 2, fg, "midright")
        note = pygame.Rect(ROW_X, 612, ROW_W, 64)
        r.panel(note)
        r.text("PRIVACY: CAMERA FRAMES ARE PROCESSED LOCALLY.", (note.centerx, note.y + 14), 2, Palette.TEXT, "midtop")
        r.text("NO CAMERA FOOTAGE IS UPLOADED OR STORED.", (note.centerx, note.y + 38), 2, Palette.TEXT, "midtop")
        r.text("ARROWS: SELECT / CHANGE   ENTER: TOGGLE   ESC: BACK", (640, 692), 2, Palette.TEXT_DIM, "midtop")
