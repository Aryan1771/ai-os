"""The cancelled active chat is a separate ephemeral reference, never new intent."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QByteArray, QProcess
from PySide6.QtWidgets import QApplication

from ai_os import conversation_widget as chat


@pytest.fixture
def widget(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication(["steering-reference-test"])

    class Backend(QProcess):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.phase = QProcess.ProcessState.NotRunning
            self.requests = []

        def state(self):
            return self.phase

        def start(self, *_args):
            self.phase = QProcess.ProcessState.Running

        def write(self, payload):
            self.requests.append(json.loads(bytes(payload)))
            return len(payload)

        def closeWriteChannel(self):
            pass

        def terminate(self):
            self.phase = QProcess.ProcessState.NotRunning

        def waitForFinished(self, _timeout):
            self.phase = QProcess.ProcessState.NotRunning
            return True

        def readAllStandardOutput(self):
            return QByteArray(b'{"ok":true,"response":{"type":"text","content":"Synthetic reply"}}')

    monkeypatch.setattr(chat, "QProcess", Backend)
    window = chat.ConversationWidget(tmp_path, compact=True)
    cancel = window.cancel
    yield window
    cancel()
    window.grant_timer.stop()
    window.close()
    app.processEvents()


def _send(window, text):
    window.input.setPlainText(text)
    window.send()
    return window.process


def test_steer_sends_only_latest_intent_with_separate_same_session_reference(widget):
    widget.session.setText("synthetic-session")
    old = _send(widget, "Open an application and make the interface blue")
    widget.input.setPlainText("Do not open anything. Only describe a blue palette.")
    assert widget.steer()
    current = widget.process.requests[-1]
    assert old.state() == QProcess.ProcessState.NotRunning
    assert current == {"action": "chat", "session": "synthetic-session",
                       "text": "Do not open anything. Only describe a blue palette.",
                       "interrupted_context": "Open an application and make the interface blue"}
    assert widget._active_chat["text"] == current["text"]


def test_reference_is_single_previous_request_and_bounded(widget):
    _send(widget, "A" * 8000)
    widget.input.setPlainText("A short correction")
    assert widget.steer()
    first = widget.process.requests[-1]
    assert len(first["interrupted_context"]) == 4000
    widget.input.setPlainText("Another correction")
    assert widget.steer()
    assert widget.process.requests[-1]["interrupted_context"] == "A short correction"
    assert "A" * 100 not in json.dumps(widget.process.requests[-1])


@pytest.mark.parametrize("change", ["session", "generation"])
def test_stale_session_or_generation_does_not_reuse_original_text(widget, change):
    _send(widget, "Synthetic original that must not cross scope")
    if change == "session":
        widget.session.setText("different-session")
    else:
        widget._active_chat["generation"] -= 1
    widget.input.setPlainText("A new request")
    assert widget.steer()
    assert "interrupted_context" not in widget.process.requests[-1]


def test_cancel_failure_does_not_submit_reference_or_new_request(widget, monkeypatch):
    original = _send(widget, "The old request")
    widget.input.setPlainText("Do this instead")
    monkeypatch.setattr(widget, "cancel", lambda: False)
    assert not widget.steer()
    assert widget.process is original and len(original.requests) == 1
    assert widget.input.toPlainText() == "Do this instead"


def test_finish_failure_cancel_and_fresh_send_clear_previous_context(widget):
    process = _send(widget, "A completed original")
    process.phase = QProcess.ProcessState.NotRunning
    widget.finished(0, QProcess.ExitStatus.NormalExit)
    assert widget._active_chat is None
    fresh = _send(widget, "A separate new request")
    assert "interrupted_context" not in fresh.requests[-1]
    fresh.phase = QProcess.ProcessState.NotRunning
    widget.failed(QProcess.ProcessError.FailedToStart)
    assert widget._active_chat is None
    _send(widget, "Cancelled original")
    widget.cancel()
    assert widget._active_chat is None


def test_voice_or_approved_request_cannot_become_steering_reference(widget):
    _send(widget, "An unrelated old chat")
    widget.process.phase = QProcess.ProcessState.NotRunning
    widget._start_reviewed_request({"action": "approved_command", "confirmed": True}, "Synthetic review")
    assert widget._active_chat is None
    widget.input.setPlainText("An independent correction")
    assert widget.steer()
    assert "interrupted_context" not in widget.process.requests[-1]


def test_cancelled_original_is_not_written_to_history_again_or_memory(widget):
    original = "SYNTHETIC_INTERRUPTED_REFERENCE"
    _send(widget, original)
    widget.input.setPlainText("A short corrected current request")
    assert widget.steer()
    assert widget.history.toPlainText().count(original) == 1  # Original explicit display only.
    assert not (widget.home / "data/private/conversations.sqlite3").exists()


def test_send_button_is_an_ordinary_fresh_request(widget):
    widget.input.setPlainText("A message sent using the native button")
    widget.send_button.click()
    assert widget.process.requests[-1] == {"action": "chat", "text": "A message sent using the native button",
                                           "session": "default"}


def test_invalid_reference_does_not_clear_input_or_send(widget):
    widget.input.setPlainText("Keep this draft")
    widget.send(interrupted_context="A" * 4001)
    assert widget.input.toPlainText() == "Keep this draft"
    assert widget.process.requests == []


def test_normal_completion_does_not_kill_a_completed_desktop_launch(widget, monkeypatch):
    calls = []
    _send(widget, "Launch a synthetic app")
    widget.process.phase = QProcess.ProcessState.NotRunning
    widget.worker_group = 991001
    monkeypatch.setattr(chat.os, "killpg", lambda group, sig: calls.append((group, sig)))
    widget.finished(0, QProcess.ExitStatus.NormalExit)
    assert calls == [] and widget.worker_group is None
