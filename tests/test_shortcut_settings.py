"""Native scope review cannot silently apply shortcuts or save other edits."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from ai_os.config import load_raw_config
from ai_os.native_settings import SettingsWindow


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication(["shortcut-settings-test"])
    window = SettingsWindow(tmp_path, launch_companion=False)
    yield window
    window.shortcut_process = None
    window.poll.stop()
    window.access_poll.stop()
    window.conversation.grant_timer.stop()
    window.conversation.cancel()
    window.saved = window.collect()
    window.close()
    app.processEvents()


@pytest.mark.parametrize("answer, expected_count", [(QMessageBox.StandardButton.No, 0),
                                                     (QMessageBox.StandardButton.Yes, 1)])
def test_only_explicit_yes_submits_exact_scope_and_preserves_unsaved_fields(window, monkeypatch, answer, expected_count):
    before = load_raw_config(window.home)
    window.fields["avatar_scale"].setValue(87)
    pending = window.collect()
    requests = []
    monkeypatch.setattr(window, "run_shortcut_action", lambda *a: requests.append(a))
    def confirm(box):
        assert box.defaultButton().text() == "&No"
        assert "Super + Alt + A" in box.text()
        return answer
    monkeypatch.setattr(QMessageBox, "exec", confirm)
    proposal = {"ok": True, "supported": True, "session": "GNOME", "revision": "synthetic",
                "bindings": [{"accelerator": "<Super><Alt>a", "command": "/reviewed/python -m ai_os.hub_launcher"}]}
    window.shortcut_result("propose", proposal)
    assert len(requests) == expected_count
    if requests:
        assert requests[0] == ("apply", {"proposal": proposal, "confirmed": True})
    assert window.collect() == pending
    assert load_raw_config(window.home) == before


def test_conflicts_never_reach_confirmation_or_apply(window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: pytest.fail("conflict must stop"))
    monkeypatch.setattr(window, "run_shortcut_action", lambda *a: pytest.fail("conflict applied"))
    window.shortcut_result("propose", {"ok": False, "conflicts": [{"id": "chat"}]})
    assert "conflicts" in window.shortcut_status.text()


def test_restore_rejects_external_backup_location_and_cancel_preserves_scope(window, monkeypatch):
    monkeypatch.setattr(window, "run_shortcut_action", lambda *a: pytest.fail("rollback was not approved"))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (str(window.home / ("a" * 32 + ".json")), ""))
    window.restore_shortcut_backup()
    assert "original directory" in window.shortcut_status.text()
    path = window.home / "backups/desktop-shortcuts" / ("a" * 32 + ".json")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (str(path), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    window.restore_shortcut_backup()


def test_close_waits_for_in_progress_shortcut_change(window):
    window.shortcut_process = object()
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert "finish" in window.shortcut_status.text()
