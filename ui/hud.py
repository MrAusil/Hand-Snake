"""In-game HUD: top bar, status bar, side panel and camera preview."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import pygame

from config import settings as cfg
from config.settings import Palette
from game.snake import Direction
from ui.renderer import Renderer
from utils.helpers import format_score
from vision.hand_tracker import HAND_CONNECTIONS
from vision.worker import CameraStatus, VisionSnapshot

DIR_GLYPH = {Direction.UP: "\u2191", Direction.DOWN: "\u2193",
             Direction.LEFT: "\u2190", Direction.RIGHT: "\u2192"}

PREVIEW_RECT = pygame.Rect(cfg.PANEL_X, 80, cfg.PANEL_WIDTH, 218)
PAUSE_BUTTON_RECT = pygame.Rect(cfg.PANEL_X, 588, cfg.PANEL_WIDTH, 44)


@dataclass
class ViewState:
    """Everything the UI needs to know about input, without touching vision code."""
    snapshot: VisionSnapshot
    last_command: Optional[Direction] = None
    last_command_age: float = 999.0
    displacement: Tuple[float, float] = (0.0, 0.0)
    keyboard_mode: bool = False
    fps: float = 0.0
    show_camera: bool = True
    show_landmarks: bool = True
    sensitivity: float = cfg.DEFAULT_SENSITIVITY


def status_texts(view: ViewState):
    """Return ((camera, colour), (hand, colour), (control, colour))."""
    snap = view.snapshot
    cam = {CameraStatus.ACTIVE: ("ACTIVE", Palette.OK), CameraStatus.STARTING: ("STARTING", Palette.WARN),
           CameraStatus.ERROR: ("ERROR", Palette.BAD)}.get(snap.status, ("OFF", Palette.TEXT_DIM))
    if snap.status != CameraStatus.ACTIVE:
        hand = ("--", Palette.TEXT_DIM)
    elif snap.hand_detected:
        hand = ("DETECTED", Palette.OK)
    else:
        hand = ("NOT DETECTED", Palette.WARN)
    if view.keyboard_mode or snap.status == CameraStatus.ERROR:
        control = ("KEYBOARD", Palette.WARN)
    elif snap.status == CameraStatus.ACTIVE:
        control = ("READY", Palette.OK) if snap.hand_detected else ("PAUSED", Palette.WARN)
    else:
        control = ("OFF", Palette.TEXT_DIM)
    return cam, hand, control


class Hud:
    def __init__(self, renderer: Renderer) -> None:
        self.r = renderer
        self._preview_id = -1
        self._preview: Optional[pygame.Surface] = None
        self._preview_buffer: Optional[bytes] = None

    # ------------------------------------------------------------------ preview image
    def preview_surface(self, snap: VisionSnapshot) -> Optional[pygame.Surface]:
        """Convert the newest RGB frame to a (cached, tinted) Surface."""
        if snap.frame_rgb is None or snap.status != CameraStatus.ACTIVE:
            return None
        if snap.frame_id != self._preview_id:
            self._preview_buffer = snap.frame_rgb  # keep the buffer alive
            surf = pygame.image.frombuffer(self._preview_buffer, snap.frame_size, "RGB").copy()
            surf.fill((175, 235, 175), special_flags=pygame.BLEND_RGB_MULT)  # LCD tint
            self._preview, self._preview_id = surf, snap.frame_id
        return self._preview

    def draw_camera_preview(self, rect: pygame.Rect, view: ViewState, scale: int = 2) -> None:
        r, snap = self.r, view.snapshot
        pygame.draw.rect(r.surface, Palette.INK, rect)
        surf = self.preview_surface(snap)
        if surf is not None:
            if surf.get_size() != rect.size:
                surf = pygame.transform.scale(surf, rect.size)
            r.surface.blit(surf, rect)
            if view.show_landmarks:
                self._draw_tracking(rect, view)
        else:
            message = {CameraStatus.STARTING: "STARTING CAMERA...",
                       CameraStatus.ERROR: "CAMERA ERROR"}.get(snap.status, "CAMERA OFF")
            color = Palette.BAD if snap.status == CameraStatus.ERROR else Palette.TEXT_DIM
            r.text(message, rect.center, scale, color, "center")
        pygame.draw.rect(r.surface, Palette.PANEL_BORDER, rect, 2)

    def _draw_tracking(self, rect: pygame.Rect, view: ViewState) -> None:
        snap, surf = view.snapshot, self.r.surface
        if not snap.hand_detected or snap.center is None:
            return

        def px(p):
            return (rect.x + int(p[0] * rect.width), rect.y + int(p[1] * rect.height))

        pts = [px(p) for p in snap.landmarks]
        for a, b in HAND_CONNECTIONS:
            if a < len(pts) and b < len(pts):
                pygame.draw.line(surf, Palette.TEXT, pts[a], pts[b], 1)
        for p in pts:
            pygame.draw.circle(surf, Palette.ACCENT, p, 2)
        c = px(snap.center)
        pygame.draw.circle(surf, Palette.ACCENT, c, max(8, rect.width // 28), 2)  # palm ring
        dx, dy = view.displacement
        tip = (c[0] + int(dx * rect.width * 3), c[1] + int(dy * rect.height * 3))
        if abs(tip[0] - c[0]) + abs(tip[1] - c[1]) > 4:  # movement vector
            pygame.draw.line(surf, Palette.WARN, c, tip, 3)
            pygame.draw.circle(surf, Palette.WARN, tip, 4)

    # ------------------------------------------------------------------ bars
    def draw_top_bar(self, score: int) -> None:
        r = self.r
        r.text(cfg.GAME_TITLE, (40, 24), 4, Palette.ACCENT)
        r.text(f"SCORE: {format_score(score)}", (1240, 24), 4, Palette.TEXT, "topright")

    def draw_status_bar(self, view: ViewState) -> None:
        r = self.r
        pygame.draw.line(r.surface, Palette.PANEL_BORDER, (40, 664), (1240, 664), 2)
        x = 40
        for label, (value, color) in zip(("CAMERA:", "HAND:", "CONTROL:"), status_texts(view)):
            x = r.text(label, (x, 684), 2, Palette.TEXT_DIM).right + 10
            if label == "CAMERA:":
                pygame.draw.circle(r.surface, color, (x + 5, 691), 5)
                x += 18
            x = r.text(value, (x, 684), 2, color).right + 36
        r.text(f"FPS {view.fps:.0f}", (1240, 684), 2, Palette.TEXT_DIM, "topright")

    # ------------------------------------------------------------------ side panel
    def _stat_box(self, y: int, label: str, value: str) -> None:
        box = pygame.Rect(cfg.PANEL_X, y, cfg.PANEL_WIDTH, 62)
        self.r.panel(box)
        self.r.text(label, (box.x + 12, y + 8), 2, Palette.TEXT_DIM)
        self.r.text(value, (box.x + 12, y + 28), 4, Palette.TEXT)

    def draw_side_panel(self, view: ViewState, best: int, length: int, speed: float,
                        pause_hover: bool = False) -> None:
        r = self.r
        if view.show_camera:
            self.draw_camera_preview(PREVIEW_RECT, view)
        else:
            r.panel(PREVIEW_RECT)
            r.text("PREVIEW OFF", PREVIEW_RECT.center, 2, Palette.TEXT_DIM, "center")

        move = pygame.Rect(cfg.PANEL_X, 310, cfg.PANEL_WIDTH, 48)
        r.panel(move)
        r.text("LAST MOVE", (move.x + 12, move.y + 17), 2, Palette.TEXT_DIM)
        if view.last_command is not None and view.last_command_age < 1.5:
            r.text(DIR_GLYPH[view.last_command], (move.right - 16, move.centery), 4, Palette.ACCENT, "midright")
        else:
            r.text("-", (move.right - 16, move.centery), 4, Palette.TEXT_DIM, "midright")

        self._stat_box(368, "BEST", format_score(best))
        self._stat_box(438, "LENGTH", str(length))
        self._stat_box(508, "SPEED", f"{speed:.1f}")

        fill = Palette.TEXT if pause_hover else Palette.PANEL
        pygame.draw.rect(r.surface, fill, PAUSE_BUTTON_RECT)
        pygame.draw.rect(r.surface, Palette.PANEL_BORDER, PAUSE_BUTTON_RECT, 2)
        r.text("PAUSE (P)", PAUSE_BUTTON_RECT.center, 2, Palette.INK if pause_hover else Palette.TEXT, "center")
