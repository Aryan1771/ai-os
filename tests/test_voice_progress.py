"""Guided progress and recorder ordering without microphone/model access."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import deque
from types import SimpleNamespace

import pytest

from ai_os import voice_diagnostics, voice_progress
from ai_os.config import load_config
from ai_os.services import listener, voice_input
from ai_os.services.stt import TranscriptionResult
from ai_os.services.voice_errors import VoicePipelineError
from ai_os.settings_store import save_settings


@pytest.fixture(autouse=True)
def forbid_live_io(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("No real microphone, playback or model request is permitted")
    monkeypatch.setattr(voice_input.subprocess, "Popen", forbidden)
    monkeypatch.setattr(voice_input.subprocess, "run", forbidden)
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)


@pytest.mark.parametrize("bad", [
    None, [], {"event": "private", "phase": "thinking"},
    {"event": "voice_progress", "phase": []},
    {"event": "voice_progress", "phase": {}},
    {"event": "voice_progress", "phase": "private text"},
    {"event": "voice_progress", "phase": "thinking", "transcript": "PRIVATE"},
    {"event": "voice_progress", "phase": "thinking", "silence_seconds": True},
    {"event": "voice_progress", "phase": "thinking", "silence_seconds": float("nan")},
    {"event": "voice_progress", "phase": "thinking", "silence_seconds": 10**500},
    {"event": "voice_progress", "phase": "thinking", "silence_seconds": -1},
])
def test_progress_rejects_text_unknown_fields_and_invalid_numbers(bad):
    assert voice_progress.public_progress(bad) is None


def test_progress_throttles_repeated_phases_but_reports_transitions_and_has_count_cap(monkeypatch):
    clock = [100.0]
    events = []
    monkeypatch.setattr(voice_progress.time, "monotonic", lambda: clock[0])
    reporter = voice_progress.ProgressReporter(events.append)
    reporter.emit("capturing", silence_seconds=.125, required_silence_seconds=5)
    for _ in range(100):
        reporter.emit("capturing", silence_seconds=.2, required_silence_seconds=5)
    assert len(events) == 1
    clock[0] += .25
    reporter.emit("capturing", silence_seconds=.375, required_silence_seconds=5)
    reporter.emit("microphone_off")
    assert [event["phase"] for event in events] == ["capturing", "capturing", "microphone_off"]
    assert events[0]["silence_seconds"] == .12
    monkeypatch.setattr(voice_progress, "MAX_EVENTS", 4)
    reporter.emit("transcribing")
    reporter.emit("thinking")
    assert len(events) == 4
    assert "Microphone off" in voice_progress.progress_message(events[-1])


def test_disabled_progress_performs_no_extra_clock_or_output(monkeypatch):
    monkeypatch.setattr(voice_progress.time, "monotonic", lambda: pytest.fail("No diagnostic collector"))
    voice_progress.ProgressReporter().emit("capturing", silence_seconds=1)


def setup_capture(tmp_path, monkeypatch, *, reap_failure=False):
    events, stages = [], []
    frames = deque([(2000).to_bytes(2, "little", signed=True) * 1280] * 7
                   + [b"\0" * 2560] * 64)
    clock = [0.0]

    class Recorder:
        stdout = object()
        ended = False
        waits = 0

        def poll(self):
            if reap_failure == "bad_poll":
                return "unconfirmed"
            return -15 if self.ended else None

        def terminate(self):
            stages.append("terminate")

        def kill(self):
            stages.append("kill")

        def wait(self, timeout):
            self.waits += 1
            if reap_failure is True or reap_failure == "recover" and self.waits == 1:
                raise subprocess.TimeoutExpired("synthetic-recorder", timeout)
            self.ended = True
            stages.append("reaped")
            return None if reap_failure == "bad_wait" else -15

    recorder = Recorder()
    recorder.phases = []

    class Transcriber:
        def __init__(self, *_args, **_kwargs):
            pass

        def availability(self):
            return True, "synthetic ready"

        def transcribe_file(self, path):
            assert recorder.ended and path.is_file()
            stages.append("transcribe")
            return SimpleNamespace(ok=True, text="A synthetic completed utterance.", detected_language="en")

    def read(_service, size):
        clock[0] += size / 32000
        return frames.popleft()[:size]

    def filter_audio(path, _home):
        assert recorder.ended and path.is_file()
        stages.append("filter")
        return True, "synthetic filter off"

    monkeypatch.setattr(voice_input, "WhisperCppTranscriber", Transcriber)
    monkeypatch.setattr(voice_input.subprocess, "Popen", lambda *_a, **_k: recorder)
    monkeypatch.setattr(listener.AlwaysListeningService, "_read_audio", read)
    monkeypatch.setattr(voice_input, "publish_state", lambda phase, **_k: recorder.phases.append(phase))
    monkeypatch.setattr(listener.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr("ai_os.speaker_filter.filter_utterance", filter_audio)
    monkeypatch.setenv("AI_OS_VOICE_TMP", str(tmp_path))
    return load_config(tmp_path / "runtime"), events, stages, recorder


def test_one_shot_reaps_recorder_before_filter_and_stt_and_reports_full_pause(tmp_path, monkeypatch):
    config, events, stages, recorder = setup_capture(tmp_path, monkeypatch)
    assert voice_input.capture_once(config, on_progress=events.append) == "A synthetic completed utterance."
    assert stages == ["terminate", "reaped", "filter", "transcribe"]
    assert recorder.ended
    assert recorder.phases == ["listening", "transcribing", "transcribing"]
    phases = [event["phase"] for event in events]
    assert phases[0:2] == ["checking_input", "waiting_for_speech"]
    assert phases.index("microphone_off") < phases.index("filtering") < phases.index("transcribing")
    capture_events = [event for event in events if event["phase"] == "capturing"]
    assert capture_events and all(event["required_silence_seconds"] == 5 for event in capture_events)
    assert max(event["silence_seconds"] for event in capture_events) >= 4.7
    assert not list(tmp_path.glob("regenos-mic-*"))


def test_unconfirmed_recorder_exit_fails_closed_without_mic_off_filter_or_stt(tmp_path, monkeypatch):
    config, events, stages, _recorder = setup_capture(tmp_path, monkeypatch, reap_failure=True)
    with pytest.raises(subprocess.TimeoutExpired):
        voice_input.capture_once(config, on_progress=events.append)
    assert "filter" not in stages and "transcribe" not in stages
    assert not any(event["phase"] == "microphone_off" for event in events)
    assert not list(tmp_path.glob("regenos-mic-*"))


def test_slow_recorder_is_killed_and_reaped_before_processing(tmp_path, monkeypatch):
    config, events, stages, _recorder = setup_capture(tmp_path, monkeypatch, reap_failure="recover")
    assert voice_input.capture_once(config, on_progress=events.append)
    assert stages == ["terminate", "kill", "reaped", "filter", "transcribe"]
    assert any(event["phase"] == "microphone_off" for event in events)


@pytest.mark.parametrize("failure", ["bad_wait", "bad_poll"])
def test_non_integer_recorder_exit_is_not_advertised_as_mic_off(tmp_path, monkeypatch, failure):
    config, events, stages, _recorder = setup_capture(tmp_path, monkeypatch, reap_failure=failure)
    with pytest.raises(VoicePipelineError, match="confirm the recorder stopped"):
        voice_input.capture_once(config, on_progress=events.append)
    assert "filter" not in stages and "transcribe" not in stages
    assert not any(event["phase"] == "microphone_off" for event in events)


@pytest.mark.parametrize("interruption", ["cancel_in_hook", "unfinished_audio"])
def test_capture_completion_races_never_submit_incomplete_or_cancelled_audio(tmp_path, monkeypatch, interruption):
    service = listener.AlwaysListeningService(
        run_dir=tmp_path,
        transcriber=SimpleNamespace(transcribe_file=lambda _path: pytest.fail("No transcript")),
        on_transcript=lambda _text: None)
    service._process = SimpleNamespace(stdout=object())
    frames = deque([b"\0" * 2560] * 63)
    service.on_capture_complete = lambda: service._stop.set()
    monkeypatch.setattr(service, "_read_audio", lambda _size: (
        b"" if interruption == "unfinished_audio" else frames.popleft()))
    if interruption == "unfinished_audio":
        with pytest.raises(VoicePipelineError, match="ending pause"):
            service._capture_and_transcribe(b"\1\0" * 1280, 2560)
    else:
        assert service._capture_and_transcribe(b"\1\0" * 1280, 2560) == ""
    assert not list(tmp_path.glob("*.wav"))


def test_continuous_endpoint_does_not_stop_its_recorder_while_transcribing(tmp_path, monkeypatch):
    frames = deque([b"\0" * 2560] * 63)
    recorder = SimpleNamespace(stdout=object(), poll=lambda: None)
    calls = []
    service = listener.AlwaysListeningService(
        run_dir=tmp_path,
        transcriber=SimpleNamespace(transcribe_file=lambda _path: (
            calls.append("transcribed-with-recorder-alive")
            or SimpleNamespace(ok=True, text="Synthetic completed utterance"))),
        on_transcript=lambda _text: None)
    service._process = recorder
    monkeypatch.setattr(service, "_read_audio", lambda _size: frames.popleft())
    monkeypatch.setattr(service, "stop_recorder", lambda: pytest.fail("Continuous input must remain active"))
    assert service._capture_and_transcribe(b"\1\0" * 1280, 2560) == "Synthetic completed utterance"
    assert calls == ["transcribed-with-recorder-alive"]


@pytest.mark.parametrize("enabled", [False, True])
def test_worker_cli_preserves_final_json_and_only_opted_in_phase_lines(monkeypatch, capsys, tmp_path, enabled):
    monkeypatch.setenv("AI_OS_HOME", str(tmp_path))
    def check(*_args, on_progress=None, **_kwargs):
        if on_progress:
            on_progress({"event": "voice_progress", "phase": "transcribing"})
            on_progress({"event": "voice_progress", "phase": "thinking", "private": "PRIVATE"})
        return {"ok": True, "message": "Done", "transcript": "Synthetic", "reply": "Synthetic reply"}

    monkeypatch.setattr(voice_diagnostics, "check_voice", check)
    monkeypatch.setattr(voice_diagnostics.signal, "signal", lambda *_args: None)
    argv = ["voice_diagnostics", "--worker", "record", "--confirmed"]
    monkeypatch.setattr(sys, "argv", argv + (["--progress"] if enabled else []))
    assert voice_diagnostics.main() == 0
    output = capsys.readouterr().out
    assert "PRIVATE" not in output
    lines = [json.loads(line) for line in output.splitlines()]
    assert len(lines) == (2 if enabled else 1)
    assert lines[-1]["ok"] is True


def test_guided_pipeline_forwards_safe_capture_phases_then_processing_without_history(tmp_path, monkeypatch):
    events = []
    save_settings({"speech_enabled": True}, tmp_path)

    def capture(config, *, on_progress=None, **_kwargs):
        assert config.voice_max_utterance_seconds == 20 and config.voice_silence_seconds == 5
        for phase in ("waiting_for_speech", "microphone_off", "transcribing"):
            on_progress({"event": "voice_progress", "phase": phase})
        return TranscriptionResult(True, "Synthetic current utterance", detected_language="en")

    class Speech:
        def __init__(self, *_args, **_kwargs):
            pass

        def speak_text(self, _text, **_kwargs):
            pass

    monkeypatch.setattr(voice_input, "capture_once", capture)
    monkeypatch.setattr(voice_diagnostics, "local_reply", lambda *_a, **_k: "Synthetic reply")
    monkeypatch.setattr("ai_os.speech_queue.SpeechQueue", Speech)
    result = voice_diagnostics.check_voice("record", "en", home=tmp_path,
                                          human_confirmed=True, on_progress=events.append)
    assert result["ok"]
    assert [event["phase"] for event in events] == ["preparing", "waiting_for_speech", "microphone_off",
                                                   "transcribing", "thinking", "speaking"]
    assert "Synthetic" not in json.dumps(events)


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(["voice-progress-test"])


@pytest.fixture
def fake_dialog(app, tmp_path, monkeypatch):
    from PySide6 import QtCore
    from PySide6.QtCore import QCoreApplication, QEvent, QProcess, QTimer
    from shiboken6 import isValid

    instances = []

    class FakeProcess(QProcess):
        def __init__(self, parent):
            super().__init__(parent)
            self.pending = b""
            self.launches = []
            instances.append(self)

        def start(self, program, arguments):
            self.launches.append((program, arguments))

        def readAllStandardOutput(self):
            data, self.pending = self.pending, b""
            return data

    monkeypatch.setattr(QtCore, "QProcess", FakeProcess)
    dialog = voice_diagnostics.create_dialog(tmp_path)
    dialog.consent.setChecked(True)
    dialog.record.click()
    yield dialog, instances[0]
    dialog.reject()
    assert not any(timer.isActive() for timer in dialog.findChildren(QTimer))
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(dialog, QEvent.Type.DeferredDelete)
    assert not isValid(dialog) and all(not isValid(child) for child in instances)


def test_native_progress_handles_partial_lines_and_keeps_final_result_compatible(fake_dialog):
    dialog, process = fake_dialog
    assert "Preparing" in dialog.status.text() and "--progress" in process.launches[0][1]
    first = json.dumps({"event": "voice_progress", "phase": "waiting_for_speech"}).encode() + b"\n"
    process.pending = first[:17]
    dialog.read_output()
    assert "Preparing" in dialog.status.text()
    process.pending = first[17:]
    dialog.read_output()
    assert "Microphone on" in dialog.status.text()
    process.pending = json.dumps({"event": "voice_progress", "phase": "capturing",
                                  "silence_seconds": 1.2, "required_silence_seconds": 5}).encode() + b"\n"
    dialog.read_output()
    assert "1.2 / 5.0" in dialog.status.text()
    for phase in ("microphone_off", "filtering", "transcribing", "thinking", "speaking"):
        process.pending = json.dumps({"event": "voice_progress", "phase": phase}).encode() + b"\n"
        dialog.read_output()
        assert "Microphone off" in dialog.status.text()
    process.pending = json.dumps({"ok": True, "message": "Completed", "transcript": "Synthetic utterance",
                                  "reply": "Synthetic reply"}).encode() + b"\n"
    dialog.finished(0, process.ExitStatus.NormalExit)
    assert dialog.status.text() == "Completed" and "Synthetic utterance" in dialog.details.toPlainText()
    assert dialog.process is None and dialog.temporary is None


def test_native_progress_rejects_private_unknown_fields_without_displaying_them(fake_dialog):
    dialog, process = fake_dialog
    process.pending = b'{"event":"voice_progress","phase":"thinking","text":"PRIVATE"}\n'
    dialog.read_output()
    assert dialog.process is None and "invalid progress" in dialog.status.text()
    assert "PRIVATE" not in dialog.status.text() + dialog.details.toPlainText()


def test_native_progress_counts_consumed_bytes_against_original_output_limit(fake_dialog):
    dialog, process = fake_dialog
    event = b'{"event":"voice_progress","phase":"capturing"}\n'
    process.pending = event * 500
    dialog.read_output()
    assert dialog.process is not None and not dialog.output
    process.pending = event * 500
    dialog.read_output()
    assert dialog.process is not None
    process.pending = event * 500
    dialog.read_output()
    assert dialog.process is None and "too much data" in dialog.status.text()


@pytest.mark.parametrize("size", [(680, 540), (480, 320)])
@pytest.mark.parametrize("theme", ["graphite", "light"])
def test_guided_initial_status_and_empty_results_are_visible_below_buttons(app, tmp_path, size, theme):
    from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect
    from shiboken6 import isValid

    from ai_os.native_widgets import theme_stylesheet

    dialog = voice_diagnostics.create_dialog(tmp_path)
    try:
        dialog.setStyleSheet(theme_stylesheet(theme))
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        assert dialog.process is None and not dialog.consent.isChecked()
        assert dialog.status.text() and "Microphone off" in dialog.status.text()
        assert dialog.details.placeholderText() and dialog.details.isReadOnly()
        assert dialog.status.accessibleName() == "Voice check progress"
        for control in (dialog.status, dialog.details):
            rect = QRect(control.mapTo(dialog, QPoint()), control.size())
            assert control.isVisible() and dialog.rect().contains(rect)
            assert rect.top() > dialog.record.geometry().bottom()
        assert dialog.details.geometry().top() > dialog.status.geometry().bottom()
    finally:
        dialog.reject()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(dialog, QEvent.Type.DeferredDelete)
        assert not isValid(dialog)
