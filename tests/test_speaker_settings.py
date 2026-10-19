"""Native speaker setup and saved language controls; no microphone or model calls."""
import json
import os

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from ai_os.config import load_config, load_raw_config
from ai_os.native_settings import SettingsWindow
from ai_os.settings_store import PROTECTED_KEYS, protected_changes, save_settings


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["speaker-settings-test"])


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


def fake_setup_dialog(monkeypatch, return_value=QDialog.DialogCode.Rejected):
    from ai_os import speaker_setup
    calls = []
    class FakeDialog:
        def __init__(self, home, parent=None):
            calls.append((home, parent, load_raw_config(home)))
        def exec(self):
            return return_value
    monkeypatch.setattr(speaker_setup, "SpeakerSetupDialog", FakeDialog)
    return calls


def test_setup_confirmation_cancel_preserves_disk_and_all_unsaved_fields(window, monkeypatch):
    before = load_raw_config(window.home)
    model = str(window.home / "new-speaker.onnx")
    window.fields["speaker_model"].setText(model)
    window.fields["speaker_recognition_enabled"].setChecked(True)
    window.fields["avatar_scale"].setValue(87)
    pending = window.collect()
    calls = fake_setup_dialog(monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Cancel)
    window.setup_speaker()
    assert not calls
    assert load_raw_config(window.home) == before
    assert window.collect() == pending
    assert window.saved == before


def test_approved_setup_saves_only_model_and_keeps_other_unsaved_preferences(window, monkeypatch):
    before = load_raw_config(window.home)
    model = str(window.home / "new-speaker.onnx")
    window.fields["speaker_model"].setText(model)
    window.fields["speaker_recognition_enabled"].setChecked(True)
    window.fields["speaker_threshold"].setValue(.86)
    window.fields["reply_language_mode"].setCurrentIndex(window.fields["reply_language_mode"].findData("match"))
    window.fields["avatar_scale"].setValue(87)
    pending = window.collect()
    calls = fake_setup_dialog(monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Apply)
    window.setup_speaker()
    saved = load_raw_config(window.home)
    assert {k for k in saved if saved[k] != before[k]} == {"speaker_model"}
    assert saved["speaker_model"] == model
    assert not saved["speaker_recognition_enabled"]
    assert window.collect() == pending
    assert window.saved == saved
    assert len(calls) == 1 and calls[0][0] == window.home and calls[0][1] is window
    assert calls[0][2]["speaker_model"] == model
    assert not calls[0][2]["speaker_recognition_enabled"]


def test_unchanged_saved_model_opens_setup_without_saving_other_edits(window, monkeypatch):
    model = str(window.home / "already-selected.onnx")
    before = save_settings({"speaker_model":model}, window.home, human_confirmed=True)
    window.saved = before
    window.restore()
    window.fields["speaker_threshold"].setValue(.88)
    pending = window.collect()
    calls = fake_setup_dialog(monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: pytest.fail("unchanged model must not ask to resave"))
    window.setup_speaker()
    assert len(calls) == 1
    assert load_raw_config(window.home) == before
    assert window.collect() == pending


def test_failed_model_save_does_not_open_wizard_or_discard_pending_changes(window, monkeypatch):
    before = load_raw_config(window.home)
    window.fields["speaker_model"].setText("invalid\npath")
    window.fields["avatar_scale"].setValue(87)
    pending = window.collect()
    calls = fake_setup_dialog(monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Apply)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
    window.setup_speaker()
    assert not calls and warnings
    assert load_raw_config(window.home) == before
    assert window.collect() == pending


@pytest.mark.parametrize("setting,value", [("speaker_recognition_enabled",True),
                                            ("speaker_model","/tmp/local-speaker.onnx"),
                                            ("speaker_threshold",.85)])
def test_speaker_controls_require_explicit_confirmation(tmp_path, setting, value):
    before = load_raw_config(tmp_path)
    assert setting in PROTECTED_KEYS
    assert setting in protected_changes(before, {setting:value})
    with pytest.raises(PermissionError):
        save_settings({setting:value}, tmp_path)
    assert load_raw_config(tmp_path) == before
    save_settings({setting:value}, tmp_path, human_confirmed=True)
    assert load_raw_config(tmp_path)[setting] == value


def test_disabling_filter_is_protected_too(tmp_path):
    save_settings({"speaker_recognition_enabled":True}, tmp_path, human_confirmed=True)
    with pytest.raises(PermissionError):
        save_settings({"speaker_recognition_enabled":False}, tmp_path)
    assert load_raw_config(tmp_path)["speaker_recognition_enabled"]
    save_settings({"speaker_recognition_enabled":False}, tmp_path, human_confirmed=True)
    assert not load_raw_config(tmp_path)["speaker_recognition_enabled"]


def test_native_enable_cancel_does_not_silently_switch_filter(window, monkeypatch):
    window.fields["speaker_recognition_enabled"].setChecked(True)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Cancel)
    assert not window.save()
    assert not load_raw_config(window.home)["speaker_recognition_enabled"]
    assert window.fields["speaker_recognition_enabled"].isChecked()


