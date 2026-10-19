"""Trusted native opt-in must preserve unrelated pending and saved preferences."""
import os

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from ai_os import github_mcp
from ai_os.config import load_raw_config
from ai_os.native_settings import SettingsWindow


@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication(["github-settings-test"])
    monkeypatch.setattr(github_mcp, "_binary", lambda home: home / "reviewed-server")
    settings = SettingsWindow(tmp_path, launch_companion=False)
    yield settings
    settings.poll.stop()
    settings.access_poll.stop()
    settings.conversation.grant_timer.stop()
    settings.conversation.cancel()
    settings.saved = settings.collect()
    settings.close()
    app.processEvents()


def test_opening_settings_never_enables_or_reads_account(window, monkeypatch):
    monkeypatch.setattr(github_mcp, "_token", lambda: pytest.fail("no credential read during setup"))
    window.refresh_github_status()
    assert "off" in window.github_status_label.text()
    assert not (window.home / "github-mcp.json").exists()


@pytest.mark.parametrize("cancel_stage", ["list", "confirmation"])
def test_cancel_preserves_scope_and_pending_preferences(window, monkeypatch, cancel_stage):
    github_mcp.configure_github(False, ["Aryan1771/ai-os"], home=window.home, human_confirmed=True)
    before = (window.home / "github-mcp.json").read_bytes()
    window.fields["avatar_scale"].setValue(87)
    pending = window.collect()
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *a: ("Other/repo", cancel_stage != "list"))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)
    assert not window.configure_github_access()
    assert (window.home / "github-mcp.json").read_bytes() == before
    assert window.collect() == pending
    assert window.save_button.isEnabled()


def test_approved_scope_is_separate_from_ai_voice_and_unsaved_preferences(window, monkeypatch):
    before = load_raw_config(window.home)
    window.fields["avatar_scale"].setValue(87)
    pending = window.collect()
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *a: ("Aryan1771/ai-os\nOther/project", True))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(github_mcp, "_token", lambda: pytest.fail("setup must not fetch credentials"))
    assert window.configure_github_access()
    preferences = github_mcp._config(window.home)
    assert preferences == {"enabled": True, "repositories": ["Aryan1771/ai-os", "Other/project"]}
    assert load_raw_config(window.home) == before
    assert window.collect() == pending
    assert "Read-only access enabled" in window.github_status_label.text()
    assert (window.home / "github-mcp.json").stat().st_mode & 0o777 == 0o600
    assert window.disable_github_access()
    assert not github_mcp._config(window.home)["enabled"]
    assert window.collect() == pending


def test_invalid_scope_does_not_reach_confirmation_or_enable(window, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *a: ("https://github.com/Other/repo", True))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: pytest.fail("invalid scope must not reach confirmation"))
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
    assert not window.configure_github_access()
    assert warnings and not (window.home / "github-mcp.json").exists()


def test_hologram_shade_cancel_keeps_saved_preferences(window, monkeypatch):
    before = window.collect()
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a: ("Electric", False))
    window.choose_accent()
    assert window.collect() == before
    assert not window.save_button.isEnabled()
