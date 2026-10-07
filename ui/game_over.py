"""Game-over screen with a short retro reveal animation."""
from __future__ import annotations

from typing import Callable, Optional

import pygame

from config import settings as cfg
from config.settings import Palette
from ui.renderer import Renderer
from ui.widgets import ButtonList
from utils.helpers import format_score


class GameOverScreen:
    def __init__(self, renderer: Renderer, on_navigate: Optional[Callable[[], None]] = None) -> None:
        self.r = renderer
        self.age = 0.0
        self.buttons = ButtonList(renderer, [("PLAY AGAIN", "again"), ("MAIN MENU", "menu"), ("QUIT", "quit")],
                                  cfg.ARENA_X + cfg.ARENA_WIDTH // 2, 440, width=340, height=48, gap=12,
                                  on_navigate=on_navigate)
        self.score = self.best = self.length = 0
        self.new_record = self.won = False

    def start(self, score: int, best: int, length: int, new_record: bool, won: bool) -> None:
        self.age = 0.0
        self.score, self.best, self.length = score, best, length
        self.new_record, self.won = new_record, won
        self.buttons.reset()

    def update(self, dt: float) -> None:
        self.age += dt

    @property
    def snake_visible(self) -> bool:
        """Snake blinks while the death flash plays."""
        return self.age >= cfg.GAME_OVER_FLASH_SECONDS or int(self.age * 8) % 2 == 0

    @property
    def panel_ready(self) -> bool:
        return self.age >= cfg.GAME_OVER_FLASH_SECONDS

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if self.age < cfg.GAME_OVER_FLASH_SECONDS + cfg.GAME_OVER_INPUT_DELAY:
            return None  # ignore accidental clicks right after dying
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "menu"
            if event.key == pygame.K_r:
                return "again"
        return self.buttons.handle_event(event)

    def draw(self) -> None:
        if not self.panel_ready:
            return
        r = self.r
        r.veil(180)
        panel = pygame.Rect(0, 0, 540, 560)
        panel.center = (cfg.ARENA_X + cfg.ARENA_WIDTH // 2, 360)
        r.panel(panel, Palette.BG, Palette.TEXT, 3)
        t = self.age - cfg.GAME_OVER_FLASH_SECONDS
        title = "YOU WIN!" if self.won else "GAME OVER"
        blink_on = t > 1.5 or int(t * 4) % 2 == 0   # blinks briefly, then stays solid
        r.text(title, (panel.centerx, panel.y + 30), 7, Palette.ACCENT if blink_on else Palette.TEXT_DIM, "midtop")
        if self.new_record and int(t * 2) % 2 == 0:
            r.text("NEW BEST!", (panel.centerx, panel.y + 100), 3, Palette.WARN, "midtop")
        y = panel.y + 150
        for label, value in (("SCORE", format_score(self.score)), ("BEST", format_score(self.best)),
                             ("LENGTH", str(self.length))):
            r.text(label, (panel.x + 50, y + 8), 2, Palette.TEXT_DIM)
            r.text(value, (panel.right - 50, y), 4, Palette.TEXT, "topright")
            y += 44
        self.buttons.draw()
