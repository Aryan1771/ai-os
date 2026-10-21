"""Microphone routing and native metadata refresh, with no host audio access."""
from __future__ import annotations

import json
import os
import subprocess
from collections import deque
from types import SimpleNamespace

import pytest

from ai_os import audio_input
from ai_os.audio_input import AudioInputError, InputDevice
from ai_os.config import atomic_json, load_config, load_raw_config
from ai_os.services.voice_errors import diagnostic
from ai_os.settings_store import save_settings


def source(name="alsa_input.test", description="Test microphone", **props):
    return {"type": "PipeWire:Interface:Node", "info": {"props": {
        "media.class": "Audio/Source", "node.name": name,
        "node.description": description, **props,
    }}}


def test_parser_returns_only_bounded_capture_sources_without_private_properties():
    payload = [source(description=" <b>Local</b>\n\u202e microphone\x00 ",
                      **{"device.serial": "private", "object.serial": 99}),
               source("output", **{"media.class": "Audio/Sink"}),
               source("camera", **{"media.class": "Video/Source"}),
               source("stream", **{"media.class": "Stream/Input/Audio"}),
               source("sink.monitor"), source("monitor", **{"stream.monitor": True}),
               source("--target=evil"), source("auto"), source(""),
               {"type": "PipeWire:Interface:Client", "info": {"props": {}}},
               [], None, {"info": None}]
    devices = audio_input.parse_input_devices(json.dumps(payload))
    assert devices == (InputDevice("alsa_input.test", "<b>Local</b> microphone"),)
    assert "private" not in repr(devices) and "99" not in repr(devices)


@pytest.mark.parametrize("target", [None, True, 12, "12", "0", "auto", "--target=x",
                                    "input;id", "input/other", "input\nnext", "input x",
                                    "$(id)", "a" * 256, "माइक"])
def test_setting_rejects_malformed_or_transient_targets_without_saving(tmp_path, target):
    before = load_raw_config(tmp_path)
    with pytest.raises(ValueError):
        save_settings({"voice_input_target": target}, tmp_path, human_confirmed=True)
    assert load_raw_config(tmp_path) == before


def test_selection_requires_trusted_confirmation_even_with_settings_lock_off(tmp_path):
    save_settings({"sandbox_lock_settings": False}, tmp_path, human_confirmed=True)
    with pytest.raises(PermissionError, match="voice_input_target"):
        save_settings({"voice_input_target": "alsa_input.test"}, tmp_path)
    save_settings({"voice_input_target": "alsa_input.test"}, tmp_path, human_confirmed=True)
    config = load_config(tmp_path)
    assert config.voice_input_target == "alsa_input.test"
    assert not config.always_listening_enabled and not config.wake_word_enabled
    assert config.voice_silence_seconds == 5


def test_old_configuration_preserves_default_and_recorder_does_not_scan(tmp_path, monkeypatch):
    atomic_json(tmp_path / "config.json", {"whisper_language": "hi"})
    assert load_config(tmp_path).voice_input_target == ""
    monkeypatch.setattr(audio_input, "discover_input_devices",
                        lambda: pytest.fail("The preserved default does not require discovery"))
    assert audio_input.recorder_arguments() == [
        "--raw", "--format", "s16", "--rate", "16000", "--channels", "1", "-"]


def test_selected_input_is_checked_and_pinned_without_fallback_or_movement(monkeypatch):
    monkeypatch.setattr(audio_input, "discover_input_devices",
                        lambda: (InputDevice("alsa_input.test", "Test input"),))
    args = audio_input.recorder_arguments("alsa_input.test")
    assert args[:7] == ["--raw", "--format", "s16", "--rate", "16000", "--channels", "1"]
    assert args[7:9] == ["--target", "alsa_input.test"] and args[-1] == "-"
    assert json.loads(args[10]) == {"node.dont-fallback": True,
                                    "node.dont-reconnect": True, "node.dont-move": True}


