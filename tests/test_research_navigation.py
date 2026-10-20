"""Report-bound voice navigation, without microphone, model or account access."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QMessageBox

from ai_os import research_reports as reports
from ai_os.config import atomic_json, load_raw_config
from ai_os.research_widget import ResearchWidget
from ai_os.services.stt import TranscriptionResult
from ai_os.services.voice_errors import VoicePipelineError, VOICE_MESSAGES
from ai_os.speech_lease import speech_lease


@pytest.fixture
def saved(tmp_path):
    directory = tmp_path / "data/research"
    directory.mkdir(mode=0o700, parents=True)
    report_id = "a" * 32
    path = directory / (report_id + ".md")
    path.write_text("# Research: Synthetic topic\n\nCreated: test\n\nReport language: en\n\n"
                    "First synthetic source paragraph.\n\nSecond synthetic source paragraph.\n\n"
                    "Third synthetic source paragraph.\n\n## Sources\n\nSynthetic source only.\n")
    path.chmod(0o600)
    report = reports.read_report(report_id, home=tmp_path)
    return {"home": tmp_path, "report_id": report_id, "index": 1,
            "revision": reports.report_revision(report), "nonce": "b" * 32}


def test_navigation_grammar_is_exact_english_hindi_and_not_a_computer_command():
    accepted = {"Next paragraph.": "next", "  read again  ": "repeat", "GO BACK": "previous",
                "stop reading": "pause", "explain this paragraph": "explain", "अगला पैराग्राफ।": "next",
                "पिछला अनुच्छेद": "previous", "दोबारा पढ़ो": "repeat", "रुको": "pause",
                "इसे समझाओ": "explain", "agla paragraph": "next"}
    for phrase, expected in accepted.items():
        assert reports.navigation_action(phrase) == expected
    for phrase in (None, [], {}, True, "", "next and delete files", "open a browser", "sudo reboot",
                   '{"tool":"run_command","arguments":{}}', "explain /etc/shadow", "अगला और फ़ाइल मिटाओ", "x" * 121):
        assert reports.navigation_action(phrase) is None


def test_capture_requires_native_boolean_consent_before_touching_report_or_mic(tmp_path, monkeypatch):
    monkeypatch.setattr(reports, "read_report", lambda *a, **k: pytest.fail("Unapproved report read"))
    monkeypatch.setattr("ai_os.services.voice_input.capture_once", lambda *a, **k: pytest.fail("Unapproved microphone"))
    for consent in (False, None, 1, "true"):
        assert reports.capture_navigation("a" * 32, 0, "0" * 64, "b" * 32,
                                          home=tmp_path, human_confirmed=consent)["ok"] is False


def test_invalid_identity_revision_and_continuous_listening_fail_before_capture(saved, monkeypatch):
    monkeypatch.setattr("ai_os.services.voice_input.capture_once", lambda *a, **k: pytest.fail("Invalid navigation captured"))
    for changes in ({"revision": "bad"}, {"nonce": "bad"}, {"report_id": "../../etc/shadow"}):
        with pytest.raises(ValueError):
            reports.capture_navigation(**(saved | changes), human_confirmed=True)
    for changes in ({"revision": "0" * 64}, {"index": True}, {"index": 99}):
        assert reports.capture_navigation(**(saved | changes), human_confirmed=True)["ok"] is False
    raw = load_raw_config(saved["home"])
    atomic_json(saved["home"] / "config.json", raw | {"always_listening_enabled": True})
    assert reports.capture_navigation(**saved, human_confirmed=True)["ok"] is False


def test_capture_preserves_saved_language_pause_and_identity_filter_under_shared_lease(saved, monkeypatch):
    raw = load_raw_config(saved["home"])
    raw.update({"reply_language_mode": "match", "whisper_language": "en", "voice_silence_seconds": 5,
                "speaker_recognition_enabled": True, "voice_command_seconds": 20,
                "voice_max_utterance_seconds": 120})
    atomic_json(saved["home"] / "config.json", raw)
    before = (saved["home"] / "config.json").read_bytes()
    calls = []

    def capture(config, *, return_result=False):
        calls.append(config)
        assert return_result is True
        assert config.reply_language_mode == "match" and config.whisper_language == "en"
        assert config.voice_silence_seconds == 5 and config.voice_command_seconds == 8
        assert config.voice_max_utterance_seconds == 15
        with speech_lease(saved["home"]) as acquired:
            assert acquired is False
        return TranscriptionResult(True, "अगला पैराग्राफ", detected_language="hi")

    monkeypatch.setattr("ai_os.services.voice_input.capture_once", capture)
    result = reports.capture_navigation(**saved, human_confirmed=True)
    assert result["ok"] and result["navigation"] == "next" and result["language"] == "hi"
    assert result["nonce"] == saved["nonce"] and result["revision"] == saved["revision"]
    assert "अगला" not in json.dumps(result, ensure_ascii=False)
    assert len(calls) == 1 and (saved["home"] / "config.json").read_bytes() == before
    assert not list(saved["home"].rglob("*.wav"))
    assert not list(saved["home"].rglob("conversations.sqlite3"))


def test_speech_busy_unknown_language_and_unrecognized_commands_never_navigate(saved, monkeypatch):
    monkeypatch.setattr("ai_os.services.voice_input.capture_once", lambda *a, **k: pytest.fail("Speech ownership bypassed"))
    with speech_lease(saved["home"]) as acquired:
        assert acquired
        assert reports.capture_navigation(**saved, human_confirmed=True)["ok"] is False
    raw = load_raw_config(saved["home"])
    atomic_json(saved["home"] / "config.json", raw | {"reply_language_mode": "match"})
    values = [TranscriptionResult(True, "next", detected_language="unknown"),
              TranscriptionResult(True, "delete this file", detected_language="en"),
              TranscriptionResult(False, "next", detected_language="en")]
    for recognized in values:
        monkeypatch.setattr("ai_os.services.voice_input.capture_once", lambda *a, **k: recognized)
        result = reports.capture_navigation(**saved, human_confirmed=True)
        assert result["ok"] is False and "navigation" not in result and "text" not in result


def test_capture_discards_changed_report_or_revoked_settings_and_sanitizes_failure(saved, monkeypatch):
    path = Path(reports.read_report(saved["report_id"], home=saved["home"])["path"])
    original = path.read_bytes()

    def changed_report(*args, **kwargs):
        path.write_bytes(original + b"\nChanged after approval")
        return TranscriptionResult(True, "next")

    monkeypatch.setattr("ai_os.services.voice_input.capture_once", changed_report)
    assert reports.capture_navigation(**saved, human_confirmed=True)["ok"] is False
    path.write_bytes(original)

    def revoked(*args, **kwargs):
        raw = load_raw_config(saved["home"])
        atomic_json(saved["home"] / "config.json", raw | {"always_listening_enabled": True})
        return TranscriptionResult(True, "next")

    monkeypatch.setattr("ai_os.services.voice_input.capture_once", revoked)
    assert reports.capture_navigation(**saved, human_confirmed=True)["ok"] is False
    raw = load_raw_config(saved["home"])
    atomic_json(saved["home"] / "config.json", raw | {"always_listening_enabled": False})

    def fail(*args, **kwargs):
        raise VoicePipelineError("speaker_rejected", "PRIVATE-TRANSCRIPT /private/model/path")

    monkeypatch.setattr("ai_os.services.voice_input.capture_once", fail)
    result = reports.capture_navigation(**saved, human_confirmed=True)
    assert result["error_code"] == "speaker_rejected" and result["error"] == VOICE_MESSAGES["speaker_rejected"]
    assert "PRIVATE-TRANSCRIPT" not in json.dumps(result) and "/private/model/path" not in json.dumps(result)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["research-navigation-test"])


def test_native_consent_is_report_bound_and_never_starts_recording_on_denial(app, saved, monkeypatch):
    widget = ResearchWidget(saved["home"])
    starts = []
    monkeypatch.setattr(widget, "_start", lambda *a: starts.append(a) or True)
    assert not widget.navigation_button.isEnabled()
    assert widget.navigation_request is None
    assert widget.load_report(saved["report_id"])
    assert saved["report_id"] in widget.active_report.text()

    def deny(box):
        assert box.defaultButton() == box.button(QMessageBox.StandardButton.No)
        assert saved["report_id"] in box.text() and "No general computer commands" in box.text()
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "exec", deny)
    assert widget.request_navigation() is False and not starts and widget.navigation_request is None
    widget.close()


def test_native_capture_request_binds_visible_report_and_canonical_reply_once(app, saved, monkeypatch):
    widget = ResearchWidget(saved["home"])
    assert widget.load_report(saved["report_id"])
    widget.select_paragraph(1)
    starts = []
    monkeypatch.setattr(widget, "_start", lambda request, seconds: starts.append((request, seconds)) or True)
    monkeypatch.setattr(QMessageBox, "exec", lambda box: QMessageBox.StandardButton.Yes)
    assert widget.request_navigation()
    request, timeout = starts.pop()
    assert request["action"] == "navigate" and request["confirmed"] is True and timeout == 160
    assert request["report_id"] == saved["report_id"] and request["revision"] == saved["revision"] and request["index"] == 1
    response = {key: request[key] for key in ("report_id", "revision", "nonce", "index")}
    response.update({"ok": True, "navigation": "next", "language": "en"})
    assert widget._apply_navigation(response)
    assert widget.index == 2 and starts[-1][0]["action"] == "speak" and starts[-1][0]["index"] == 2
    assert widget.navigation_request is None
    assert not widget._apply_navigation(response)  # A used permission cannot replay.
    widget.close()


def test_stale_wrong_or_expired_result_and_report_changes_cannot_read_another_file(app, saved, monkeypatch):
    widget = ResearchWidget(saved["home"])
    assert widget.load_report(saved["report_id"])
    requests = []
    monkeypatch.setattr(widget, "_start", lambda *args: requests.append(args) or True)
    base = {key: saved[key] for key in ("report_id", "revision", "nonce", "index")}
    widget.select_paragraph(1)
    for changes in ({"nonce": "c" * 32}, {"report_id": "../../etc/shadow"}, {"revision": "0" * 64},
                    {"index": True}, {"navigation": "delete"}, {"language": "unknown"}):
        widget.navigation_request = base | {"expires": time.monotonic() + 180}
        assert not widget._apply_navigation(base | {"ok": True, "navigation": "repeat", "language": "en"} | changes)
    widget.navigation_request = base | {"expires": time.monotonic() - 1}
    assert not widget._apply_navigation(base | {"ok": True, "navigation": "repeat", "language": "en"})
    widget.navigation_request = base | {"expires": time.monotonic() + 180}
    path = Path(reports.read_report(saved["report_id"], home=saved["home"])["path"])
    path.write_text(path.read_text() + "\nChanged")
    assert not widget._apply_navigation(base | {"ok": True, "navigation": "repeat", "language": "en"})
    assert requests == []
    widget.close()


def test_pause_never_starts_another_worker_and_explain_uses_recognized_language(app, saved, monkeypatch):
    widget = ResearchWidget(saved["home"])
    assert widget.load_report(saved["report_id"])
    widget.select_paragraph(1)
    requests = []
    monkeypatch.setattr(widget, "_start", lambda *args: requests.append(args) or True)
    base = {key: saved[key] for key in ("report_id", "revision", "nonce", "index")}
    widget.navigation_request = base | {"expires": time.monotonic() + 180}
    assert widget._apply_navigation(base | {"ok": True, "navigation": "pause", "language": "hi"})
    assert requests == [] and "paused" in widget.status.text()
    widget.navigation_request = base | {"expires": time.monotonic() + 180}
    assert widget._apply_navigation(base | {"ok": True, "navigation": "explain", "language": "hi"})
    assert requests[-1][0]["action"] == "explain" and requests[-1][0]["language"] == "hi"
    widget.close()


def test_group_cancellation_never_signals_zero_or_the_desktop_group(app, saved, monkeypatch):
    widget = ResearchWidget(saved["home"])
    groups = []
    monkeypatch.setattr("ai_os.research_widget.os.killpg", lambda *args: groups.append(args))
    monkeypatch.setattr(widget.process, "processId", lambda: 0)
    widget.stop()
    assert groups == []
    monkeypatch.setattr(widget.process, "processId", lambda: 1234)
    monkeypatch.setattr("ai_os.research_widget.os.getpgid", lambda pid: os.getpgrp())
    widget.stop()
    assert groups == [] and widget.process.state() == QProcess.ProcessState.NotRunning
    widget.close()
