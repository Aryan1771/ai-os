"""Keyboard, steering races and public activity; no model, microphone or tools."""
import json
import os
import sys
import time

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ai_os.config import atomic_json
from ai_os.conversation_widget import ConversationInput, ConversationWidget
from ai_os.quick_chat import QuickChatWindow
from ai_os.request_activity import record


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["quick-chat-test"])


def test_enter_sends_shift_adds_line_and_ctrl_steers(app):
    composer = ConversationInput()
    events = []
    composer.sendRequested.connect(lambda: events.append("send"))
    composer.steerRequested.connect(lambda: events.append("steer"))
    composer.setPlainText("hello")
    composer.moveCursor(composer.textCursor().MoveOperation.End)
    QTest.keyClick(composer, Qt.Key.Key_Return)
    assert events == ["send"] and composer.toPlainText() == "hello"
    QTest.keyClick(composer, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert composer.toPlainText() == "hello\n"
    QTest.keyClick(composer, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert events == ["send", "steer"]


def test_steering_reaps_old_process_preserves_session_and_ignores_stale_callbacks(app, tmp_path, monkeypatch):
    widget = ConversationWidget(tmp_path, compact=True)
    widget.session.setText("synthetic-session")
    old, generation = widget.process, widget.request_generation
    old.start(sys.executable, ["-c", "import time; time.sleep(30)"])
    assert old.waitForStarted(1000)
    widget.input.setPlainText("A correction to the current request")
    sent = []
    monkeypatch.setattr(widget, "send", lambda: sent.append((widget.input.toPlainText(), widget.session.text(), widget.process)))
    assert widget.steer()
    assert old.state() == old.ProcessState.NotRunning
    assert sent == [("A correction to the current request", "synthetic-session", widget.process)]
    assert widget.process is not old and widget.request_generation > generation
    monkeypatch.setattr(widget, "finished", lambda *a: pytest.fail("Stale callback consumed a new response"))
    widget._finished_current(old, generation, 0, None)
    widget.cancel()
    widget.grant_timer.stop()
    widget.close()


def test_empty_steering_does_not_stop_work(app, tmp_path, monkeypatch):
    widget = ConversationWidget(tmp_path)
    monkeypatch.setattr(widget, "cancel", lambda: pytest.fail("Empty steering cancelled work"))
    assert not widget.steer()
    widget.grant_timer.stop()
    widget.close()


def test_activity_contains_only_public_tool_name_no_arguments_or_private_reasoning(app, tmp_path, monkeypatch):
    widget = ConversationWidget(tmp_path)
    monkeypatch.setenv("AI_OS_REQUEST_ID", widget.process.processEnvironment().value("AI_OS_REQUEST_ID"))
    record(tmp_path, "tool_started", "list_directory")
    event = json.loads((tmp_path / "run/request-progress.json").read_text())
    assert set(event) == {"request_id", "state", "tool", "updated_at"}
    # This is a harmless non-model child; operational reporting never reads stdout.
    widget.process.start(sys.executable, ["-c", "import time; time.sleep(30)"])
    assert widget.process.waitForStarted(1000)
    record(tmp_path, "tool_started", "list_directory")
    widget.refresh_activity()
    assert "Using list_directory" in widget.activity.toPlainText()
    widget.cancel()
    widget.grant_timer.stop()
    widget.close()


def test_other_request_status_and_unregistered_names_are_not_rendered(app, tmp_path):
    widget = ConversationWidget(tmp_path)
    widget.process.start(sys.executable, ["-c", "import time; time.sleep(30)"])
    assert widget.process.waitForStarted(1000)
    atomic_json(tmp_path / "run/request-progress.json", {"request_id": "other", "updated_at": time.time(), "state": "tool_started", "tool": "private_secret"})
    widget.refresh_activity()
    assert "private_secret" not in widget.activity.toPlainText()
    widget.cancel()
    widget.grant_timer.stop()
    widget.close()


def test_quick_window_reports_actual_mic_state_and_remains_native(app, tmp_path):
    window = QuickChatWindow(tmp_path)
    assert window.windowTitle() == "REgenOS Chat"
    assert "microphone off" in window.mode_indicator.text()
    assert window.conversation.input.isEnabled()
    window.close()