def test_disappeared_input_is_never_replaced_with_another_device(monkeypatch):
    monkeypatch.setattr(audio_input, "discover_input_devices",
                        lambda: (InputDevice("alsa_input.other", "Other input"),))
    with pytest.raises(AudioInputError, match="no fallback") as raised:
        audio_input.recorder_arguments("alsa_input.test")
    code, message = diagnostic(raised.value, "listening")
    assert code == "input_unavailable" and "No request" in message
    assert "alsa_input" not in message


@pytest.mark.parametrize("payload", [b"not json", b"{}", b"[null]" * 100,
                                     b"\xff", json.dumps([source(), source()])])
def test_invalid_or_ambiguous_inventory_fails_closed(payload):
    with pytest.raises(AudioInputError):
        audio_input.parse_input_devices(payload)


def test_inventory_bounds_bytes_nodes_and_inputs(monkeypatch):
    monkeypatch.setattr(audio_input, "MAX_DUMP_BYTES", 5)
    with pytest.raises(AudioInputError, match="size"):
        audio_input.parse_input_devices(b"[null]")
    monkeypatch.setattr(audio_input, "MAX_DUMP_BYTES", 1024)
    monkeypatch.setattr(audio_input, "MAX_DUMP_NODES", 1)
    with pytest.raises(AudioInputError, match="node"):
        audio_input.parse_input_devices("[null,null]")
    monkeypatch.setattr(audio_input, "MAX_DUMP_NODES", 10)
    monkeypatch.setattr(audio_input, "MAX_INPUTS", 1)
    with pytest.raises(AudioInputError, match="input"):
        audio_input.parse_input_devices(json.dumps([source("first"), source("second")]))


def test_discovery_uses_only_fixed_bounded_metadata_command(monkeypatch):
    calls = []

    def run():
        calls.append(True)
        return json.dumps([source()]).encode()

    monkeypatch.setattr(audio_input, "_run_inventory", run)
    assert audio_input.discover_input_devices() == (InputDevice("alsa_input.test", "Test microphone"),)
    assert calls == [True]


@pytest.mark.parametrize("failure", [None, "timeout", "oversize", "exit"])
def test_inventory_reader_is_bounded_reaped_and_stays_in_caller_group(monkeypatch, failure):
    calls = []
    output = deque([b"[]", b""])
    closed = []
    stream = SimpleNamespace(fileno=lambda: 57, close=lambda: closed.append(True))
    process = SimpleNamespace(stdout=stream, returncode=None, kills=0)

    def wait(timeout):
        assert 0 < timeout <= 4
        process.returncode = 1 if failure == "exit" else 0

    def kill():
        process.kills += 1

    process.wait = wait
    process.poll = lambda: process.returncode
    process.kill = kill

    def launch(argv, **kwargs):
        calls.append((argv, kwargs))
        return process

    class Selector:
        def __init__(self):
            self.registered = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def register(self, target, _events):
            assert target is stream
            self.registered = True

        def get_map(self):
            return {57: stream} if self.registered else {}

        def select(self, timeout):
            assert 0 < timeout <= .1
            return [(SimpleNamespace(fileobj=stream), 1)]

        def unregister(self, _target):
            self.registered = False

    monkeypatch.setattr(audio_input.subprocess, "Popen", launch)
    monkeypatch.setattr(audio_input.selectors, "DefaultSelector", Selector)
    monkeypatch.setattr(audio_input.os, "read", lambda fd, size: output.popleft())
    if failure == "timeout":
        clock = iter([0, 5])
        monkeypatch.setattr(audio_input.time, "monotonic", lambda: next(clock))
    elif failure == "oversize":
        monkeypatch.setattr(audio_input, "MAX_DUMP_BYTES", 1)
    if failure:
        with pytest.raises((subprocess.TimeoutExpired, AudioInputError)):
            audio_input._run_inventory()
    else:
        assert audio_input._run_inventory() == b"[]"
    assert process.kills == int(failure in {"timeout", "oversize"})
    assert closed == [True]
    assert calls == [(["/usr/bin/pw-dump", "--no-colors"], {
        "cwd": "/", "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL, "shell": False, "start_new_session": False,
        "bufsize": 0})]


