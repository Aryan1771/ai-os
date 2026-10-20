"""Optional native projected depth and explicit fresh-state sensor controls."""
from __future__ import annotations

from copy import deepcopy
import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox

from ai_os import avatar_overlay as avatar
from ai_os.config import DEFAULT_CONFIG, load_raw_config
from ai_os.native_widgets import CompanionCanvas
from ai_os.pixel_engine import project_hologram_particle
from ai_os.settings_store import save_settings


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["avatar-depth-controls-test"])


@pytest.fixture
def overlay(app, tmp_path):
    save_settings({"avatar_enabled": False}, tmp_path)
    window = avatar.AvatarOverlay(tmp_path)
    window.timer.stop()
    yield window
    window.close()
    app.processEvents()


def test_projected_depth_is_finite_bounded_and_has_perspective_without_scene_state():
    depths, scales = set(), set()
    for elapsed in (0, 10, 150):
        for x in (-12, -4, 0, 5, 12):
            for y in (-12, -3, 0, 7, 12):
                px, py, depth, scale = project_hologram_particle(x, y, elapsed)
                assert all(math.isfinite(value) for value in (px, py, depth, scale))
                assert abs(px) < 16 and abs(py) < 16 and abs(depth) < 12
                assert .8 < scale < 1.25
                depths.add(round(depth, 1))
                scales.add(round(scale, 2))
    assert len(depths) > 20 and len(scales) > 10
    assert project_hologram_particle(float("nan"), 0) == (0, 0, 0, 1)


def test_default_stays_2d_and_only_known_render_modes_are_saved(tmp_path):
    assert DEFAULT_CONFIG["avatar_render_mode"] == "2d"
    assert load_raw_config(tmp_path)["avatar_render_mode"] == "2d"
    assert save_settings({"avatar_render_mode": "3d"}, tmp_path)["avatar_render_mode"] == "3d"
    with pytest.raises(ValueError):
        save_settings({"avatar_render_mode": "javascript"}, tmp_path)
    assert load_raw_config(tmp_path)["avatar_render_mode"] == "3d"


def test_native_2d_and_depth_render_differ_without_replacing_particles(app):
    canvas = CompanionCanvas()
    canvas.timer.stop()
    canvas.resize(270, 270)
    config = deepcopy(DEFAULT_CONFIG)
    state = {"phase": "speaking", "shape": "code", "emotions": {}, "pixels": None}
    rendered = []
    identities = None
    for mode in ("2d", "3d"):
        config["avatar_render_mode"] = mode
        canvas.set_state(state, config)
        canvas.engine.advance(.02, animate=False)
        current = [id(pixel) for pixel in canvas.engine.pixels]
        if identities is not None:
            assert current == identities
        identities = current
        image = QImage(270, 270, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        canvas.render(image)
        rendered.append(bytes(image.constBits()))
    assert rendered[0] != rendered[1]
    assert canvas.render_shape == "code"
    assert canvas.timer.interval() == 42
    config["avatar_motion"] = 0
    canvas.set_state(state, config)
    assert canvas.timer.interval() == 200
    canvas.engine.advance(.05, motion=0)
    orbit = canvas.engine.orbit_elapsed
    canvas.engine.advance(.05, motion=0)
    assert canvas.engine.orbit_elapsed == orbit
    canvas.close()


def _action(menu, prefix):
    return next(action for action in menu.actions() if action.text().startswith(prefix))


def test_opening_menu_and_denying_start_never_enables_microphone_or_screen(overlay, monkeypatch):
    window = overlay
    questions = []

    def deny(box):
        questions.append(box.windowTitle())
        assert box.textFormat() == Qt.TextFormat.PlainText
        assert box.standardButton(box.defaultButton()) == QMessageBox.StandardButton.No
        return QMessageBox.StandardButton.No

    save_settings({"wake_word_enabled": True, "sandbox_lock_settings": False}, window.home, human_confirmed=True)
    monkeypatch.setattr(QMessageBox, "exec", deny)
    before = (window.home / "config.json").read_bytes()
    menu = window.build_context_menu()
    assert not questions
    _action(menu, "Start microphone").trigger()
    _action(menu, "Start screen sharing").trigger()
    assert len(questions) == 2
    assert (window.home / "config.json").read_bytes() == before
    assert window.screen_reader.state() == QProcess.ProcessState.NotRunning
    menu.deleteLater()


def test_confirmed_microphone_start_and_stop_refresh_menu_immediately(overlay, monkeypatch):
    window = overlay
    save_settings({"wake_word_enabled": True}, window.home)
    monkeypatch.setattr(QMessageBox, "exec", lambda _box: QMessageBox.StandardButton.Yes)
    _action(window.build_context_menu(), "Start microphone").trigger()
    assert load_raw_config(window.home)["always_listening_enabled"] is True
    assert "enabled in settings" in window.status.text()
    menu = window.build_context_menu()
    _action(menu, "Stop microphone").trigger()
    assert load_raw_config(window.home)["always_listening_enabled"] is False
    assert "stop requested" in window.status.text()
    assert _action(window.build_context_menu(), "Start microphone")


def test_start_does_not_invent_a_listening_mode(overlay, monkeypatch):
    window = overlay
    save_settings({"wake_word_enabled": False, "conversation_listening_enabled": False},
                  window.home, human_confirmed=True)
    monkeypatch.setattr(QMessageBox, "exec", lambda _box: pytest.fail("No valid listening mode was chosen"))
    assert not window.set_listening(True)
    assert load_raw_config(window.home)["always_listening_enabled"] is False
    assert "Choose wake-word" in window.status.text()


@pytest.mark.parametrize("sensor", ["microphone", "screen"])
def test_settings_changed_during_start_dialog_invalidate_old_approval(overlay, monkeypatch, sensor):
    window = overlay
    save_settings({"wake_word_enabled": True}, window.home)

    def change_mode_then_approve(_box):
        save_settings({"wake_word_enabled": False, "conversation_listening_enabled": True},
                      window.home, human_confirmed=True)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "exec", change_mode_then_approve)
    result = window.set_listening(True) if sensor == "microphone" else window.set_screen_sharing(True)
    assert not result
    current = load_raw_config(window.home)
    assert current["always_listening_enabled"] is False and current["screen_context_enabled"] is False
    assert "changed during approval" in window.status.text()


