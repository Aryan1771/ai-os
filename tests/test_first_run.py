"""Post-install onboarding is explicit, isolated and does not provision a system."""
from __future__ import annotations

from copy import deepcopy
import json
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QListWidget, QMainWindow

from ai_os import first_run as setup
from ai_os.config import DEFAULT_CONFIG


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["first-run-test"])


def _final_page(wizard):
    wizard.acknowledge.setChecked(True)
    wizard.setStartId(wizard.final_page)
    wizard.restart()


def test_open_cancel_and_early_accept_do_not_create_runtime_or_probe(app, tmp_path, monkeypatch):
    home = tmp_path / "untouched-runtime"
    monkeypatch.setattr(setup, "readiness_snapshot", lambda _home: pytest.fail("Opening setup probed the runtime"))
    wizard = setup.create_wizard(home, live=False)
    assert not home.exists() and wizard.worker is None
    assert not wizard.acknowledge.isChecked()
    wizard.accept()
    assert not home.exists()
    wizard.language.setCurrentIndex(wizard.language.findData("hi"))
    wizard.reject()
    assert not home.exists()


def test_finish_requires_final_page_and_acknowledgement_before_marker(app, tmp_path):
    home = tmp_path / "runtime"
    wizard = setup.create_wizard(home, live=False)
    wizard.setStartId(wizard.final_page)
    wizard.restart()
    wizard.accept()
    assert not setup.completion_path(home).exists()
    wizard.acknowledge.setChecked(True)
    wizard.accept()
    assert not setup.setup_needed(home, live=False)
    marker = json.loads(setup.completion_path(home).read_text())
    assert set(marker) == {"version", "completed", "completed_at"}
    assert not (home / "config.json").exists()  # Unedited defaults need no config write.


def test_explicit_finish_changes_only_edited_choices_and_preserves_private_assets(app, tmp_path):
    config = deepcopy(DEFAULT_CONFIG) | {
        "always_listening_enabled": True, "screen_context_enabled": True,
        "memory_enabled": False, "memory_allow_remote": True,
        "command_access": "supervised", "SYNTHETIC_PRIVATE_FIELD": "preserve",
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    private = tmp_path / "data/private"
    private.mkdir(parents=True)
    memory = private / "conversations.sqlite3"
    memory.write_bytes(b"SYNTHETIC_PRIVATE_DATABASE_DO_NOT_READ_OR_MIGRATE")
    model = tmp_path / "models/synthetic-model.bin"
    model.parent.mkdir()
    model.write_bytes(b"SYNTHETIC_MODEL_DO_NOT_CHANGE")
    wizard = setup.create_wizard(tmp_path, live=False)
    wizard.language.setCurrentIndex(wizard.language.findData("hi"))
    wizard.personality.setCurrentIndex(wizard.personality.findData("focused"))
    _final_page(wizard)
    wizard.accept()
    saved = json.loads(path.read_text())
    assert saved == config | {"whisper_language": "hi", "companion_personality": "focused"}
    assert memory.read_bytes() == b"SYNTHETIC_PRIVATE_DATABASE_DO_NOT_READ_OR_MIGRATE"
    assert model.read_bytes() == b"SYNTHETIC_MODEL_DO_NOT_CHANGE"
    assert setup.completion_path(tmp_path).stat().st_mode & 0o777 == 0o600
    assert private.stat().st_mode & 0o777 == 0o700


def test_automatic_language_is_visible_and_not_silently_changed(app, tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"whisper_language": "auto", "reply_language_mode": "match"}))
    before = config.read_bytes()
    wizard = setup.create_wizard(tmp_path, live=False)
    assert wizard.language.currentData() == "auto"
    assert "Automatic" in wizard.language.currentText()
    _final_page(wizard)
    wizard.accept()
    assert config.read_bytes() == before


@pytest.mark.parametrize("confirmed", [False, None, 1, "yes"])
def test_completion_api_rejects_non_explicit_confirmation_without_writes(tmp_path, confirmed):
    home = tmp_path / "untouched"
    with pytest.raises(PermissionError):
        setup.complete_setup(home, human_confirmed=confirmed, live=False)
    assert not home.exists()


@pytest.mark.parametrize("changes", [{"always_listening_enabled": True}, {"allow_external_apis": True},
                                      {"command_access": "supervised"}, [], "approve"])
def test_finish_cannot_grant_permissions_or_accept_arbitrary_config(tmp_path, changes):
    home = tmp_path / "untouched"
    with pytest.raises(ValueError):
        setup.complete_setup(home, changes, human_confirmed=True, live=False)
    assert not home.exists()


def test_changed_same_preference_is_not_overwritten_and_unrelated_edits_are_preserved(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"companion_personality": "warm", "avatar_render_mode": "2d"}))
    baseline = setup.read_preferences(tmp_path)
    path.write_text(json.dumps({"companion_personality": "calm", "avatar_render_mode": "3d"}))
    with pytest.raises(ValueError, match="changed elsewhere"):
        setup.complete_setup(tmp_path, {"companion_personality": "focused"}, baseline=baseline,
                             human_confirmed=True, live=False)
    assert not setup.completion_path(tmp_path).exists()
    setup.complete_setup(tmp_path, {"whisper_language": "hi"}, baseline=baseline,
                         human_confirmed=True, live=False)
    saved = setup.read_preferences(tmp_path)
    assert saved["companion_personality"] == "calm" and saved["avatar_render_mode"] == "3d"
    assert saved["whisper_language"] == "hi"


