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


def test_compatibility_launchers_use_python_settings(monkeypatch):
    from ai_os import hub_launcher, settings_server

    monkeypatch.setattr("ai_os.native_settings.main", lambda: 17)
    assert hub_launcher.main() == 17
    assert settings_server.main() == 17


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
    window.navigation.setCurrentRow(1)  # Companion page, after Conversation.
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


def test_memory_widget_inspection_is_explicit_and_forget_is_confirmed(app, tmp_path, monkeypatch):
    from ai_os.conversation_memory import ConversationMemory
    from ai_os.memory_widget import MemoryWidget

    memory = ConversationMemory(tmp_path)
    memory.append('Favorite color is lavender', 'Understood')
    widget = MemoryWidget(tmp_path)
    assert not widget.output.toPlainText()
    widget.inspect()
    assert 'lavender' in widget.output.toPlainText()
    widget.value.setPlainText('lavender')
    monkeypatch.setattr(widget, 'confirmed', lambda message: False)
    widget.forget()
    assert memory.history()
    monkeypatch.setattr(widget, 'confirmed', lambda message: True)
    widget.forget()
    assert memory.history() == []
    assert 'lavender' not in widget.output.toPlainText()


def test_chat_cancel_reaps_backend_and_empty_input_is_rejected(app, tmp_path):
    import sys

    from PySide6.QtCore import QProcess

    from ai_os.conversation_widget import ConversationWidget

    widget = ConversationWidget(tmp_path)
    widget.send()
    assert widget.process.state() == QProcess.ProcessState.NotRunning
    assert '8000' in widget.status.text()
    widget.process.start(sys.executable, ['-c', 'import time; time.sleep(30)'])
    assert widget.process.waitForStarted(2000)
    widget.cancel()
    assert widget.process.state() == QProcess.ProcessState.NotRunning
    assert not widget.timer.isActive()


def test_native_command_review_denies_then_executes_exact_proposal(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtCore import QProcess
    from ai_os.conversation_widget import ConversationWidget

    save_settings({"command_access": "supervised"}, tmp_path, human_confirmed=True)
    widget = ConversationWidget(tmp_path)
    target = tmp_path / "approved-only.txt"
    proposal = {"tool": "run_command", "arguments": {"command": ["/usr/bin/touch", str(target)]}}
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
    assert not widget.approve_command(proposal)
    assert not target.exists()
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    assert widget.approve_command(proposal)
    for _ in range(100):
        QTest.qWait(50)
        if widget.process.state() == QProcess.ProcessState.NotRunning:
            break
    assert target.exists()
    assert widget.process.state() == QProcess.ProcessState.NotRunning
    widget.cancel()
