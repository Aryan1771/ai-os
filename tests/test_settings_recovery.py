"""Native recovery controls use temporary state and never launch real apps."""

import os
from pathlib import Path
import sqlite3

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
pytest.importorskip("PySide6")
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from ai_os.config import load_raw_config
from ai_os.avatar_overlay import AvatarOverlay
from ai_os import native_settings
from ai_os.native_settings import SettingsWindow
from ai_os.security.access_grants import GrantStore
from ai_os.settings_store import save_settings


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication(["regenos-recovery-test"])
    yield application


@pytest.fixture
def window(app, tmp_path):
    settings = SettingsWindow(tmp_path, launch_companion=False)
    yield settings
    settings.poll.stop()
    settings.access_poll.stop()
    settings.conversation.grant_timer.stop()
    settings.conversation.cancel()
    settings.saved = settings.collect()
    settings.close()


@pytest.fixture
def grant_dialogs(monkeypatch):
    """Allow the prerequisite check without depending on host packages."""
    original = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda path: path == Path("/usr/bin/bwrap") or original(path))
    monkeypatch.setattr(QInputDialog, "getInt", lambda *args, **kwargs: (15, True))
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args[1:]))
    return warnings


def test_unhide_button_remains_visible_outside_companion_page(app, window):
    window.show()
    for row in (0, window.navigation.count() - 1):
        window.navigation.setCurrentRow(row)
        app.processEvents()
        assert window.show_avatar_button.isVisible()
        assert window.show_avatar_button.isEnabled()


def test_unhide_restores_visibility_and_launches_in_selected_runtime(window, monkeypatch):
    save_settings({"avatar_enabled": False}, window.home)
    window.saved = load_raw_config(window.home)
    window.restore()
    edited_scale = window.fields["avatar_scale"].value() + 1
    window.fields["avatar_scale"].setValue(edited_scale)
    launches = []

    class CapturingProcess(QProcess):
        def startDetached(self):
            launches.append((self.program(), self.arguments(), self.processEnvironment().value("AI_OS_HOME")))
            return True, 123

    monkeypatch.setattr(native_settings, "QProcess", CapturingProcess)
    window.show_companion()
    assert load_raw_config(window.home)["avatar_enabled"] is True
    assert window.fields["avatar_enabled"].isChecked()
    assert window.fields["avatar_scale"].value() == edited_scale
    assert load_raw_config(window.home)["avatar_scale"] != edited_scale
    assert len(launches) == 1
    assert launches[0][1] == ["-m", "ai_os.avatar_overlay", "--show"]
    assert launches[0][2] == str(window.home)


def test_failed_detached_launch_is_not_reported_as_opening(window, monkeypatch):
    class FailedProcess(QProcess):
        def startDetached(self):
            return False, -1

    monkeypatch.setattr(native_settings, "QProcess", FailedProcess)
    window.show_companion()
    assert "could not start" in window.status.text().lower()


@pytest.mark.parametrize("cancel_at", ["duration", "confirmation"])
def test_cancel_full_access_preserves_mode_and_unsaved_edits(window, grant_dialogs, monkeypatch, cancel_at):
    edited_scale = window.fields["avatar_scale"].value() + 1
    window.fields["avatar_scale"].setValue(edited_scale)
    if cancel_at == "duration":
        monkeypatch.setattr(QInputDialog, "getInt", lambda *args, **kwargs: (15, False))
    else:
        monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No)
    window.enable_full_access()
    assert load_raw_config(window.home)["command_access"] == "restricted"
    assert window.fields["avatar_scale"].value() == edited_scale
    assert "grant" not in GrantStore(window.home).status("default")


def test_grant_is_created_only_after_native_confirmation(window, grant_dialogs, monkeypatch):
    edited_scale = window.fields["avatar_scale"].value() + 1
    window.fields["avatar_scale"].setValue(edited_scale)
    checks = []

    def approve(box):
        checks.append(True)
        assert box.standardButton(box.defaultButton()) == QMessageBox.StandardButton.No
        assert load_raw_config(window.home)["command_access"] == "restricted"
        assert "grant" not in GrantStore(window.home).status("default")
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "exec", approve)
    window.enable_full_access()
    assert checks
    assert load_raw_config(window.home)["command_access"] == "supervised"
    assert window.fields["avatar_scale"].value() == edited_scale
    assert load_raw_config(window.home)["avatar_scale"] != edited_scale
    grant = GrantStore(window.home).status("default")["grant"]
    assert grant["kind"] == "user"
    assert window.save()
    assert GrantStore(window.home).status("default")["grant"] == grant


@pytest.mark.parametrize("failing_method,error", [
    ("request", sqlite3.OperationalError("database busy")),
    ("confirm", PermissionError("request expired")),
])
def test_grant_failure_is_reported_without_throwing(window, grant_dialogs, monkeypatch, failing_method, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(GrantStore, failing_method, fail)
    window.enable_full_access()
    assert grant_dialogs
    assert "grant" not in GrantStore(window.home).status("default")


def test_expired_grant_status_returns_to_off(window, grant_dialogs, monkeypatch):
    from ai_os.security import access_grants

    window.enable_full_access()
    window.refresh_full_access_status()
    assert "active" in window.full_access_status.text().lower()
    now = access_grants.time.monotonic()
    monkeypatch.setattr(access_grants.time, "monotonic", lambda: now + 901)
    window.refresh_full_access_status()
    assert "off" in window.full_access_status.text().lower()


def test_reveal_checks_persistent_preference_even_when_refresh_snapshot_is_unchanged(app, tmp_path):
    save_settings({"avatar_enabled": True}, tmp_path)
    overlay = AvatarOverlay(tmp_path)
    try:
        overlay.refresh()
        overlay.hide()
        assert not overlay.isVisible()
        overlay.reveal_if_enabled()
        app.processEvents()
        assert overlay.isVisible()
        save_settings({"avatar_enabled": False}, tmp_path)
        overlay.hide()
        overlay.reveal_if_enabled()
        app.processEvents()
        assert not overlay.isVisible()
    finally:
        overlay.timer.stop()
        overlay.close()
