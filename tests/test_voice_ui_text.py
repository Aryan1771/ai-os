"""Private early transcript/reply display; no audio, providers or personal data."""
from __future__ import annotations

import json
import os
import sys

import pytest

from ai_os import voice_check_status, voice_diagnostics, voice_progress, voice_ui_text
from ai_os.services.stt import TranscriptionResult
from ai_os.services.voice_errors import VoicePipelineError
from ai_os.settings_store import save_settings


@pytest.fixture(autouse=True)
def forbid_live_work(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("No recording, playback, model request or private history is permitted")
    monkeypatch.setattr("ai_os.services.voice_input.capture_once", forbidden)
    monkeypatch.setattr("ai_os.speech_queue.SpeechQueue.speak_text", forbidden)
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)


@pytest.mark.parametrize("bad", [
    None, [], {"event": "voice_progress", "kind": "transcript", "text": "PRIVATE"},
    {"event": "voice_ui_text", "kind": [], "text": "PRIVATE"},
    {"event": "voice_ui_text", "kind": "command", "text": "PRIVATE"},
    {"event": "voice_ui_text", "kind": "transcript", "text": {"tool": "PRIVATE"}},
    {"event": "voice_ui_text", "kind": "transcript", "text": "PRIVATE", "path": "PRIVATE"},
    {"event": "voice_ui_text", "kind": "transcript", "text": " "},
    {"event": "voice_ui_text", "kind": "transcript", "text": "x" * 8001},
    {"event": "voice_ui_text", "kind": "reply", "text": "x" * 2001},
    {"event": "voice_ui_text", "kind": "transcript", "text": "ह" * 6000},
    {"event": "voice_ui_text", "kind": "transcript", "text": "\0" * 8000},
    {"event": "voice_ui_text", "kind": "reply", "text": "\0" * 2000},
    {"event": "voice_ui_text", "kind": "transcript", "text": "\ud800"},
])
def test_private_event_rejects_unknown_fields_kinds_types_and_actual_wire_expansion(bad):
    assert voice_ui_text.private_ui_text(bad) is None
    assert voice_ui_text.encoded_text_event(bad) is None


@pytest.mark.parametrize("kind,text", [("transcript", "ह" * 5461), ("reply", "😀" * 2000),
                                       ("transcript", "A\n" * 2500)])
def test_valid_private_event_has_bounded_utf8_json_wire_and_cannot_be_public_progress(kind, text):
    event = voice_ui_text.text_event(kind, text)
    wire = voice_ui_text.encoded_text_event(event)
    assert len(wire) <= voice_ui_text.LIMITS[kind][1] + 128
    assert json.loads(wire) == event and wire.count(b"\n") == 1
    assert voice_progress.public_progress(event) is None


@pytest.mark.parametrize("fail_speech", [False, True])
def test_pipeline_emits_transcript_after_stt_and_reply_before_speech_with_separate_callbacks(
    tmp_path, monkeypatch, fail_speech,
):
    save_settings({"speech_enabled": True}, tmp_path)
    order, private, public = [], [], []

    def capture(*_args, **_kwargs):
        order.append("stt")
        return TranscriptionResult(True, "PRIVATE recognized words", detected_language="en")

    def ui(event):
        private.append(event)
        order.append(event["kind"])

    def reply(text, *_args, **_kwargs):
        assert text == "PRIVATE recognized words" and private[0]["kind"] == "transcript"
        order.append("model")
        return "PRIVATE model reply"

    class Speech:
        def __init__(self, *_args, **_kwargs):
            pass

        def speak_text(self, *_args, **_kwargs):
            assert [event["kind"] for event in private] == ["transcript", "reply"]
            order.append("speech")
            if fail_speech:
                raise RuntimeError("PRIVATE backend path")

    monkeypatch.setattr("ai_os.services.voice_input.capture_once", capture)
    monkeypatch.setattr("ai_os.speech_queue.SpeechQueue", Speech)
    monkeypatch.setattr(voice_diagnostics, "local_reply", reply)
    if fail_speech:
        with pytest.raises(VoicePipelineError, match="speech failed"):
            voice_diagnostics.check_voice("record", "en", home=tmp_path, human_confirmed=True,
                                          on_ui_text=ui, on_progress=public.append)
    else:
        assert voice_diagnostics.check_voice("record", "en", home=tmp_path, human_confirmed=True,
                                             on_ui_text=ui, on_progress=public.append)["ok"]
    assert order == ["stt", "transcript", "model", "reply", "speech"]
    assert "PRIVATE" not in json.dumps(public)