@pytest.mark.parametrize("failure", ["timeout", "missing", "exit"])
def test_discovery_failures_hide_backend_text(monkeypatch, failure):
    private = "private graph names and backend output"

    def run(*_args, **_kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired("pw-dump", 4, output=private)
        if failure == "missing":
            raise OSError(private)
        raise AudioInputError("Microphone input discovery failed.")

    monkeypatch.setattr(audio_input, "_run_inventory", run)
    with pytest.raises(AudioInputError) as raised:
        audio_input.discover_input_devices()
    assert private not in str(raised.value)


def test_continuous_capture_checks_missing_selection_before_recorder_start(tmp_path, monkeypatch):
    from ai_os.services import listener

    service = listener.AlwaysListeningService(
        run_dir=tmp_path, transcriber=SimpleNamespace(), on_transcript=lambda _: None,
        input_target="alsa_input.missing", require_wake_word=False)
    monkeypatch.setattr(service, "availability", lambda: (True, "synthetic"))
    monkeypatch.setattr(audio_input, "discover_input_devices", lambda: ())
    monkeypatch.setattr(listener.subprocess, "Popen", lambda *_a, **_k: pytest.fail("No recorder"))
    with pytest.raises(AudioInputError):
        service.run_forever()
    assert service._process is None


def test_one_shot_capture_checks_missing_selection_before_recorder_start(tmp_path, monkeypatch):
    from ai_os.services import voice_input

    config = load_config(tmp_path)
    object.__setattr__(config, "voice_input_target", "alsa_input.missing")
    monkeypatch.setattr(voice_input, "WhisperCppTranscriber",
                        lambda *_a, **_k: SimpleNamespace(availability=lambda: (True, "synthetic")))
    monkeypatch.setattr(audio_input, "discover_input_devices", lambda: ())
    monkeypatch.setattr(voice_input.subprocess, "Popen", lambda *_a, **_k: pytest.fail("No recorder"))
    with pytest.raises(AudioInputError):
        voice_input.capture_once(config)


def test_voice_worker_passes_saved_input_to_listener_without_capture(tmp_path, monkeypatch):
    from ai_os import config as config_module
    from ai_os import runtime_services
    from ai_os.services import listener

    save_settings({"voice_input_target": "alsa_input.saved", "always_listening_enabled": True,
                   "conversation_listening_enabled": True}, tmp_path, human_confirmed=True)
    config = load_config(tmp_path)
    observed = []

    class InertListener:
        def __init__(self, **kwargs):
            observed.append(kwargs)

        def run_forever(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(config_module, "load_config", lambda: config)
    monkeypatch.setattr(listener, "AlwaysListeningService", InertListener)
    assert runtime_services.voice_worker() == 0
    assert observed[0]["input_target"] == "alsa_input.saved"
    assert observed[0]["silence_seconds"] == 5


def test_selection_change_reloads_voice_signature_without_enabling_listening(tmp_path, monkeypatch):
    from ai_os.runtime_services import VoiceSupervisor

    supervisor = VoiceSupervisor(tmp_path)
    stops = []
    monkeypatch.setattr(supervisor, "stop", lambda: stops.append(True))
    supervisor.tick()
    supervisor.tick()
    assert len(stops) == 1 and supervisor.process is None
    save_settings({"voice_input_target": "alsa_input.saved"}, tmp_path, human_confirmed=True)
    supervisor.tick()
    assert len(stops) == 2 and supervisor.process is None
    assert not load_raw_config(tmp_path)["always_listening_enabled"]


@pytest.mark.parametrize("present", [True, False])
def test_readiness_checks_selected_source_instead_of_default_without_names(
    tmp_path, monkeypatch, present,
):
    import requests

    from ai_os import runtime_health

    calls = []
    save_settings({"voice_input_target": "alsa_input.selected"}, tmp_path, human_confirmed=True)
    monkeypatch.setattr(audio_input, "discover_input_devices", lambda: (
        (InputDevice("alsa_input.selected", "Private peripheral text"),) if present else ()))
    monkeypatch.setattr(runtime_health, "voice_readiness", lambda *_a: {
        "transcriber_ready": True, "wake_assets_ready": True})
    monkeypatch.setattr(runtime_health.subprocess, "run", lambda argv, **_kwargs: (
        calls.append(argv) or SimpleNamespace(returncode=0, stdout="active")))

    def unavailable():
        raise requests.ConnectionError("synthetic offline")

    monkeypatch.setattr(runtime_health.requests, "Session", unavailable)
    report = runtime_health.report(tmp_path)
    assert report["microphone_selection"] == "explicit"
    assert report["selected_input_status"] == ("present" if present else "unavailable")
    assert report["pipewire_source_query"] == ("ready" if present else "unavailable")
    assert report["microphone_mute_check"] == "not_checked_for_explicit_input"
    assert "microphone_muted" not in report
    assert not any("wpctl" in item for argv in calls for item in argv)
    assert ("pipewire_input_unverified" in report["voice_blockers"]) is not present
    assert "alsa_input" not in json.dumps(report) and "Private peripheral" not in json.dumps(report)


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(["regenos-input-selection-test"])


def destroy_enrollment_owner(window, processes):
    """Retire fake Qt children while their fixture and subclass are still alive."""
    from PySide6.QtCore import QCoreApplication, QEvent, QTimer
    from shiboken6 import isValid

    assert not any(timer.isActive() for timer in window.findChildren(QTimer))
    destroyed = []
    window.destroyed.connect(lambda: destroyed.append(True))
    window.deleteLater()
    QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
    assert destroyed == [True]
    assert not isValid(window)
    assert all(not isValid(process) for process in processes)


@pytest.fixture
def settings_window(app, tmp_path):
    from ai_os.native_settings import SettingsWindow
    window = SettingsWindow(tmp_path, launch_companion=False)
    yield window
    window.poll.stop()
    window.access_poll.stop()
    window.conversation.grant_timer.stop()
    window.saved = window.collect()
    window.close()


@pytest.fixture
def fake_scan(monkeypatch):
    from PySide6.QtCore import QProcess

    from ai_os import native_settings

    instances = []

    class FakeScan(QProcess):
        def __init__(self, parent):
            super().__init__(parent)
            self.output = b""
            self.errors = b""
            self.running = False
            self.launches = []
            self.kills = 0
            instances.append(self)

        def start(self, program, arguments):
            self.running = True
            self.launches.append((program, arguments))

        def state(self):
            return QProcess.ProcessState.Running if self.running else QProcess.ProcessState.NotRunning

        def readAllStandardOutput(self):
            output, self.output = self.output, b""
            return output

        def readAllStandardError(self):
            output, self.errors = self.errors, b""
            return output

        def kill(self):
            self.kills += 1

        def waitForFinished(self, _timeout):
            self.running = False
            return True

        def finish(self, code=0):
            self.running = False
            self.finished.emit(code, QProcess.ExitStatus.NormalExit)

    monkeypatch.setattr(native_settings, "QProcess", FakeScan)
    return instances


def test_native_input_refresh_is_explicit_asynchronous_and_never_records(settings_window, fake_scan):
    window = settings_window
    assert not fake_scan and window.input_scan_process is None
    window.refresh_audio_inputs()
    process = fake_scan[0]
    assert not window.refresh_inputs_button.isEnabled() and window.input_scan_timer.isActive()
    assert process.launches == [("/usr/bin/pw-dump", ["--no-colors"])]
    window.refresh_audio_inputs()
    assert len(fake_scan) == 1
    process.output = json.dumps([source()]).encode()
    process.finish()
    assert window.refresh_inputs_button.isEnabled() and not window.input_scan_timer.isActive()
    assert window.fields["voice_input_target"].findData("alsa_input.test") == 1
    assert window.fields["voice_input_target"].currentData() == ""
    assert not load_raw_config(window.home)["always_listening_enabled"]
    assert "Found 1" in window.input_device_status.text()


def test_refresh_preserves_unsaved_missing_selection(settings_window, fake_scan):
    window = settings_window
    combo = window.fields["voice_input_target"]
    combo.addItem("Previously selected", "alsa_input.missing")
    combo.setCurrentIndex(1)
    window.refresh_audio_inputs()
    fake_scan[0].output = json.dumps([source()]).encode()
    fake_scan[0].finish()
    assert combo.currentData() == "alsa_input.missing"
    assert "no fallback" in combo.currentText()
    assert "unavailable" in window.input_device_status.text()
    assert load_raw_config(window.home)["voice_input_target"] == ""


@pytest.mark.parametrize("failure", ["timeout", "oversize", "exit", "invalid", "start"])
def test_native_scan_failure_preserves_selection_and_suppresses_raw_output(
    settings_window, fake_scan, monkeypatch, failure,
):
    from PySide6.QtCore import QProcess
    window = settings_window
    window.refresh_audio_inputs()
    process = fake_scan[0]
    private = b"private devices and backend errors"
    process.errors = private
    if failure == "timeout":
        window.audio_input_scan_timeout()
        assert process.kills == 1
    elif failure == "oversize":
        monkeypatch.setattr(audio_input, "MAX_DUMP_BYTES", 8)
        process.output = private
        process.readyReadStandardOutput.emit()
        assert process.kills == 1
    elif failure == "start":
        process.running = False
        process.errorOccurred.emit(QProcess.ProcessError.FailedToStart)
    elif failure == "invalid":
        process.output = private
    process.finish(1 if failure == "exit" else 0)
    assert window.input_scan_process is None and window.refresh_inputs_button.isEnabled()
    assert window.fields["voice_input_target"].currentData() == ""
    assert not window.input_scan_output
    assert private.decode() not in window.input_device_status.text()


def test_saved_selection_can_be_restored_after_refresh_removes_its_item(app, tmp_path, fake_scan):
    from ai_os.native_settings import SettingsWindow
    save_settings({"voice_input_target": "alsa_input.saved"}, tmp_path, human_confirmed=True)
    window = SettingsWindow(tmp_path, launch_companion=False)
    try:
        combo = window.fields["voice_input_target"]
        assert combo.currentData() == "alsa_input.saved"
        combo.setCurrentIndex(0)
        window.refresh_audio_inputs()
        fake_scan[-1].output = b"[]"
        fake_scan[-1].finish()
        assert combo.findData("alsa_input.saved") == -1
        window.restore()
        assert combo.currentData() == "alsa_input.saved"
    finally:
        window.poll.stop()
        window.access_poll.stop()
        window.conversation.grant_timer.stop()
        window.close()


def test_closing_settings_cancels_only_its_metadata_scan(settings_window, fake_scan):
    window = settings_window
    window.refresh_audio_inputs()
    process = fake_scan[0]
    window.close()
    assert process.kills == 1
    assert window.input_scan_process is None and not window.input_scan_timer.isActive()


def test_native_microphone_save_requires_approval_and_never_enables_listening(
    settings_window, fake_scan, monkeypatch,
):
    from PySide6.QtWidgets import QMessageBox
    window = settings_window
    window.refresh_audio_inputs()
    fake_scan[0].output = json.dumps([source()]).encode()
    fake_scan[0].finish()
    window.fields["voice_input_target"].setCurrentIndex(1)
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Cancel)
    assert not window.save()
    assert load_raw_config(window.home)["voice_input_target"] == ""
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Apply)
    assert window.save()
    saved = load_raw_config(window.home)
    assert saved["voice_input_target"] == "alsa_input.test"
    assert not saved["always_listening_enabled"] and not saved["wake_word_enabled"]