@pytest.mark.parametrize("kind", ["marker", "private-directory"])
def test_completion_rejects_symlink_destinations_without_touching_targets(tmp_path, kind):
    home, outside = tmp_path / "runtime", tmp_path / "outside"
    home.mkdir()
    outside.mkdir()
    target = outside / "preserve.json"
    target.write_text("SYNTHETIC_TARGET_MUST_REMAIN")
    if kind == "marker":
        setup.completion_path(home).parent.mkdir(parents=True)
        setup.completion_path(home).symlink_to(target)
    else:
        (home / "data").mkdir()
        (home / "data/private").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        setup.complete_setup(home, human_confirmed=True, live=False)
    assert target.read_text() == "SYNTHETIC_TARGET_MUST_REMAIN"
    assert not (outside / "first-run.json").exists()


@pytest.mark.parametrize("marker", [{}, {"version": True, "completed": True, "completed_at": 1},
    {"version": 1, "completed": "true", "completed_at": 1},
    {"version": 1, "completed": True, "completed_at": True},
    {"version": 1, "completed": True, "completed_at": int(time.time()) + 99999}])
def test_malformed_or_future_completion_marker_does_not_suppress_setup(tmp_path, marker):
    path = setup.completion_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(marker))
    assert setup.setup_needed(tmp_path, live=False)


def test_completed_and_live_if_needed_gating_exits_before_any_gui(tmp_path, monkeypatch):
    setup.complete_setup(tmp_path, human_confirmed=True, live=False)
    monkeypatch.setattr(setup, "AI_OS_HOME", tmp_path)
    monkeypatch.setattr(setup, "create_wizard", lambda *_args, **_kwargs: pytest.fail("Unneeded GUI opened"))
    monkeypatch.setattr("sys.argv", ["regenos-setup", "--if-needed"])
    assert setup.main() == 0
    monkeypatch.setenv("REGENOS_LIVE_SESSION", "1")
    assert setup.main() == 0


def test_live_preview_cannot_save_choices_or_completion(app, tmp_path):
    home = tmp_path / "live-runtime"
    wizard = setup.create_wizard(home, live=True)
    assert not wizard.language.isEnabled()
    _final_page(wizard)
    wizard.accept()
    assert not home.exists()
    assert not setup.setup_needed(home, live=True)
    with pytest.raises(PermissionError):
        setup.complete_setup(home, human_confirmed=True, live=True)


def test_readiness_is_static_and_does_not_initialize_missing_runtime(tmp_path, monkeypatch):
    home = tmp_path / "untouched"
    monkeypatch.setattr(setup.shutil, "which", lambda _name: None)
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: pytest.fail("Readiness launched a command"))
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("Readiness launched a process"))
    result = setup.readiness_snapshot(home)
    assert result["scope"] == "static_presence_only"
    assert all(set(item) == {"name", "present"} for item in result["items"])
    assert not home.exists()


def test_invalid_saved_config_is_preserved_and_prevents_finish(app, tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{broken synthetic configuration")
    wizard = setup.create_wizard(tmp_path, live=False)
    _final_page(wizard)
    wizard.accept()
    assert not setup.completion_path(tmp_path).exists()
    assert config.read_text() == "{broken synthetic configuration"
    assert "could not be completed" in wizard.finish_status.text()
    wizard.reject()


def test_finish_does_not_replace_a_symlinked_preference_file(tmp_path):
    target = tmp_path / "external-config.json"
    target.write_text(json.dumps({"whisper_language": "en"}))
    home = tmp_path / "runtime"
    home.mkdir()
    (home / "config.json").symlink_to(target)
    with pytest.raises(ValueError, match="destination needs review"):
        setup.complete_setup(home, {"whisper_language": "hi"}, human_confirmed=True, live=False)
    assert (home / "config.json").is_symlink()
    assert json.loads(target.read_text())["whisper_language"] == "en"
    assert not setup.completion_path(home).exists()


def test_settings_links_reuse_one_panel_preserve_runtime_and_do_not_start_companion(app, tmp_path, monkeypatch):
    launches = []

    class Settings(QMainWindow):
        def __init__(self, home, *, launch_companion):
            super().__init__()
            launches.append((home, launch_companion))
            self.navigation = QListWidget()
            self.navigation.addItems(list(setup.SETTINGS_PAGES.values()))
            self.unsaved_draft = "SYNTHETIC_DRAFT"

    monkeypatch.setattr("ai_os.native_settings.SettingsWindow", Settings)
    wizard = setup.create_wizard(tmp_path, live=False)
    wizard.open_settings("voice")
    panel = wizard.settings_window
    assert panel.navigation.currentItem().text() == "Voice & listening"
    wizard.open_settings("permissions")
    assert wizard.settings_window is panel and panel.unsaved_draft == "SYNTHETIC_DRAFT"
    assert panel.navigation.currentItem().text() == "Permissions"
    assert launches == [(tmp_path, False)]
    panel.close()
    wizard.reject()


def test_inventory_requires_click_is_bounded_and_cancel_cleans_worker(app, tmp_path, monkeypatch):
    from PySide6 import QtCore
    launches = []

    class Worker(QProcess):
        def start(self, program, arguments):
            launches.append((program, arguments, self.processEnvironment().value("AI_OS_HOME")))

    monkeypatch.setattr(QtCore, "QProcess", Worker)
    wizard = setup.create_wizard(tmp_path, live=False)
    assert not launches and wizard.worker is None
    wizard.start_inventory()
    assert launches == [(os.sys.executable, ["-m", "ai_os.first_run", "--inventory"], str(tmp_path))]
    assert wizard.worker_timer.isActive() and wizard.worker_timer.interval() == 8000
    wizard.reject()
    assert wizard.worker is None and not wizard.worker_timer.isActive()
    assert not setup.completion_path(tmp_path).exists()
