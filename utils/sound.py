"""Tiny synthesised retro sound effects (no audio files required)."""
from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple

import numpy as np
import pygame

from utils.logger import get_logger

log = get_logger("sound")

Notes = Sequence[Tuple[float, float]]  # (frequency Hz [0 = rest], seconds)

_EFFECTS: Dict[str, Notes] = {
    "click": ((880, 0.04),),
    "eat": ((660, 0.05), (990, 0.07)),
    "tick": ((440, 0.08),),
    "go": ((880, 0.22),),
    "gameover": ((392, 0.16), (330, 0.16), (262, 0.16), (196, 0.40)),
    "highscore": ((523, 0.10), (659, 0.10), (784, 0.10), (1047, 0.30)),
}


class SoundManager:
    """Generates square-wave effects at start-up; degrades silently without audio."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._sounds: Dict[str, pygame.mixer.Sound] = {}
        self.available = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self._rate, _fmt, self._channels = pygame.mixer.get_init()
            for name, notes in _EFFECTS.items():
                self._sounds[name] = self._synth(notes)
            self.available = True
            log.info("Sound initialized")
        except (pygame.error, NotImplementedError, OSError) as exc:
            log.warning("Sound disabled (no audio device?): %s", exc)

    def _synth(self, notes: Notes, volume: float = 0.22) -> pygame.mixer.Sound:
        chunks = []
        for freq, seconds in notes:
            n = max(1, int(self._rate * seconds))
            t = np.arange(n) / self._rate
            wave = np.sign(np.sin(2 * math.pi * freq * t)) if freq > 0 else np.zeros(n)
            fade = np.minimum(1.0, np.linspace(1.0, 0.0, n) * 8)  # short release: no clicks
            chunks.append(wave * fade)
        data = (np.concatenate(chunks) * volume * 32767).astype(np.int16)
        if self._channels == 2:
            data = np.column_stack((data, data))
        return pygame.mixer.Sound(buffer=data.tobytes())

    def play(self, name: str) -> None:
        if self.enabled and self.available:
            sound = self._sounds.get(name)
            if sound is not None:
                sound.play()

    def close(self) -> None:
        if self.available:
            pygame.mixer.quit()
            self.available = False