def test_enrollment_missing_input_records_nothing_and_releases_shared_lease(
    app, tmp_path, monkeypatch, fake_scan,
):
    from ai_os import native_settings, speaker_setup
    from ai_os.speaker_identity import profile_path
    from ai_os.speech_lease import speech_lease

    model = tmp_path / "speaker.onnx"
    model.write_bytes(b"synthetic local model")
    save_settings({"speaker_model": str(model), "voice_input_target": "alsa_input.missing"},
                  tmp_path, human_confirmed=True)
    monkeypatch.setattr(speaker_setup, "backend_available", lambda: True)
    monkeypatch.setattr(speaker_setup.shutil, "which", lambda _: "/usr/bin/pw-record")
    monkeypatch.setattr(speaker_setup, "QProcess", native_settings.QProcess)
    monkeypatch.setattr(audio_input, "discover_input_devices", lambda: pytest.fail("No synchronous query"))
    window = speaker_setup.SpeakerSetupDialog(tmp_path)
    try:
        window.consent.setChecked(True)
        window.record()
        assert window.phase == "input_check" and window.temporary is None
        fake_scan[0].output = b"[]"
        fake_scan[0].finish()
        assert window.process is None and window.temporary is None
        assert "selected microphone is unavailable" in window.status.text()
        assert not profile_path(tmp_path).exists()
        with speech_lease(tmp_path) as acquired:
            assert acquired
    finally:
        window.reject()
        destroy_enrollment_owner(window, fake_scan)


