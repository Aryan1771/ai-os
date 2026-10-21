"""Fake clocks/PCM/processes verify timing without microphone, models or speech."""
from __future__ import annotations

import json
import subprocess
import sys
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication

from ai_os import voice_diagnostics as check
from ai_os import voice_timings
from ai_os.services import listener as listener_module
from ai_os.services import voice_input
from ai_os.services.stt import STT_ERRORS, TranscriptionResult
from ai_os.services.voice_errors import VoicePipelineError
from ai_os.speaker_filter import MESSAGES
from ai_os.speech_queue import SpeechQueue

FRAME_SAMPLES = 1280
VOICE = (2000).to_bytes(2, "little", signed=True) * FRAME_SAMPLES
QUIET = b"\0" * (FRAME_SAMPLES * 2)


class Clock:
    now = 100.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    monkeypatch.setattr(voice_timings.time, "monotonic", value.monotonic)
    return value


@pytest.fixture(autouse=True)
def forbid_live_operations(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("An actual audio/model/network process was attempted")

    monkeypatch.setattr(voice_input.subprocess, "Popen", forbidden)
    monkeypatch.setattr(voice_input.subprocess, "run", forbidden)
    monkeypatch.setattr(check.requests, "Session", forbidden)


@pytest.mark.parametrize("value", [
    True, False, -1, None, "SYNTHETIC_PRIVATE_TEXT", float("nan"), float("inf"),
    float("-inf"), voice_timings.MAX_TIMING_SECONDS + 1, 10**500, [], {},
])
def test_public_timings_drop_invalid_values_without_exposing_private_fields(value):
    metrics = {"stt_seconds": value, "synthesis_seconds": .123456,
               "SYNTHETIC_PRIVATE_PATH": "SYNTHETIC_PRIVATE_TRANSCRIPT"}
    assert voice_timings.public_timings(metrics) == {"synthesis_seconds": .123}
    assert "PRIVATE" not in json.dumps(voice_timings.public_timings(metrics), allow_nan=False)


def test_optional_collector_is_bounded_and_accumulation_ignores_invalid_previous_values(clock):
    voice_timings.record_timing(None, "stt_seconds", 1)
    voice_timings.elapsed_timing(None, "stt_seconds", clock.now)
    assert voice_timings.public_timings([]) == {}
    metrics = {"synthesis_seconds": "SYNTHETIC_PRIVATE_TEXT"}
    voice_timings.record_timing(metrics, "synthesis_seconds", 1.5, accumulate=True)
    voice_timings.record_timing(metrics, "synthesis_seconds", .25, accumulate=True)
    voice_timings.record_timing(metrics, "synthesis_seconds", float("inf"), accumulate=True)
    voice_timings.record_timing(metrics, "SYNTHETIC_UNKNOWN_FIELD", 1)
    assert metrics == {"synthesis_seconds": 1.75}
    voice_timings.elapsed_timing(metrics, "stt_seconds", clock.now + 1)
    assert "stt_seconds" not in metrics


@dataclass
class VoiceConfig:
    home: Path
    whisper_cli: str = "synthetic-whisper"
    whisper_model: Path = Path("synthetic-model.bin")
    whisper_language: str = "en"
    reply_language_mode: str = "selected"
    voice_command_seconds: int = 8
    voice_silence_seconds: int = 5
    voice_max_utterance_seconds: int = 20
    ai_provider: str = "ollama"
    ollama_url: str = "http://127.0.0.1:11434"
    speech_enabled: bool = True
    piper_model: Path = Path("synthetic-en.onnx")
    piper_hindi_model: Path = Path("synthetic-hi.onnx")
    piper_length_scale: float = 1.0


def synthetic_capture(tmp_path, monkeypatch, clock, *, rejection=None, speaker_allowed=True, quiet_only=False):
    config = VoiceConfig(tmp_path)
    frames = deque([QUIET] * 110 if quiet_only else [QUIET] * 4 + [VOICE] * 23 + [QUIET] * 63)
    observed = {"processes": [], "wav": [], "filters": [], "stopped": []}

    class Transcriber:
        def __init__(self, *_args, **_kwargs):
            pass

        def availability(self):
            return True, "synthetic ready"

        def transcribe_file(self, path):
            with wave.open(str(path), "rb") as audio:
                observed["wav"].append((audio.getnframes(), audio.getframerate()))
            clock.advance(.75)
            if rejection:
                return TranscriptionResult(False, "", STT_ERRORS[rejection], error_code=rejection)
            return TranscriptionResult(True, "A complete synthetic utterance.", detected_language="en")

    class Recorder:
        stdout = object()
        ended = False

        def poll(self):
            return 0 if self.ended else None

        def terminate(self):
            self.ended = True
            observed["stopped"].append(True)

        def wait(self, timeout):
            return 0

    def record(argv, **kwargs):
        observed["processes"].append((argv, kwargs))
        return Recorder()

    def read(_service, size):
        clock.advance(size / (2 * 16000))
        assert frames, "The synthetic recorder unexpectedly needed more audio"
        return frames.popleft()[:size]

    def filter_audio(path, home):
        assert home == tmp_path and path.is_file()
        observed["filters"].append(True)
        clock.advance(.125)
        return speaker_allowed, MESSAGES["speaker_matched" if speaker_allowed else "speaker_rejected"]

    monkeypatch.setenv("AI_OS_VOICE_TMP", str(tmp_path))
    monkeypatch.setattr(voice_input, "WhisperCppTranscriber", Transcriber)
    monkeypatch.setattr(listener_module.AlwaysListeningService, "_read_audio", read)
    monkeypatch.setattr(voice_input.subprocess, "Popen", record)
    monkeypatch.setattr("ai_os.speaker_filter.filter_utterance", filter_audio)
    monkeypatch.setattr(voice_input, "publish_state", lambda *_args, **_kwargs: None)
    return config, observed


def test_capture_separates_detection_pcm_pause_filter_and_stt_without_clipping(tmp_path, monkeypatch, clock):
    config, observed = synthetic_capture(tmp_path, monkeypatch, clock)
    metrics = {}
    result = voice_input.capture_once(config, return_result=True, metrics=metrics)
    assert result.text == "A complete synthetic utterance." and result.detected_language == "en"
    assert metrics == {"speech_detection_wait_seconds": .56, "capture_seconds": 6.64,
                       "captured_audio_seconds": 7.04, "ending_silence_audio_seconds": 5.04,
                       "speaker_filter_seconds": .125, "stt_seconds": .75}
    assert observed["wav"] == [(35200, 16000)]  # All words plus the existing 200ms tail.
    assert len(observed["processes"]) == len(observed["stopped"]) == 1
    argv, options = observed["processes"][0]
    assert argv == ["/usr/bin/pw-record", "--raw", "--format", "s16", "--rate", "16000", "--channels", "1", "-"]
    assert options["shell"] is False
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kind", ["speaker", "stt", "no_speech"])
def test_rejected_capture_keeps_only_reached_stage_times_and_removes_audio(tmp_path, monkeypatch, clock, kind):
    config, observed = synthetic_capture(tmp_path, monkeypatch, clock,
                                         rejection="transcription_timeout" if kind == "stt" else None,
                                         speaker_allowed=kind != "speaker", quiet_only=kind == "no_speech")
    metrics = {}
    with pytest.raises(RuntimeError):
        voice_input.capture_once(config, return_result=True, metrics=metrics)
    assert "speech_detection_wait_seconds" in metrics
    if kind == "no_speech":
        assert set(metrics) == {"speech_detection_wait_seconds"}
        assert 8 <= metrics["speech_detection_wait_seconds"] <= 8.08
        assert not observed["filters"]
    else:
        assert metrics["speaker_filter_seconds"] == .125
        assert metrics.get("stt_seconds") == (.75 if kind == "stt" else None)
    assert len(observed["wav"]) == (1 if kind == "stt" else 0)
    assert observed["stopped"] == [True] and not list(tmp_path.iterdir())


def test_capture_without_collector_preserves_result_and_audio_path_cleanup(tmp_path, monkeypatch, clock):
    config, observed = synthetic_capture(tmp_path, monkeypatch, clock)
    assert voice_input.capture_once(config) == "A complete synthetic utterance."
    assert len(observed["processes"]) == 1 and not list(tmp_path.iterdir())


def synthetic_speech(tmp_path, monkeypatch, clock, *, failure=None):
    model = tmp_path / "synthetic.onnx"
    model.touch()
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert not kwargs.get("shell", False)
        if "--output_file" in argv:
            clock.advance(1.25)
            if failure == "synthesis":
                raise subprocess.TimeoutExpired(argv, 60, output=b"SYNTHETIC_PRIVATE_OUTPUT")
            with wave.open(argv[argv.index("--output_file") + 1], "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(22050)
                audio.writeframes(b"\0\0" * 22050)
        else:
            clock.advance(2.5)
            if failure == "playback":
                raise subprocess.CalledProcessError(1, argv, stderr=b"SYNTHETIC_PRIVATE_OUTPUT")

    monkeypatch.setenv("AI_OS_VOICE_TMP", str(tmp_path))
    monkeypatch.setattr("ai_os.speech_queue.shutil.which", lambda name: "/synthetic/" + name)
    monkeypatch.setattr("ai_os.speech_queue.subprocess.run", run)
    return SpeechQueue(model), calls


def test_synthesis_and_playback_measurements_are_distinct_and_accumulate_sentences(tmp_path, monkeypatch, clock):
    speech, calls = synthetic_speech(tmp_path, monkeypatch, clock)
    metrics = {}
    speech.speak_text("First synthetic sentence.", metrics=metrics)
    assert metrics == {"synthesis_seconds": 1.25, "playback_seconds": 2.5}
    speech.speak_text("Second synthetic sentence.", metrics=metrics)
    assert metrics == {"synthesis_seconds": 2.5, "playback_seconds": 5.0}
    assert len(calls) == 4
    assert all(not path.name.startswith("regenos-speech-") for path in tmp_path.iterdir())


@pytest.mark.parametrize("failure", ["synthesis", "playback", "stopped"])
def test_failed_or_stopped_speech_omits_unreached_playback_and_cleans_wav(tmp_path, monkeypatch, clock, failure):
    speech, calls = synthetic_speech(tmp_path, monkeypatch, clock, failure=failure)
    metrics = {}
    if failure == "stopped":
        speech.stop()
        speech.speak_text("Synthetic cancelled playback.", metrics=metrics)
    else:
        with pytest.raises(subprocess.SubprocessError):
            speech.speak_text("Synthetic failed playback.", metrics=metrics)
    assert metrics["synthesis_seconds"] == 1.25
    assert metrics.get("playback_seconds") == (2.5 if failure == "playback" else None)
    assert len(calls) == (2 if failure == "playback" else 1)
    assert not any(path.name.startswith("regenos-speech-") for path in tmp_path.iterdir())


def diagnostic_fakes(tmp_path, monkeypatch, clock, *, fail_capture=False):
    config = VoiceConfig(tmp_path)
    observed = {"capture": [], "model": [], "speech": []}
    monkeypatch.setattr(check, "load_config", lambda _home: config)
    monkeypatch.setattr(check, "load_raw_config", lambda _home: {
        "always_listening_enabled": False, "speech_enabled": True,
    })
    monkeypatch.setattr("ai_os.companion_state.publish_state", lambda *_args, **_kwargs: None)

    def capture(config, *, return_result=False, metrics=None):
        observed["capture"].append(config)
        metrics.update({"stt_seconds": .75, "speaker_filter_seconds": .125,
                        "ending_silence_audio_seconds": 5.04, "captured_audio_seconds": 7.04,
                        "SYNTHETIC_PRIVATE_KEY": "SYNTHETIC_PRIVATE_TEXT"})
        clock.advance(8)
        if fail_capture:
            raise VoicePipelineError("transcription_timeout", "SYNTHETIC_PRIVATE_EXCEPTION")
        return TranscriptionResult(True, "Synthetic current utterance.")

    def reply(text, language, home, *, metrics=None):
        observed["model"].append(text)
        metrics.update({"load_seconds": .5, "prompt_eval_seconds": .2, "eval_seconds": .3,
                        "SYNTHETIC_PRIVATE_KEY": "SYNTHETIC_PRIVATE_TEXT"})
        clock.advance(1.2)
        return "Synthetic relevant reply."

    class Speech:
        def __init__(self, *_args, **_kwargs):
            pass

        def speak_text(self, text, *, metrics=None):
            observed["speech"].append(text)
            metrics.update({"synthesis_seconds": .7, "playback_seconds": 1.3})
            clock.advance(2)

    monkeypatch.setattr(voice_input, "capture_once", capture)
    monkeypatch.setattr(check, "local_reply", reply)
    monkeypatch.setattr("ai_os.speech_queue.SpeechQueue", Speech)
    return observed


def test_guided_result_preserves_combined_model_times_and_replaces_stale_collector(tmp_path, monkeypatch, clock):
    observed = diagnostic_fakes(tmp_path, monkeypatch, clock)
    metrics = {"playback_seconds": 999, "SYNTHETIC_PREVIOUS_PRIVATE_FIELD": "old"}
    result = check.check_voice("record", "en", home=tmp_path, human_confirmed=True, metrics=metrics)
    assert result["transcript"] == "Synthetic current utterance." and result["reply"] == "Synthetic relevant reply."
    timings = result["timings"]
    assert timings["capture_and_stt_seconds"] == 8 and timings["model_seconds"] == 1.2
    assert timings["synthesis_and_playback_seconds"] == 2 and timings["total_seconds"] == 11.2
    assert [timings[key] for key in ("model_load_seconds", "model_prompt_eval_seconds", "model_eval_seconds")] == [.5, .2, .3]
    assert timings["stt_seconds"] == .75 and timings["playback_seconds"] == 1.3
    assert "PRIVATE" not in json.dumps(timings) and "SYNTHETIC_PREVIOUS_PRIVATE_FIELD" not in metrics
    assert metrics == timings
    assert len(observed["capture"]) == len(observed["model"]) == len(observed["speech"]) == 1
    assert not (tmp_path / "config.json").exists() and not (tmp_path / "data").exists()


def test_guided_failure_retains_reached_numeric_times_without_model_or_speech(tmp_path, monkeypatch, clock):
    observed = diagnostic_fakes(tmp_path, monkeypatch, clock, fail_capture=True)
    metrics = {}
    with pytest.raises(VoicePipelineError) as failure:
        check.check_voice("record", "en", home=tmp_path, human_confirmed=True, metrics=metrics)
    assert failure.value.code == "transcription_timeout" and "PRIVATE" not in str(failure.value)
    timings = voice_timings.public_timings(metrics)
    assert timings["stt_seconds"] == .75 and timings["total_seconds"] == 8
    assert "model_seconds" not in timings and "playback_seconds" not in timings
    assert observed["model"] == observed["speech"] == []
    assert metrics == timings and "PRIVATE" not in json.dumps(metrics)


def test_metrics_never_bypass_explicit_per_call_consent_or_mutate_caller_on_denial(tmp_path, monkeypatch, clock):
    observed = diagnostic_fakes(tmp_path, monkeypatch, clock)
    metrics = {"playback_seconds": .5}
    with pytest.raises(PermissionError):
        check.check_voice("record", "en", home=tmp_path, metrics=metrics)
    assert metrics == {"playback_seconds": .5}
    assert observed["capture"] == observed["model"] == observed["speech"] == []


def test_playback_only_has_no_capture_or_model_metrics(tmp_path, monkeypatch, clock):
    observed = diagnostic_fakes(tmp_path, monkeypatch, clock)
    result = check.check_voice("play", "hi", home=tmp_path, human_confirmed=True)
    assert observed["capture"] == observed["model"] == []
    assert set(result["timings"]) == {"synthesis_seconds", "playback_seconds", "synthesis_and_playback_seconds", "total_seconds"}


def test_worker_failure_json_contains_only_public_error_and_allowed_numbers(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("AI_OS_HOME", str(tmp_path))
    def fail(*_args, metrics=None, **_kwargs):
        metrics.update({"stt_seconds": 2.123456, "model_seconds": float("nan"),
                        "SYNTHETIC_PRIVATE_PATH": "SYNTHETIC_PRIVATE_TRANSCRIPT"})
        raise VoicePipelineError("transcription_timeout", "SYNTHETIC_PRIVATE_EXCEPTION")

    monkeypatch.setattr(check, "check_voice", fail)
    monkeypatch.setattr(check.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(sys, "argv", ["voice_diagnostics", "--worker", "record", "--confirmed"])
    assert check.main() == 1
    raw = capsys.readouterr().out
    result = json.loads(raw)
    assert result["code"] == "transcription_timeout" and result["timings"] == {"stt_seconds": 2.123}
    assert "PRIVATE" not in raw and "NaN" not in raw


def test_failed_native_result_shows_reached_times_without_private_transcript(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication(["voice-stage-timing-test"])
    monkeypatch.setattr(check, "load_raw_config", lambda _home: {"reply_language_mode": "selected", "whisper_language": "en"})
    dialog = check.create_dialog(tmp_path)
    dialog.process = type("FakeProcess", (), {"readAllStandardOutput": lambda _self: b""})()
    monkeypatch.setattr(dialog, "release", lambda: setattr(dialog, "process", None))
    dialog.output.extend(json.dumps({
        "ok": False, "message": "Transcription timed out.", "transcript": "SYNTHETIC_PRIVATE_TRANSCRIPT",
        "timings": {"stt_seconds": 2, "SYNTHETIC_PRIVATE_PATH": "private", "playback_seconds": True},
    }).encode())
    dialog.finished(1, QProcess.ExitStatus.NormalExit)
    details = dialog.details.toPlainText()
    assert "stt_seconds" in details and "PRIVATE" not in details and "playback_seconds" not in details
    assert dialog.status.text() == "Transcription timed out."
    dialog.close()
    app.processEvents()
