import os
from pathlib import Path

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
pytest.importorskip("PySide6")
from PySide6.QtGui import QFontDatabase, QFontMetrics
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ai_os.avatar_overlay import AvatarOverlay
from ai_os.config import load_raw_config
from ai_os.native_settings import SettingsWindow
from ai_os.native_widgets import LocalInstance
from ai_os.settings_store import save_settings


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication(["regenos-test"])
    application.setStyle("Fusion")
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
    if os.name == "nt" and font.is_file():
        QFontDatabase.addApplicationFont(str(font))
    return application


def test_native_settings_persist_emotion_bars_and_toggle(app, tmp_path):
    window = SettingsWindow(tmp_path, launch_companion=False)
    window.show()
    window.fields["avatar_enabled"].setChecked(False)
    window.fields["avatar_emotions.joy"].setValue(84)
    window.fields["avatar_motion"].setValue(22)
    window.fields["branding.brand_name"].setText("REgenOS Lab")
    assert window.save()
    saved = load_raw_config(tmp_path)
    assert saved["avatar_emotions"]["joy"] == 84
    assert saved["avatar_motion"] == 22
    assert not saved["avatar_enabled"]
    assert window.windowTitle() == "REgenOS Lab Settings"
    window.close()


def test_native_pages_render_and_canvas_has_visible_pixels(app, tmp_path):
    window = SettingsWindow(tmp_path, launch_companion=False)
    window.resize(780, 570)
    window.show()
    QTest.qWait(600)
    assert QFontMetrics(window.save_button.font()).inFontUcs4(ord("A"))
    image = window.canvas.grab().toImage()
    visible_colors = {
        image.pixelColor(x, y).name()
        for x in range(0, image.width(), 3)
        for y in range(0, image.height(), 3)
    }
    assert len(visible_colors) >= 4
    for index in range(window.pages.count()):
        window.navigation.setCurrentRow(index)
        app.processEvents()
        assert window.pages.currentWidget().isVisible()
        assert window.save_button.geometry().right() < window.width()
    window.close()


def test_overlay_live_visibility_scale_and_bars(app, tmp_path):
    save_settings({"avatar_enabled": False}, tmp_path)
    overlay = AvatarOverlay(tmp_path)
    assert not overlay.isVisible()
    save_settings(
        {"avatar_enabled": True, "avatar_scale": 60, "avatar_show_emotion_bars": False}, tmp_path
    )
    overlay.refresh()
    app.processEvents()
    assert overlay.isVisible()
    assert not overlay.bars.isVisible()
    assert overlay.canvas.height() == 138
    assert overlay.canvas.geometry().right() < overlay.width()
    assert overlay.grab().toImage().pixelColor(0, 0).alpha() == 0
    save_settings({"avatar_enabled": False}, tmp_path)
    overlay.refresh()
    assert not overlay.isVisible()
    overlay.timer.stop()
    overlay.close()


def test_native_single_instance_activates_existing_window(app, tmp_path):
    raised = []
    first = LocalInstance(tmp_path, "settings")
    second = LocalInstance(tmp_path, "settings")
    assert first.acquire(lambda: raised.append(True))
    assert first.lock.staleLockTime() == 0
    assert not second.acquire(lambda: None)
    app.processEvents()
    assert raised == [True]
    first.server.close()
    first.lock.unlock()
