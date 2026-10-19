"""Original blue hologram rendering, morph persistence and opt-out behavior."""
from copy import deepcopy
import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from ai_os.config import DEFAULT_CONFIG
from ai_os.native_widgets import (CompanionCanvas, HOLOGRAM_COLORS, hologram_palette,
                                  is_blue_hologram_accent)
from ai_os.pixel_engine import PixelEngine, target_pixels


def test_core_has_segmented_rings_and_stable_speaking_aperture():
    core = target_pixels("core", {}, mouth_open=0)
    speaking = target_pixels("core", {}, mouth_open=2)
    geometry = {(x, y) for x, y, _ in core}
    assert geometry == {(x, y) for x, y, _ in speaking}
    assert core != speaking
    assert len([1 for x, y, _ in core if 9.5 <= math.hypot(x, y) <= 10.6]) > 40
    assert len([1 for x, y, _ in core if 4.3 <= math.hypot(x, y) <= 5.2]) > 20
    assert all(abs(x) <= 11 and abs(y) <= 11 for x, y, _ in core)


def test_orbit_motion_reuses_particles_and_disabled_motion_settles():
    engine = PixelEngine()
    engine.set_form("core", {})
    engine.advance(.02, animate=False)
    identities = [id(p) for p in engine.pixels]
    for _ in range(120):
        engine.advance(.02, motion=.8)
    assert identities == [id(p) for p in engine.pixels]
    assert any(abs(p.x - p.tx) > .2 for p in engine.pixels if math.hypot(p.tx, p.ty) > 9)
    frozen_phase = engine.orbit_elapsed
    engine.advance(.02, motion=0, animate=False)
    assert engine.orbit_elapsed == frozen_phase
    assert all((p.x, p.y) == (p.tx, p.ty) for p in engine.pixels)
    engine.set_form("search", {})
    assert set(identities) == {id(p) for p in engine.pixels}
    assert not engine.core_form


def test_custom_form_never_becomes_core_or_loses_pixels_while_speaking():
    app = QApplication.instance() or QApplication(["hologram-test"])
    canvas = CompanionCanvas()
    canvas.timer.stop()
    config = deepcopy(DEFAULT_CONFIG)
    custom = [".##.", "####", "#++#", ".**."]
    state = {"phase": "speaking", "shape": "search", "emotions": {}, "pixels": custom}
    canvas.set_state(state, config)
    assert canvas.render_shape == "search"
    assert not canvas.engine.core_form
    expected = {(x, y) for x, y, _ in target_pixels("search", {}, custom)}
    assert {(p.tx, p.ty) for p in canvas.engine.pixels if p.active} == expected
    canvas.speech_elapsed = .24
    canvas.update_form()
    assert canvas.mouth_frame == 2
    assert {(p.tx, p.ty) for p in canvas.engine.pixels if p.active} == expected
    config["avatar_topic_morphing"] = False
    canvas.set_state(state, config)
    assert canvas.render_shape == config["avatar_idle_shape"]
    assert canvas.engine.core_form
    canvas.close()
    app.processEvents()


def test_every_material_and_rendered_particle_remains_blue():
    app = QApplication.instance() or QApplication(["hologram-colors-test"])
    assert all(QColor(value).blue() > QColor(value).red() for value in HOLOGRAM_COLORS.values())
    canvas = CompanionCanvas()
    canvas.timer.stop()
    canvas.resize(270, 270)
    config = deepcopy(DEFAULT_CONFIG)
    config["avatar_accent"] = "#ff7700"
    canvas.set_state({"phase": "speaking", "shape": "core", "emotions": {}, "pixels": None}, config)
    canvas.engine.advance(.02, animate=False)
    image = QImage(270, 270, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    canvas.render(image)
    visible = [image.pixelColor(x, y) for x in range(270) for y in range(270)
               if image.pixelColor(x, y).alpha() > 30]
    assert len(visible) > 1000
    assert all(color.blue() > color.red() and color.blue() >= color.green() for color in visible)
    canvas.close()
    app.processEvents()


def test_blue_choices_change_real_palette_and_other_hues_fall_back():
    choices = ("#4daaff", "#69d8ff", "#637dff")
    assert all(is_blue_hologram_accent(shade) for shade in choices)
    palettes = [hologram_palette(shade) for shade in choices]
    assert len({tuple(palette.items()) for palette in palettes}) == len(choices)
    assert [palette["+"] for palette in palettes] == list(choices)
    for shade in ("#00ff00", "#ff9900", "#ffffff", "not a color", None):
        assert not is_blue_hologram_accent(shade)
        assert hologram_palette(shade) == hologram_palette()
    assert all(QColor(color).blue() >= max(QColor(color).red(), QColor(color).green())
               for palette in palettes for color in palette.values())


def test_blue_setting_changes_native_rendered_pixels():
    app = QApplication.instance() or QApplication(["hologram-shades-test"])
    canvas = CompanionCanvas()
    canvas.timer.stop()
    canvas.resize(180, 180)
    config = deepcopy(DEFAULT_CONFIG)
    state = {"phase": "idle", "shape": "core", "emotions": {}, "pixels": None}
    rendered = []
    for accent in ("#4daaff", "#69d8ff", "#637dff"):
        config["avatar_accent"] = accent
        canvas.set_state(state, config)
        canvas.engine.advance(.02, animate=False)
        image = QImage(180, 180, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        canvas.render(image)
        rendered.append(bytes(image.constBits()))
    assert len(set(rendered)) == 3
    canvas.close()
    app.processEvents()
