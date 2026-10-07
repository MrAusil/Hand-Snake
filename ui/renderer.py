"""Shared drawing helpers: text, panels, arena, scanlines, veil."""
from __future__ import annotations

from typing import Dict, Tuple

import pygame

from config import settings as cfg
from config.settings import Palette
from ui.pixel_font import PixelFont

Color = Tuple[int, int, int]


class Renderer:
    """Owns the pixel font and a few pre-rendered overlays."""

    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.font = PixelFont()
        self.arena_rect = pygame.Rect(cfg.ARENA_X, cfg.ARENA_Y, cfg.ARENA_WIDTH, cfg.ARENA_HEIGHT)
        self._arena_bg = self._build_arena_bg()
        self._scanlines = self._build_scanlines()
        self._veils: Dict[int, pygame.Surface] = {}

    # ------------------------------------------------------------------ prebuilt layers
    def _build_arena_bg(self) -> pygame.Surface:
        bg = pygame.Surface(self.arena_rect.size)
        bg.fill(Palette.LCD)
        g = cfg.GRID_SIZE
        for cx in range(cfg.ARENA_COLS):          # faint LCD dot per cell
            for cy in range(cfg.ARENA_ROWS):
                bg.fill(Palette.LCD_DOT, (cx * g + g // 2 - 1, cy * g + g // 2 - 1, 2, 2))
        return bg

    def _build_scanlines(self) -> pygame.Surface:
        layer = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        for y in range(0, layer.get_height(), 3):
            layer.fill((0, 0, 0, 38), (0, y, layer.get_width(), 1))
        return layer

    def _veil(self, alpha: int) -> pygame.Surface:
        veil = self._veils.get(alpha)
        if veil is None:
            veil = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
            veil.fill((*Palette.VEIL, alpha))
            self._veils[alpha] = veil
        return veil

    # ------------------------------------------------------------------ primitives
    def clear(self) -> None:
        self.surface.fill(Palette.BG)

    def text(self, text: str, pos: Tuple[int, int], scale: int = 2, color: Color = Palette.TEXT,
             anchor: str = "topleft") -> pygame.Rect:
        """Draw ``text``; ``anchor`` is any pygame.Rect attribute (center, topright...)."""
        image = self.font.render(text, scale, color)
        rect = image.get_rect()
        setattr(rect, anchor, pos)
        self.surface.blit(image, rect)
        return rect

    def text_width(self, text: str, scale: int) -> int:
        return self.font.measure(text, scale)[0]

    def panel(self, rect: pygame.Rect, fill: Color = Palette.PANEL,
              border: Color = Palette.PANEL_BORDER, width: int = 2) -> None:
        pygame.draw.rect(self.surface, fill, rect)
        if width:
            pygame.draw.rect(self.surface, border, rect, width)

    def bar(self, rect: pygame.Rect, value: float, segments: int = 10) -> None:
        """Segmented level meter, value in 0..1."""
        gap = 3
        seg_w = (rect.width - gap * (segments - 1)) // segments
        filled = round(max(0.0, min(1.0, value)) * segments)
        for i in range(segments):
            seg = pygame.Rect(rect.x + i * (seg_w + gap), rect.y, seg_w, rect.height)
            if i < filled:
                pygame.draw.rect(self.surface, Palette.ACCENT, seg)
            else:
                pygame.draw.rect(self.surface, Palette.TEXT_DIM, seg, 2)

    def veil(self, alpha: int = 170) -> None:
        self.surface.blit(self._veil(alpha), (0, 0))

    def draw_scanlines(self) -> None:
        self.surface.blit(self._scanlines, (0, 0))

    # ------------------------------------------------------------------ arena
    def draw_arena_background(self) -> None:
        outer = self.arena_rect.inflate(20, 20)
        pygame.draw.rect(self.surface, Palette.PANEL, outer)
        pygame.draw.rect(self.surface, Palette.PANEL_BORDER, outer, 2)
        pygame.draw.rect(self.surface, Palette.INK, self.arena_rect.inflate(8, 8))
        self.surface.blit(self._arena_bg, self.arena_rect)

    @property
    def arena_origin(self) -> Tuple[int, int]:
        return (self.arena_rect.x, self.arena_rect.y)