@pytest.fixture
def selected_enrollment(app, tmp_path, monkeypatch, fake_scan):
    from ai_os import native_settings, speaker_setup

    model = tmp_path / "speaker.onnx"
    model.write_bytes(b"synthetic local model")
    save_settings({"speaker_model": str(model), "voice_input_target": "alsa_input.selected"},
                  tmp_path, human_confirmed=True)
    monkeypatch.setattr(speaker_setup, "backend_available", lambda: True)
    monkeypatch.setattr(speaker_setup.shutil, "which", lambda _: "/usr/bin/pw-record")
    monkeypatch.setattr(speaker_setup, "QProcess", native_settings.QProcess)
    monkeypatch.setattr(audio_input, "discover_input_devices", lambda: pytest.fail("No synchronous query"))
    window = speaker_setup.SpeakerSetupDialog(tmp_path)
    yield window
    window.reject()
    destroy_enrollment_owner(window, fake_scan)


def test_enrollment_precheck_requires_record_click_and_keeps_cancel_responsive(
    selected_enrollment, fake_scan, app,
):
    from PySide6.QtCore import QTimer

    from ai_os.speech_lease import speech_lease

    window = selected_enrollment
    assert not fake_scan
    window.record()
    assert not fake_scan
    window.consent.setChecked(True)
    assert not fake_scan
    window.record_button.click()
    process = fake_scan[0]
    assert process.launches == [("/usr/bin/pw-dump", ["--no-colors"])]
    assert window.phase == "input_check" and window.temporary is None
    assert not window.capture_timer.isActive() and window.input_check_timer.isActive()
    assert window.cancel_button.isEnabled()
    with speech_lease(window.home) as acquired:
        assert not acquired
    events = []
    QTimer.singleShot(0, lambda: events.append("GUI callback ran while metadata was pending"))
    app.processEvents()
    assert events
    window.cancel_button.click()
    assert process.kills == 1 and window.process is None
    assert window.phase == "idle" and not window.input_check_timer.isActive()
    assert not window.output and window.temporary is None
    process.output = json.dumps([source("alsa_input.selected")]).encode()
    window.input_check_finished(process, 0, process.ExitStatus.NormalExit)
    assert len(fake_scan) == 1  # A late success cannot resurrect recording.
    with speech_lease(window.home) as acquired:
        assert acquired


