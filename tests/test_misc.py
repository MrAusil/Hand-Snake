import pygame

from config.settings import GAME_SPEED_OPTIONS, UserSettings
from ui.pixel_font import GLYPHS, GLYPH_H, GLYPH_W, PixelFont


def test_every_glyph_is_well_formed():
    for char, rows in GLYPHS.items():
        assert len(rows) == GLYPH_H and all(len(r) == GLYPH_W for r in rows), char


def test_font_renders_known_and_unknown_characters():
    pygame.display.init()
    font = PixelFont()
    surf = font.render("Hand 123 \u2192 \u00e9", 2, (255, 255, 255))
    assert surf.get_height() == GLYPH_H * 2 and surf.get_width() > 0


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    s = UserSettings(camera_index=2, sensitivity=0.8, sound=False)
    assert s.save(path)
    loaded = UserSettings.load(path)
    assert (loaded.camera_index, loaded.sensitivity, loaded.sound) == (2, 0.8, False)


def test_settings_sanitize_bad_values(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"camera_index": "banana", "sensitivity": 99, "game_speed": 7, "unknown": 1}')
    s = UserSettings.load(path)
    assert s.camera_index == 0 and s.sensitivity == 1.0 and s.game_speed in GAME_SPEED_OPTIONS


def test_settings_corrupt_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{{{")
    assert UserSettings.load(path).first_run is True
