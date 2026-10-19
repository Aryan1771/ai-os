"""Explicit voice checks with synthetic audio/model paths and harmless children."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore
from PySide6.QtCore import QByteArray, QProcess
from PySide6.QtWidgets import QApplication

from ai_os import voice_diagnostics as check
from ai_os.services.stt import TranscriptionResult
from ai_os.services.voice_errors import VoicePipelineError
from ai_os.settings_store import save_settings
from ai_os.speech_lease import speech_lease


@pytest.fixture(autouse=True)
def forbid_real_audio_and_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("This regression must never record, play audio or use a real model")

    monkeypatch.setattr("ai_os.services.voice_input.capture_once", forbidden)
    monkeypatch.setattr("ai_os.speech_queue.SpeechQueue.speak_text", forbidden)
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)
    monkeypatch.setattr("ai_os.hardware_profile.runtime_policy", lambda _home: None)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["voice-diagnostics-test"])


@pytest.fixture
def fake_loop(tmp_path, monkeypatch):
    save_settings({"speech_enabled": True, "whisper_language": "en",
                   "reply_language_mode": "selected", "voice_silence_seconds": 3},
                  tmp_path, human_confirmed=True)
    observed = {"capture": [], "model": [], "speech": [], "phases": []}

    def capture(config, *, return_result=False):
        observed["capture"].append((config, return_result))
        return TranscriptionResult(True, "A synthetic current utterance", detected_language="hi")

    def reply(text, language, home, *, metrics=None):
        observed["model"].append((text, language, home))
        return "A synthetic relevant reply"

    class Speech:
        def __init__(self, *_args, **_kwargs):
            pass

        def speak_text(self, text):
            observed["speech"].append(text)

    monkeypatch.setattr("ai_os.services.voice_input.capture_once", capture)
    monkeypatch.setattr("ai_os.speech_queue.SpeechQueue", Speech)
    monkeypatch.setattr("ai_os.companion_state.publish_state",
                        lambda phase, **_kwargs: observed["phases"].append(phase))
    monkeypatch.setattr(check, "local_reply", reply)
    return observed


@pytest.mark.parametrize("consent", [False, None, 1, "yes", "true"])
def test_every_check_requires_explicit_boolean_local_approval(tmp_path, fake_loop, consent):
    for action in ("play", "record"):
        with pytest.raises(PermissionError, match="Explicit local approval"):
            check.check_voice(action, "en", home=tmp_path, human_confirmed=consent)
    assert fake_loop["capture"] == fake_loop["model"] == fake_loop["speech"] == []


def test_continuous_listener_and_speech_setting_prevent_duplicate_recording(tmp_path, fake_loop):
    save_settings({"always_listening_enabled": True}, tmp_path, human_confirmed=True)
    with pytest.raises(PermissionError, match="continuous listening"):
        check.check_voice("record", "en", home=tmp_path, human_confirmed=True)
    save_settings({"always_listening_enabled": False, "speech_enabled": False},
                  tmp_path, human_confirmed=True)
    with pytest.raises(PermissionError, match="Enable spoken replies"):
        check.check_voice("record", "en", home=tmp_path, human_confirmed=True)
    assert fake_loop["capture"] == fake_loop["model"] == fake_loop["speech"] == []


def test_existing_speech_lease_blocks_recording_and_playback(tmp_path, fake_loop):
    with speech_lease(tmp_path) as acquired:
        assert acquired
        for action in ("record", "play"):
            with pytest.raises(VoicePipelineError) as failure:
                check.check_voice(action, "en", home=tmp_path, human_confirmed=True)
            assert failure.value.code == "voice_busy"
    assert fake_loop["capture"] == fake_loop["model"] == fake_loop["speech"] == []


def test_capture_failure_exposes_only_public_diagnostic_and_releases_lease(tmp_path, fake_loop, monkeypatch):
    def fail_capture(*_args, **_kwargs):
        raise RuntimeError("SYNTHETIC_PRIVATE_PATH_OR_TRANSCRIPT")

    monkeypatch.setattr("ai_os.services.voice_input.capture_once", fail_capture)
    with pytest.raises(VoicePipelineError) as failure:
        check.check_voice("record", "en", home=tmp_path, human_confirmed=True)
    assert "SYNTHETIC_PRIVATE" not in str(failure.value)
    assert fake_loop["model"] == fake_loop["speech"] == []
    assert fake_loop["phases"] == ["idle"]
    with speech_lease(tmp_path) as acquired:
        assert acquired


@pytest.mark.parametrize("language, expected", [("en", "en"), ("hi", "hi"), ("auto", "hi")])
def test_current_language_routes_same_turn_without_changing_saved_config(tmp_path, fake_loop, language, expected):
    config_before = (tmp_path / "config.json").read_bytes()
    result = check.check_voice("record", language, home=tmp_path, human_confirmed=True)
    captured, return_result = fake_loop["capture"][0]
    assert return_result
    assert captured.whisper_language == ("en" if language == "auto" else language)
    assert captured.reply_language_mode == ("match" if language == "auto" else "selected")
    assert captured.voice_command_seconds == 8 and captured.voice_max_utterance_seconds == 20
    assert captured.voice_silence_seconds == 3
    assert fake_loop["model"] == [(result["transcript"], expected, tmp_path)]
    assert fake_loop["speech"] == [result["reply"]]
    assert result["language"] == expected
    assert fake_loop["phases"] == ["thinking", "speaking", "idle"]
    assert set(result["timings"]) == {"capture_and_stt_seconds", "model_seconds",
                                       "synthesis_and_playback_seconds", "total_seconds"}
    assert (tmp_path / "config.json").read_bytes() == config_before
    assert not (tmp_path / "data/private/conversations.sqlite3").exists()
    with speech_lease(tmp_path) as acquired:
        assert acquired


def test_playback_only_check_never_captures_or_calls_model_even_if_speech_disabled(tmp_path, fake_loop):
    save_settings({"speech_enabled": False}, tmp_path)
    before = (tmp_path / "config.json").read_bytes()
    result = check.check_voice("play", "hi", home=tmp_path, human_confirmed=True)
    assert result["transcript"] == "" and result["reply"] == check.PHRASES["hi"]
    assert fake_loop["capture"] == fake_loop["model"] == []
    assert fake_loop["speech"] == [check.PHRASES["hi"]]
    assert (tmp_path / "config.json").read_bytes() == before


def test_unknown_language_never_reaches_model_or_speech(tmp_path, fake_loop, monkeypatch):
    monkeypatch.setattr("ai_os.services.voice_input.capture_once",
                        lambda *_args, **_kwargs: TranscriptionResult(True, "Synthetic", detected_language=None))
    with pytest.raises(VoicePipelineError) as failure:
        check.check_voice("record", "auto", home=tmp_path, human_confirmed=True)
    assert failure.value.code == "language_unknown"
    assert fake_loop["model"] == fake_loop["speech"] == []
    assert fake_loop["phases"] == ["idle"]


def test_revocation_during_model_turn_cancels_speech_and_releases_lease(tmp_path, fake_loop, monkeypatch):
    def revoke(*_args, **_kwargs):
        save_settings({"speech_enabled": False}, tmp_path)
        return "Do not play this reply"

    monkeypatch.setattr(check, "local_reply", revoke)
    with pytest.raises(VoicePipelineError):
        check.check_voice("record", "en", home=tmp_path, human_confirmed=True)
    assert fake_loop["speech"] == []
    assert fake_loop["phases"] == ["thinking", "idle"]
    with speech_lease(tmp_path) as acquired:
        assert acquired


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.payload), chunk_size):
            yield self.payload[offset:offset + chunk_size]


def fake_session(monkeypatch, payload):
    observed = []

    class Session:
        trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, **kwargs):
            observed.append((url, kwargs, self.trust_env))
            return FakeResponse(payload)

    monkeypatch.setattr(check.requests, "Session", Session)
    return observed


def test_local_reply_uses_current_utterance_only_without_tools_history_proxies_or_redirects(tmp_path, monkeypatch):
    from ai_os.conversation_memory import ConversationMemory

    memory = ConversationMemory(tmp_path)
    memory.append("Synthetic history that must stay out", "A private-looking synthetic response")
    memory.put("Synthetic note", "Do not send this to diagnostics")
    before = memory.path.read_bytes()
    payload = json.dumps({"message": {"content": "नमस्ते।"}}).encode()
    requests = fake_session(monkeypatch, payload)
    reply = check.local_reply("A current synthetic utterance", "hi", tmp_path)
    assert reply == "नमस्ते।"
    url, options, trust_env = requests[0]
    assert url == "http://127.0.0.1:11434/api/chat" and trust_env is False
    assert options["allow_redirects"] is False and options["timeout"] == (3, 35)
    body = options["json"]
    assert set(body) == {"model", "stream", "messages", "options"}
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert body["messages"][1]["content"] == "A current synthetic utterance"
    assert "Hindi using Devanagari" in body["messages"][0]["content"]
    assert "Synthetic history" not in json.dumps(body)
    assert "Do not send this" not in json.dumps(body)
    assert body["options"]["num_ctx"] <= 4096 and body["options"]["num_predict"] == 96
    assert memory.path.read_bytes() == before


def test_hardware_admission_and_cpu_override_are_preserved_with_public_timings(tmp_path, monkeypatch):
    import ai_os.hardware_profile as hardware
    monkeypatch.setattr(hardware, "runtime_policy", lambda home: {
        "ready": True, "model": "installed-reviewed-fallback", "options": {
            "num_ctx": 2048, "num_gpu": 0, "num_thread": 2}})
    calls = fake_session(monkeypatch, json.dumps({"message": {"content": "Ready."},
        "load_duration": 1000000000, "prompt_eval_duration": 500000000,
        "eval_duration": 250000000, "private_debug": "must not escape"}).encode())
    metrics = {}
    assert check.local_reply("Synthetic", "en", tmp_path, metrics=metrics) == "Ready."
    assert calls[0][1]["json"]["model"] == "installed-reviewed-fallback"
    options = calls[0][1]["json"]["options"]
    assert options["num_gpu"] == 0 and options["num_thread"] == 2 and options["num_ctx"] == 2048
    assert metrics == {"load_seconds": 1.0, "prompt_eval_seconds": .5, "eval_seconds": .25}
    monkeypatch.setattr(hardware, "runtime_policy", lambda home: {"ready": False})
    with pytest.raises(ValueError, match="admission"):
        check.local_reply("Synthetic", "en", tmp_path)
    assert len(calls) == 1


@pytest.mark.parametrize("provider,url", [
    ("openai_compatible", "http://127.0.0.1:8080/v1/chat/completions"),
    ("ollama", "https://127.0.0.1:11434/api/chat"),
    ("ollama", "http://remote.example/api/chat"),
    ("ollama", "http://user:password@localhost:11434/api/chat"),
    ("ollama", "http://localhost:11434/api/chat?private=1"),
    ("ollama", "http://localhost:11434/api/chat#private"),
])
def test_remote_authenticated_and_non_http_endpoints_are_rejected_without_request(tmp_path, monkeypatch, provider, url):
    (tmp_path / "config.json").write_text(json.dumps({"ai_provider": provider, "ollama_url": url}))
    observed = fake_session(monkeypatch, b"unused")
    with pytest.raises(ValueError, match="local Ollama"):
        check.local_reply("Synthetic utterance", "en", tmp_path)
    assert observed == []


@pytest.mark.parametrize("value", [
    None, [], {"message": None}, {"message": {}},
    {"message": {"content": ""}}, {"message": {"content": " "}},
    {"message": {"content": {"tool": "run_command"}}},
    {"message": {"content": "x" * 2001}},
    {"message": {"content": "Done", "tool_calls": [{"function": {"name": "run_command"}}]}},
    {"message": {"content": "Done", "function_call": {"name": "run_command"}}},
    {"message": {"content": json.dumps({"tool": "run_command", "arguments": {}})}},
    {"message": {"content": json.dumps({"function": "open_app"})}},
    {"message": {"content": json.dumps([{"tool": "run_command", "arguments": {}}])}},
    {"message": {"content": json.dumps({"reply": "A structured reply"})}},
    {"message": {"content": '```json\n{"tool":"run_command"}\n```'}},
])
def test_invalid_or_tool_proposing_model_output_is_never_returned_as_spoken_success(tmp_path, monkeypatch, value):
    fake_session(monkeypatch, json.dumps(value).encode())
    with pytest.raises(ValueError):
        check.local_reply("Please open a browser", "en", tmp_path)


@pytest.mark.parametrize("payload", [b"invalid json", b"x" * 65537])
def test_model_reply_has_json_and_byte_limits(tmp_path, monkeypatch, payload):
    fake_session(monkeypatch, payload)
    with pytest.raises(ValueError):
        check.local_reply("A synthetic question", "en", tmp_path)


def test_trickling_model_reply_has_total_deadline(tmp_path, monkeypatch):
    fake_session(monkeypatch, json.dumps({"message": {"content": "A reply"}}).encode())
    ticks = iter((0, 41))
    monkeypatch.setattr(check.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="time or size limit"):
        check.local_reply("A synthetic question", "en", tmp_path)


def test_opening_and_consent_only_do_not_launch_worker_or_capture(app, tmp_path, monkeypatch):
    launches = []

    class FakeProcess(QProcess):
        def start(self, program, arguments):
            launches.append((program, arguments))

    monkeypatch.setattr(QtCore, "QProcess", FakeProcess)
    dialog = check.create_dialog(tmp_path)
    try:
        assert not launches and dialog.process is None and dialog.temporary is None
        assert not dialog.record.isEnabled()
        dialog.start("record")
        assert not launches
        dialog.consent.setChecked(True)
        assert not launches and dialog.record.isEnabled()
        dialog.record.click()
        assert len(launches) == 1
        program, arguments = launches[0]
        assert program == sys.executable
        assert arguments[:4] == ["-m", "ai_os.voice_diagnostics", "--worker", "record"]
        assert arguments[-1] == "--confirmed"
        private = Path(dialog.temporary.name)
        assert private.stat().st_mode & 0o777 == 0o700
        environment = dialog.process.processEnvironment()
        assert environment.value("AI_OS_HOME") == str(tmp_path)
        assert environment.value("AI_OS_VOICE_TMP") == str(private)
        assert not dialog.consent.isEnabled() and dialog.stop.isEnabled()
        # A precise deadline avoids the coarse timer's five-percent rounding.
        assert dialog.timer.isActive() and 0 < dialog.timer.remainingTime() <= 111000
        dialog.cancel("Stopped synthetic check")
        assert not private.exists() and dialog.process is None
        assert not dialog.timer.isActive() and not dialog.stop.isEnabled()
    finally:
        dialog.reject()


@pytest.mark.parametrize("mode,saved_language,selected", [
    ("selected", "en", "en"), ("selected", "hi", "hi"), ("match", "hi", "auto"),
])
def test_native_check_starts_with_current_saved_language_without_writing_settings(
    app, tmp_path, mode, saved_language, selected,
):
    save_settings({"reply_language_mode": mode, "whisper_language": saved_language}, tmp_path)
    before = (tmp_path / "config.json").read_bytes()
    dialog = check.create_dialog(tmp_path)
    assert dialog.language.currentData() == selected
    assert dialog.process is None and not dialog.consent.isChecked()
    dialog.language.setCurrentIndex(dialog.language.findData("en"))
    dialog.reject()
    assert (tmp_path / "config.json").read_bytes() == before


def test_worker_stdout_limit_cancels_and_never_displays_unbounded_data(app, tmp_path, monkeypatch):
    sentinel = b"SYNTHETIC_PRIVATE_OUTPUT" * 4000

    class FakeProcess(QProcess):
        def start(self, *_args):
            pass

        def readAllStandardOutput(self):
            return QByteArray(sentinel)

    monkeypatch.setattr(QtCore, "QProcess", FakeProcess)
    dialog = check.create_dialog(tmp_path)
    dialog.start("play")
    private = Path(dialog.temporary.name)
    dialog.read_output()
    assert dialog.process is None and not private.exists()
    assert not dialog.output and not dialog.details.toPlainText()
    assert "too much data" in dialog.status.text()
    assert "SYNTHETIC_PRIVATE_OUTPUT" not in dialog.status.text()
    dialog.reject()


@pytest.mark.parametrize("payload", [b"malformed", b"null", b"[]"])
def test_invalid_worker_completion_is_sanitized_without_showing_old_details(app, tmp_path, monkeypatch, payload):
    class FakeProcess(QProcess):
        def start(self, *_args):
            pass

        def readAllStandardOutput(self):
            return QByteArray(payload)

    monkeypatch.setattr(QtCore, "QProcess", FakeProcess)
    dialog = check.create_dialog(tmp_path)
    dialog.details.setPlainText("OLD_SYNTHETIC_PRIVATE_TRANSCRIPT")
    dialog.start("play")
    private = Path(dialog.temporary.name)
    dialog.finished(0, QProcess.ExitStatus.NormalExit)
    assert dialog.process is None and not private.exists()
    assert not dialog.details.toPlainText()
    assert "valid result" in dialog.status.text()
    assert "OLD_SYNTHETIC_PRIVATE" not in dialog.status.text()
    dialog.reject()


def test_worker_setup_failure_restores_controls_and_cleans_private_storage(app, tmp_path, monkeypatch):
    class FailingProcess(QProcess):
        def start(self, *_args):
            raise RuntimeError("SYNTHETIC_PRIVATE_FAILURE")

    monkeypatch.setattr(QtCore, "QProcess", FailingProcess)
    dialog = check.create_dialog(tmp_path)
    try:
        dialog.consent.setChecked(True)
        dialog.start("record")
        assert dialog.process is None and dialog.temporary is None
        assert dialog.record.isEnabled() and dialog.consent.isEnabled()
        assert not dialog.timer.isActive() and not dialog.stop.isEnabled()
        assert "SYNTHETIC_PRIVATE_FAILURE" not in dialog.status.text()
    finally:
        dialog.reject()


def test_starting_process_without_pid_never_signals_callers_group(app, tmp_path, monkeypatch):
    signals = []

    class StartingProcess(QProcess):
        def state(self):
            return QProcess.ProcessState.Starting

        def processId(self):
            return 0

        def terminate(self):
            pass

        def waitForFinished(self, _timeout):
            return True

    dialog = check.create_dialog(tmp_path)
    dialog.process = StartingProcess(dialog)
    monkeypatch.setattr(check.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    dialog.cancel("Cancelled synthetic startup")
    assert signals == []
    assert dialog.process is None
    dialog.reject()


def test_non_session_worker_pid_never_signals_an_unowned_group(app, tmp_path, monkeypatch):
    signals = []
    fallback = []

    class FakeProcess(QProcess):
        def state(self):
            return QProcess.ProcessState.Running

        def processId(self):
            return 991001

        def terminate(self):
            fallback.append("terminate")

        def waitForFinished(self, _timeout):
            return True

    dialog = check.create_dialog(tmp_path)
    dialog.process = FakeProcess(dialog)
    monkeypatch.setattr(check.os, "getpgid", lambda _pid: os.getpgrp())
    monkeypatch.setattr(check.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    dialog.cancel("Cancelled synthetic unowned session")
    assert signals == [] and fallback == ["terminate"]
    assert dialog.process is None
    dialog.reject()


def _alive(pid):
    try:
        status = Path(f"/proc/{pid}/stat").read_text().split()
        return status[2] != "Z"
    except FileNotFoundError:
        return False


@pytest.mark.skipif(sys.platform != "linux", reason="Linux new-session group cleanup")
@pytest.mark.parametrize("ignore_descendant_term", [False, True])
def test_stop_reaps_harmless_child_and_terminates_owned_descendant_group(app, tmp_path, ignore_descendant_term):
    dialog = check.create_dialog(tmp_path)
    process = QProcess(dialog)
    process.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
    marker = tmp_path / "harmless-child.json"
    ready = tmp_path / "harmless-descendant-ready"
    descendant = (
        "import os,pathlib,signal,time;"
        + ("signal.signal(signal.SIGTERM,signal.SIG_IGN);" if ignore_descendant_term else "")
        + f"pathlib.Path({str(ready)!r}).write_text('ready');time.sleep(30)"
    )
    program = (
        "import json,os,pathlib,subprocess,sys,time;"
        f"child=subprocess.Popen([sys.executable,'-c',{descendant!r}]);"
        f"pathlib.Path({str(marker)!r}).write_text(json.dumps([os.getpid(),child.pid]));"
        "time.sleep(30)"
    )
    owned_group = None
    child_pid = None
    try:
        process.start(sys.executable, ["-c", program])
        assert process.waitForStarted(1500)
        root_pid = process.processId()
        assert root_pid > 1 and os.getpgid(root_pid) == root_pid != os.getpgrp()
        owned_group = root_pid
        deadline = time.monotonic() + 3
        while (not marker.exists() or not ready.exists()) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        root_pid, child_pid = json.loads(marker.read_text())
        assert ready.exists()
        assert root_pid == process.processId()
        assert os.getpgid(root_pid) == root_pid != os.getpgrp()
        assert os.getpgid(child_pid) == root_pid
        dialog.process = process
        dialog.temporary = tempfile.TemporaryDirectory(prefix="voice-check-stop-test-", dir=tmp_path)
        private = Path(dialog.temporary.name)
        (private / "fake-audio.wav").write_bytes(b"synthetic temporary data")
        dialog.cancel("Stopped synthetic child")
        deadline = time.monotonic() + 2
        while _alive(child_pid) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert process.state() == QProcess.ProcessState.NotRunning
        assert not _alive(child_pid)
        assert not private.exists() and dialog.process is None
    finally:
        # Only the verified disposable new session may ever receive a signal.
        if owned_group and owned_group != os.getpgrp():
            try:
                os.killpg(owned_group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(1500)
        dialog.reject()