def test_enrollment_success_uses_one_async_scan_and_exact_input_with_no_second_query(
    selected_enrollment, fake_scan,
):
    from ai_os.speaker_identity import profile_path

    window = selected_enrollment
    window.consent.setChecked(True)
    window.record()
    assert window.temporary is None and not profile_path(window.home).exists()
    process = fake_scan[0]
    process.output = json.dumps([source("alsa_input.selected")]).encode()
    process.finish()
    assert len(fake_scan) == 2
    program, arguments = fake_scan[1].launches[0]
    assert program == "/usr/bin/pw-record" and arguments[8] == "alsa_input.selected"
    assert json.loads(arguments[10])["node.dont-fallback"] is True
    assert window.phase == "capture" and window.capture_timer.isActive()
    assert not window.input_check_timer.isActive() and not window.output
    assert window.temporary is not None
    assert not profile_path(window.home).exists()


@pytest.mark.parametrize("change", ["target", "model_path", "threshold", "consent", "model_file", "listening"])
def test_enrollment_async_precheck_rejects_changed_target_configuration_or_consent(
    selected_enrollment, fake_scan, change,
):
    from ai_os.speaker_identity import profile_path
    from ai_os.speech_lease import speech_lease

    window = selected_enrollment
    window.consent.setChecked(True)
    window.record()
    process = fake_scan[0]
    if change == "consent":
        window.consent.setChecked(False)
    elif change == "model_file":
        window.model.write_bytes(b"changed model while checking selected microphone")
    else:
        changes = {
            "target": {"voice_input_target": "alsa_input.other"},
            "model_path": {"speaker_model": "different-model.onnx"},
            "threshold": {"speaker_threshold": .8},
            "listening": {"always_listening_enabled": True},
        }
        save_settings(changes[change], window.home, human_confirmed=True)
    process.output = json.dumps([source("alsa_input.selected"), source("alsa_input.other")]).encode()
    process.finish()
    assert len(fake_scan) == 1 and window.process is None
    assert window.temporary is None and not profile_path(window.home).exists()
    assert "changed during the check" in window.status.text()
    with speech_lease(window.home) as acquired:
        assert acquired