def test_native_reply_mode_and_selected_language_persist_independently(window):
    selected = window.fields["whisper_language"]
    selected.setCurrentIndex(selected.findData("en"))
    mode = window.fields["reply_language_mode"]
    mode.setCurrentIndex(mode.findData("match"))
    assert window.save()
    saved = load_raw_config(window.home)
    assert saved["whisper_language"] == "en"
    assert saved["reply_language_mode"] == "match"
    typed = load_config(window.home)
    assert typed.whisper_language == "en"
    assert typed.reply_language_mode == "match"
    window.restore()
    assert mode.currentData() == "match"
    assert selected.currentData() == "en"
    mode.setCurrentIndex(mode.findData("selected"))
    assert window.save()
    assert load_raw_config(window.home)["reply_language_mode"] == "selected"


@pytest.mark.parametrize("key,value", [("speaker_threshold",.39), ("speaker_threshold",.96),
                                       ("speaker_threshold",float("nan")),
                                       ("reply_language_mode","anything"),
                                       ("speaker_recognition_enabled","yes")])
def test_schema_rejects_invalid_speaker_and_reply_settings(tmp_path, key, value):
    before = load_raw_config(tmp_path)
    with pytest.raises(ValueError):
        save_settings({key:value}, tmp_path, human_confirmed=True)
    assert load_raw_config(tmp_path) == before


def test_example_config_matches_safe_opt_in_defaults():
    from pathlib import Path
    example = json.loads((Path(__file__).parents[1] / "config/ai-os/config.example.json").read_text())
    assert example["speaker_recognition_enabled"] is False
    assert example["speaker_model"] == ""
    assert example["reply_language_mode"] == "selected"


@pytest.mark.parametrize("setting,value", [("speaker_recognition_enabled",True),
                                            ("speaker_model","/tmp/local-speaker.onnx"),
                                            ("speaker_threshold",.85)])
def test_speaker_controls_always_require_confirmation_even_when_global_lock_off(tmp_path, setting, value):
    save_settings({"sandbox_lock_settings":False}, tmp_path, human_confirmed=True)
    before = load_raw_config(tmp_path)
    with pytest.raises(PermissionError):
        save_settings({setting:value}, tmp_path)
    assert load_raw_config(tmp_path) == before
    save_settings({setting:value}, tmp_path, human_confirmed=True)
    assert load_raw_config(tmp_path)[setting] == value


def test_disabling_filter_stays_protected_when_global_lock_off(tmp_path):
    save_settings({"sandbox_lock_settings":False, "speaker_recognition_enabled":True},
                  tmp_path, human_confirmed=True)
    with pytest.raises(PermissionError):
        save_settings({"speaker_recognition_enabled":False}, tmp_path)
    assert load_raw_config(tmp_path)["speaker_recognition_enabled"]


def test_native_filter_change_still_asks_when_global_lock_off(window, monkeypatch):
    window.saved = save_settings({"sandbox_lock_settings":False}, window.home, human_confirmed=True)
    window.restore()
    window.fields["speaker_recognition_enabled"].setChecked(True)
    confirmations = []
    def refuse(*args):
        confirmations.append(args)
        return QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(QMessageBox, "question", refuse)
    assert not window.save()
    assert len(confirmations) == 1
    assert not load_raw_config(window.home)["speaker_recognition_enabled"]


def test_preview_uses_saved_filter_state_and_ignores_non_object_status(window):
    from ai_os.config import atomic_json
    window.fields["speaker_recognition_enabled"].setChecked(True)
    window.refresh_preview()
    assert window.speaker_status.text() == "Speaker filter is off."
    save_settings({"speaker_recognition_enabled": True}, window.home, human_confirmed=True)
    atomic_json(window.home / "run/speaker-status.json", [])
    window.refresh_preview()
    assert "filter is on" in window.speaker_status.text()


def test_unsaved_count_save_feedback_and_revert_reflect_real_preferences(window):
    assert not window.save_button.isEnabled()
    scale = window.fields["avatar_scale"]
    old = scale.value()
    scale.setValue(old - 1)
    assert window.save_button.isEnabled() and window.save_button.text() == "Save 1 changes"
    assert load_raw_config(window.home)["avatar_scale"] == old
    assert window.save()
    assert not window.save_button.isEnabled()
    assert load_raw_config(window.home)["avatar_scale"] == old - 1
    scale.setValue(old - 2)
    window.restore()
    assert scale.value() == old - 1 and not window.save_button.isEnabled()


def test_accent_picker_enables_save_and_revert_restores_saved_color(window, monkeypatch):
    from ai_os.native_settings import QInputDialog
    previous = window.accent_value
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a: ("Ice", True))
    window.choose_accent()
    assert window.accent_value == "#69d8ff" and window.save_button.isEnabled()
    window.restore()
    assert window.accent_value == previous and not window.save_button.isEnabled()