def test_private_callback_failure_stops_before_model_and_exposes_no_callback_text(tmp_path, monkeypatch):
    save_settings({"speech_enabled": True}, tmp_path)
    monkeypatch.setattr("ai_os.services.voice_input.capture_once", lambda *_a, **_k: (
        TranscriptionResult(True, "PRIVATE words", detected_language="en")))
    monkeypatch.setattr(voice_diagnostics, "local_reply", lambda *_a, **_k: pytest.fail("No model"))

    def ui(_event):
        raise RuntimeError("PRIVATE callback error")

    with pytest.raises(VoicePipelineError) as raised:
        voice_diagnostics.check_voice("record", "en", home=tmp_path, human_confirmed=True, on_ui_text=ui)
    assert "PRIVATE" not in str(raised.value)


def test_unknown_recognition_language_never_emits_unverified_private_words(tmp_path, monkeypatch):
    save_settings({"speech_enabled": True, "reply_language_mode": "match"}, tmp_path)
    events = []
    monkeypatch.setattr("ai_os.services.voice_input.capture_once", lambda *_a, **_k: (
        TranscriptionResult(True, "PRIVATE unverified words", detected_language=None)))
    monkeypatch.setattr(voice_diagnostics, "local_reply", lambda *_a, **_k: pytest.fail("No model"))
    with pytest.raises(VoicePipelineError, match="identify English or Hindi"):
        voice_diagnostics.check_voice("record", "auto", home=tmp_path, human_confirmed=True,
                                      on_ui_text=events.append)
    assert events == []


@pytest.mark.parametrize("enabled", [False, True])
def test_only_opted_in_worker_emits_private_lines_and_gui_summary_avoids_duplicate_text(
    tmp_path, monkeypatch, capsys, enabled,
):
    monkeypatch.setenv("AI_OS_HOME", str(tmp_path))
    monkeypatch.setattr(voice_diagnostics.signal, "signal", lambda *_args: None)

    def check(*_args, on_ui_text=None, on_progress=None, **_kwargs):
        assert bool(on_ui_text) == enabled
        if on_ui_text:
            on_ui_text(voice_ui_text.text_event("transcript", "PRIVATE हिन्दी words"))
            on_ui_text(voice_ui_text.text_event("reply", "PRIVATE reply"))
            on_ui_text(voice_ui_text.text_event("reply", "PRIVATE duplicate"))
        if on_progress:
            on_progress({"event": "voice_progress", "phase": "speaking"})
        return {"ok": True, "message": "Done", "transcript": "PRIVATE हिन्दी words", "reply": "PRIVATE reply"}

    monkeypatch.setattr(voice_diagnostics, "check_voice", check)
    args = ["voice_diagnostics", "--worker", "record", "--confirmed"]
    monkeypatch.setattr(sys, "argv", args + (["--ui-text"] if enabled else []))
    assert voice_diagnostics.main() == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(lines) == (3 if enabled else 1)
    if enabled:
        assert [event["kind"] for event in lines[:-1]] == ["transcript", "reply"]
        assert set(lines[-1]) == {"ok", "message"}
    else:
        assert lines[-1]["transcript"] == "PRIVATE हिन्दी words"
    assert "PRIVATE" not in json.dumps(voice_check_status.read_status(tmp_path))


