"""Main menu and pause menu."""
from __future__ import annotations

import math
from typing import Callable, Optional

import pygame

from config import settings as cfg
from config.settings import Palette
from ui.renderer import Renderer
from ui.widgets import ButtonList


def draw_title(r: Renderer, y: int = 56) -> None:
    r.text(cfg.GAME_TITLE, (644, y + 4), 10, Palette.PANEL_BORDER, "midtop")  # drop shadow
    r.text(cfg.GAME_TITLE, (640, y), 10, Palette.ACCENT, "midtop")


def draw_crawler(r: Renderer, t: float, y: int) -> None:
    """Small decorative snake slithering across the menu."""
    cell = 16
    head_x = int((t * 140) % (cfg.SCREEN_WIDTH + 14 * cell)) - cell
    for i in range(14):
        x = head_x - i * cell
        wave = int(math.sin(t * 4 - i * 0.6) * 10)
        pygame.draw.rect(r.surface, Palette.TEXT if i else Palette.ACCENT, (x, y + wave, cell - 2, cell - 2))


class MainMenu:
    def __init__(self, renderer: Renderer, on_navigate: Optional[Callable[[], None]] = None) -> None:
        self.r = renderer
        self.buttons = ButtonList(renderer, [("START GAME", "start"), ("HOW TO PLAY", "how"),
                                             ("SETTINGS", "settings"), ("QUIT", "quit")],
                                  640, 268, on_navigate=on_navigate)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "quit"
        return self.buttons.handle_event(event)

    def draw(self, t: float) -> None:
        r = self.r
        r.clear()
        draw_title(r)
        r.text("MOVE YOUR HAND.", (640, 160), 3, Palette.TEXT, "midtop")
        r.text("CONTROL THE SNAKE.", (640, 192), 3, Palette.TEXT, "midtop")
        draw_crawler(r, t, 236)
        self.buttons.draw()
        box = pygame.Rect(190, 566, 900, 112)
        r.panel(box)
        r.text("CAMERA REQUIRED", (box.centerx, box.y + 12), 2, Palette.WARN, "midtop")
        r.text("PLACE YOUR HAND IN FRONT OF THE CAMERA. MOVE IT LEFT, RIGHT,", (box.centerx, box.y + 40), 2,
               Palette.TEXT, "midtop")
        r.text("UP OR DOWN TO STEER. PRESS START TO BEGIN.", (box.centerx, box.y + 62), 2, Palette.TEXT, "midtop")
        r.text("NO CAMERA? THE ARROW KEYS WORK TOO.", (box.centerx, box.y + 86), 2, Palette.TEXT_DIM, "midtop")


PAUSE_CENTER_X = cfg.ARENA_X + cfg.ARENA_WIDTH // 2


class PauseMenu:
    def __init__(self, renderer: Renderer, on_navigate: Optional[Callable[[], None]] = None) -> None:
        self.r = renderer
        self.buttons = ButtonList(renderer, [("RESUME", "resume"), ("RESTART", "restart"),
                                             ("MAIN MENU", "menu")], PAUSE_CENTER_X, 320, on_navigate=on_navigate)

    def reset(self) -> None:
        self.buttons.reset()

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "menu"
            if event.key == pygame.K_p:
                return "resume"
        return self.buttons.handle_event(event)

    def draw(self, hand_lost: bool = False) -> None:
        r = self.r
        r.veil(175)
        panel = pygame.Rect(0, 0, 520, 420)
        panel.center = (PAUSE_CENTER_X, 360)
        r.panel(panel, Palette.BG, Palette.TEXT, 3)
        r.text("PAUSED", (panel.centerx, panel.y + 34), 7, Palette.ACCENT, "midtop")
        if hand_lost:
            r.text("HAND LOST - SHOW YOUR HAND", (panel.centerx, panel.y + 110), 2, Palette.WARN, "midtop")
            r.text("TO RESUME", (panel.centerx, panel.y + 134), 2, Palette.WARN, "midtop")
        self.buttons.draw()
