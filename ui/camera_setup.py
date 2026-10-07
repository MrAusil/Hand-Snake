"""First-run / camera test screen with live feedback."""
from __future__ import annotations

from typing import Callable, Optional

import pygame

from config import settings as cfg
from config.settings import Palette
from ui.hud import DIR_GLYPH, Hud, ViewState, status_texts
from ui.renderer import Renderer
from ui.widgets import ButtonList
from vision.worker import CameraStatus

CAMERA_HELP = ("CAMERA COULD NOT BE INITIALIZED.", "CHECK THAT:", "- YOUR WEBCAM IS CONNECTED",
               "- NO OTHER APP IS USING IT", "- CAMERA PERMISSIONS ARE ENABLED",
               "", "KEYBOARD CONTROLS ARE AVAILABLE.")


class CameraSetupScreen:
    PREVIEW = pygame.Rect(60, 150, 560, 420)

    def __init__(self, renderer: Renderer, hud: Hud,
                 on_navigate: Optional[Callable[[], None]] = None) -> None:
        self.r = renderer
        self.hud = hud
        self.buttons = ButtonList(renderer, [("TEST CAMERA", "test_camera"), ("CONTINUE", "continue")],
                                  950, 490, width=380, height=52, on_navigate=on_navigate)

    def reset(self) -> None:
        self.buttons.selected = 0

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "continue"
            if event.key in (pygame.K_LEFT, pygame.K_a):
                return "sens-"
            if event.key in (pygame.K_RIGHT, pygame.K_d):
                return "sens+"
        return self.buttons.handle_event(event)

    def draw(self, view: ViewState) -> None:
        r, snap = self.r, view.snapshot
        r.clear()
        r.text("CAMERA SETUP", (640, 24), 6, Palette.ACCENT, "midtop")
        r.text("PLACE YOUR HAND INSIDE THE CAMERA FRAME.", (640, 86), 2, Palette.TEXT, "midtop")
        r.text("MOVE YOUR HAND LEFT / RIGHT / UP / DOWN.", (640, 112), 2, Palette.TEXT, "midtop")
        self.hud.draw_camera_preview(self.PREVIEW, view)

        x, y = 700, 150
        (cam, cam_c), (hand, hand_c), _ = status_texts(view)
        r.text("CAMERA:", (x, y), 3, Palette.TEXT_DIM)
        r.text(cam, (x + 180, y), 3, cam_c)
        r.text("HAND:", (x, y + 38), 3, Palette.TEXT_DIM)
        right = r.text(hand, (x + 180, y + 38), 3, hand_c).right
        if snap.hand_detected and snap.status == CameraStatus.ACTIVE:
            r.text("\u2713", (right + 12, y + 38), 3, Palette.OK)

        if snap.status == CameraStatus.ERROR:
            box = pygame.Rect(x, y + 90, 540, 230)
            r.panel(box, Palette.PANEL, Palette.BAD)
            for i, line in enumerate(CAMERA_HELP):
                r.text(line, (box.x + 14, box.y + 14 + i * 24), 2, Palette.BAD if i == 0 else Palette.TEXT)
            r.text(snap.error[:44].upper(), (box.x + 14, box.bottom - 24), 1, Palette.TEXT_DIM)
        else:
            r.text("MOVEMENT:", (x, y + 100), 3, Palette.TEXT_DIM)
            if view.last_command is not None and view.last_command_age < 1.5:
                r.text(f"{view.last_command.name} {DIR_GLYPH[view.last_command]}", (x, y + 140), 6, Palette.ACCENT)
            else:
                r.text("-", (x, y + 140), 6, Palette.TEXT_DIM)
            r.text("SENSITIVITY:  (LEFT / RIGHT KEYS)", (x, y + 226), 2, Palette.TEXT_DIM)
            r.bar(pygame.Rect(x, y + 256, 380, 22), view.sensitivity)
        self.buttons.draw()
        r.text("CAMERA FRAMES ARE PROCESSED LOCALLY. NOTHING IS UPLOADED OR STORED.", (640, 664), 2,
               Palette.TEXT_DIM, "midtop")