def test_unconfirmed_ui_text_flag_does_not_enable_private_callback_or_metadata(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AI_OS_HOME", str(tmp_path))
    monkeypatch.setattr(voice_diagnostics.signal, "signal", lambda *_args: None)

    def check(*_args, on_ui_text=None, **_kwargs):
        assert on_ui_text is None
        raise PermissionError("PRIVATE")

    monkeypatch.setattr(voice_diagnostics, "check_voice", check)
    monkeypatch.setattr(sys, "argv", ["voice_diagnostics", "--worker", "record", "--ui-text"])
    assert voice_diagnostics.main() == 1
    output = capsys.readouterr().out
    assert "PRIVATE" not in output and len(output.splitlines()) == 1
    assert not (tmp_path / "run").exists()


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(["voice-ui-text-test"])


@pytest.fixture
def fake_dialog(app, tmp_path, monkeypatch):
    from PySide6 import QtCore
    from PySide6.QtCore import QCoreApplication, QEvent, QProcess, QTimer
    from shiboken6 import isValid

    processes = []

    class FakeProcess(QProcess):
        def __init__(self, parent):
            super().__init__(parent)
            self.pending = b""
            self.launches = []
            processes.append(self)

        def start(self, program, arguments):
            self.launches.append((program, arguments))

        def readAllStandardOutput(self):
            data, self.pending = self.pending, b""
            return data

    monkeypatch.setattr(QtCore, "QProcess", FakeProcess)
    dialog = voice_diagnostics.create_dialog(tmp_path)
    dialog.consent.setChecked(True)
    dialog.record.click()
    yield dialog, processes
    dialog.reject()
    assert not any(timer.isActive() for timer in dialog.findChildren(QTimer))
    assert not dialog.reached_text and not dialog.details.toPlainText()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(dialog, QEvent.Type.DeferredDelete)
    assert not isValid(dialog) and all(not isValid(process) for process in processes)


def deliver(dialog, process, kind, text):
    process.pending = voice_ui_text.encoded_text_event(voice_ui_text.text_event(kind, text))
    dialog.read_output(process)


def test_private_text_appears_on_split_and_coalesced_events_before_worker_finishes(fake_dialog):
    dialog, processes = fake_dialog
    process = processes[0]
    assert "--ui-text" in process.launches[0][1] and dialog.stop.text() == "Cancel check"
    wire = voice_ui_text.encoded_text_event(voice_ui_text.text_event("transcript", "PRIVATE हिन्दी <b>literal</b>"))
    split = wire.index("ह".encode()) + 1
    process.pending = wire[:split]
    dialog.read_output(process)
    assert not dialog.details.toPlainText()
    process.pending = wire[split:]
    dialog.read_output(process)
    assert dialog.details.toPlainText() == "You: PRIVATE हिन्दी <b>literal</b>"
    assert dialog.process is process and dialog.timer.isActive()
    process.pending = (voice_ui_text.encoded_text_event(voice_ui_text.text_event("reply", "PRIVATE reply"))
                       + b'{"event":"voice_progress","phase":"speaking"}\n'
                       + b'{"ok":true,"message":"Done"}\n')
    dialog.finished(0, process.ExitStatus.NormalExit, process)
    assert dialog.details.toPlainText() == "You: PRIVATE हिन्दी <b>literal</b>\n\nRE: PRIVATE reply"
    assert dialog.process is None and dialog.temporary is None


@pytest.mark.parametrize("end", ["speech_error", "cancel", "invalid_final"])
def test_reached_text_survives_speech_failure_or_cancel_until_next_check(fake_dialog, end):
    dialog, processes = fake_dialog
    process = processes[0]
    deliver(dialog, process, "transcript", "PRIVATE words")
    deliver(dialog, process, "reply", "PRIVATE reply")
    if end == "cancel":
        dialog.cancel("Cancelled synthetic check")
    else:
        process.pending = (b'{"ok":false,"message":"Speech failed","timings":{"stt_seconds":1.25}}\n'
                           if end == "speech_error" else b"invalid\n")
        dialog.finished(1, process.ExitStatus.NormalExit, process)
    assert "PRIVATE words" in dialog.details.toPlainText() and "PRIVATE reply" in dialog.details.toPlainText()
    assert dialog.process is None and dialog.temporary is None
    dialog.start("play")
    assert not dialog.details.toPlainText() and not dialog.reached_text


@pytest.mark.parametrize("bad", [
    b'{"event":"voice_ui_text","kind":"transcript","text":"PRIVATE","path":"PRIVATE"}\n',
    b'{"event":"voice_ui_text","kind":[],"text":"PRIVATE"}\n',
    b'{"event":"voice_ui_text","kind":"transcript","text":"\xff"}\n',
    b'{"event":"voice_ui_text","kind":"reply","text":42}\n',
])
def test_malformed_private_events_stop_without_displaying_rejected_payload(fake_dialog, bad):
    dialog, processes = fake_dialog
    process = processes[0]
    deliver(dialog, process, "transcript", "Accepted current words")
    process.pending = bad
    dialog.read_output(process)
    assert dialog.process is None
    assert dialog.details.toPlainText() == "You: Accepted current words"
    assert "PRIVATE" not in dialog.status.text() + dialog.details.toPlainText()


def test_duplicate_private_kind_is_rejected_without_replacing_reached_text(fake_dialog):
    dialog, processes = fake_dialog
    process = processes[0]
    deliver(dialog, process, "transcript", "First accepted words")
    deliver(dialog, process, "transcript", "PRIVATE replacement")
    assert dialog.process is None and dialog.details.toPlainText() == "You: First accepted words"


def test_cancelled_worker_callbacks_cannot_finish_or_write_into_the_next_check(fake_dialog):
    dialog, processes = fake_dialog
    old = processes[0]
    deliver(dialog, old, "transcript", "PRIVATE old words")
    dialog.cancel("Cancelled old check")
    dialog.start("play")
    current = processes[1]
    old.pending = voice_ui_text.encoded_text_event(voice_ui_text.text_event("reply", "PRIVATE old reply"))
    old.readyReadStandardOutput.emit()
    old.finished.emit(0, old.ExitStatus.NormalExit)
    old.errorOccurred.emit(old.ProcessError.FailedToStart)
    assert dialog.process is current and not dialog.details.toPlainText()
    assert dialog.timer.isActive()
    deliver(dialog, current, "reply", "Current accepted reply")
    assert dialog.details.toPlainText() == "RE: Current accepted reply"


def test_close_clears_private_fields_and_late_events_cannot_restore_them(fake_dialog):
    dialog, processes = fake_dialog
    process = processes[0]
    deliver(dialog, process, "transcript", "PRIVATE words")
    dialog.reject()
    assert not dialog.reached_text and not dialog.details.toPlainText()
    process.pending = voice_ui_text.encoded_text_event(voice_ui_text.text_event("reply", "PRIVATE late"))
    dialog.read_output(process)
    assert not dialog.reached_text and not dialog.details.toPlainText()


def test_maximum_utf8_private_payload_plus_progress_and_summary_fits_existing_stream_cap(fake_dialog):
    dialog, processes = fake_dialog
    process = processes[0]
    transcript = voice_ui_text.encoded_text_event(voice_ui_text.text_event("transcript", "ह" * 5461))
    reply = voice_ui_text.encoded_text_event(voice_ui_text.text_event("reply", "😀" * 2000))
    progress = (b'{"event":"voice_progress","phase":"capturing","captured_seconds":20,'
                b'"silence_seconds":5,"required_silence_seconds":5}\n') * 90
    summary = b'{"ok":true,"message":"Completed","timings":{"stt_seconds":1.0}}\n'
    payload = progress + transcript + reply + summary
    assert len(payload) < 65536
    process.pending = payload
    dialog.finished(0, process.ExitStatus.NormalExit, process)
    assert dialog.status.text() == "Completed" and dialog.process is None
    assert "ह" * 5461 in dialog.details.toPlainText() and "😀" * 2000 in dialog.details.toPlainText()