def test_fresh_menu_state_and_stale_stop_action_never_turn_recording_back_on(overlay, monkeypatch):
    window = overlay
    save_settings({"always_listening_enabled": True, "wake_word_enabled": True}, window.home, human_confirmed=True)
    # Do not refresh the overlay: menu labels must read the latest saved state.
    menu = window.build_context_menu()
    stop = _action(menu, "Stop microphone")
    save_settings({"always_listening_enabled": False}, window.home, human_confirmed=True)
    monkeypatch.setattr(QMessageBox, "exec", lambda _box: pytest.fail("A stale Stop action must never request Start"))
    stop.trigger()
    assert load_raw_config(window.home)["always_listening_enabled"] is False
    assert _action(window.build_context_menu(), "Start microphone")


def test_screen_start_requires_native_approval_then_stop_is_immediate(overlay, monkeypatch):
    window = overlay
    launches, stops = [], []

    class Reader(QProcess):
        def start(self, *args):
            launches.append(args)

    window.screen_reader = Reader(window)
    monkeypatch.setattr(QMessageBox, "exec", lambda _box: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(window, "stop_screen_reader", lambda: stops.append(True))
    assert window.set_screen_sharing(True)
    assert len(launches) == 1 and window.screen_requested
    assert load_raw_config(window.home)["screen_context_enabled"] is True
    assert "choose a screen" in window.status.text()
    _action(window.build_context_menu(), "Stop screen sharing").trigger()
    assert load_raw_config(window.home)["screen_context_enabled"] is False
    assert not window.screen_requested and stops == [True]
    assert "disabled" in window.status.text()
    assert _action(window.build_context_menu(), "Start screen sharing")


def test_debug_bar_toggle_applies_without_waiting_for_poll(overlay):
    window = overlay
    action = _action(window.build_context_menu(), "Debug emotion bars")
    assert not window.bars.isVisible()
    action.trigger()
    assert load_raw_config(window.home)["avatar_show_emotion_bars"] is True
    assert not window.bars.isHidden()


def test_rendering_submenu_reads_fresh_mode_and_applies_explicit_choice_immediately(overlay):
    window = overlay
    menu = _action(window.build_context_menu(), "Hologram appearance").menu()
    assert _action(menu, "2D particles").isChecked()
    assert not _action(menu, "3D depth").isChecked()
    _action(menu, "3D depth").trigger()
    assert load_raw_config(window.home)["avatar_render_mode"] == "3d"
    assert window.canvas.config["avatar_render_mode"] == "3d" and window.canvas.timer.interval() == 42
    assert "3D depth appearance selected" in window.status.text()
    fresh = _action(window.build_context_menu(), "Hologram appearance").menu()
    assert _action(fresh, "3D depth").isChecked() and not _action(fresh, "2D particles").isChecked()
    _action(fresh, "2D particles").trigger()
    assert window.canvas.config["avatar_render_mode"] == "2d" and window.canvas.timer.interval() == 34
    assert "lighter rendering" in window.status.text()