@pytest.mark.parametrize("failure", ["timeout", "oversize", "exit", "invalid", "start"])
def test_enrollment_async_precheck_failures_preserve_profile_release_lease_and_capture_nothing(
    selected_enrollment, fake_scan, monkeypatch, failure,
):
    from PySide6.QtCore import QProcess

    from ai_os.speaker_identity import profile_path
    from ai_os.speech_lease import speech_lease

    window = selected_enrollment
    profile = profile_path(window.home)
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_bytes(b"existing synthetic private profile")
    window.consent.setChecked(True)
    window.record()
    process = fake_scan[0]
    private = b"private peripheral text and backend errors"
    process.errors = private
    if failure == "timeout":
        window.input_check_timeout()
    elif failure == "oversize":
        monkeypatch.setattr(audio_input, "MAX_DUMP_BYTES", 8)
        process.output = private
        process.readyReadStandardOutput.emit()
    elif failure == "start":
        process.running = False
        process.errorOccurred.emit(QProcess.ProcessError.FailedToStart)
    else:
        process.output = private
        process.finish(1 if failure == "exit" else 0)
    assert len(fake_scan) == 1 and window.process is None
    assert window.temporary is None and not window.input_check_timer.isActive()
    assert not window.output and not window.raw
    assert profile.read_bytes() == b"existing synthetic private profile"
    assert private.decode() not in window.status.text()
    with speech_lease(window.home) as acquired:
        assert acquired


def test_enrollment_default_input_path_remains_immediate_without_discovery(selected_enrollment, fake_scan):
    window = selected_enrollment
    save_settings({"voice_input_target": ""}, window.home, human_confirmed=True)
    window.consent.setChecked(True)
    window.record()
    assert len(fake_scan) == 1
    assert fake_scan[0].launches == [("/usr/bin/pw-record", [
        "--raw", "--format", "s16", "--rate", "16000", "--channels", "1", "-"])]
    assert window.phase == "capture" and window.capture_timer.isActive()
    assert not window.input_check_timer.isActive()
