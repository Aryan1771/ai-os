"""Speaker-filter integration with synthetic local PCM; no device or model download."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import wave

import pytest

from ai_os import speaker_identity
from ai_os.services.listener import AlwaysListeningService
from ai_os.services.stt import TranscriptionResult
from ai_os.settings_store import save_settings
from ai_os.speaker_filter import filter_utterance

SAMPLES = 1280
VOICE = (2000).to_bytes(2, "little", signed=True) * SAMPLES
QUIET = b"\x00" * len(VOICE)


def setup(home, *, enabled):
    model = home / "synthetic-speaker.onnx"
    model.write_bytes(b"A synthetic model identity, never loaded as ONNX")
    save_settings({"speaker_recognition_enabled": enabled, "speaker_model": str(model)},
                  home, human_confirmed=True)
    return model


def capture(home, monkeypatch, gate, transcribe):
    phases = []
    service = AlwaysListeningService(
        run_dir=home, transcriber=SimpleNamespace(transcribe_file=transcribe),
        on_transcript=lambda _: pytest.fail("Capture must not dispatch callbacks itself"),
        require_wake_word=False, silence_seconds=1, speaker_filter=gate,
        on_activity=phases.append,
    )
    service._process = SimpleNamespace(stdout=object())
    monkeypatch.setattr(service, "_read_audio", lambda size: QUIET[:size])
    return service, phases


def test_disabled_filter_never_calls_speaker_backend(tmp_path, monkeypatch):
    setup(tmp_path, enabled=False)
    monkeypatch.setattr(speaker_identity, "speaker_allowed", lambda *args:
                        pytest.fail("Disabled filter called the speaker backend"))
    monkeypatch.setattr("ai_os.speaker_filter.subprocess.run", lambda *args, **kwargs:
                        pytest.fail("Disabled filter started a worker"))
    assert filter_utterance(tmp_path / "not-read.wav", tmp_path)[0]
    assert not (tmp_path / "run/speaker-status.json").exists()


@pytest.mark.parametrize("failure", ["missing_profile", "missing_backend"])
def test_missing_profile_or_backend_denies_before_transcription(tmp_path, monkeypatch, capsys, failure):
    model = setup(tmp_path, enabled=True)
    if failure == "missing_backend":
        enrollment = speaker_identity.Enrollment(speaker_identity.model_digest(model))
        embedding = [1.0] + [0.0] * 15
        for _ in range(speaker_identity.ENROLLMENT_SAMPLES):
            enrollment.add(embedding)
        assert enrollment.verify(embedding)
        enrollment.save(tmp_path)
        monkeypatch.setattr(speaker_identity, "backend_available", lambda: False)
    else:
        monkeypatch.setattr(speaker_identity, "encoder_for", lambda *args:
                            pytest.fail("A missing profile must not load a speaker model"))

    # Run worker logic in process for deterministic missing-backend injection,
    # then validate its public response through the real wrapper/listener gate.
    monkeypatch.setattr(sys, "argv", ["speaker_identity", "--check", str(tmp_path / "unused.wav"),
                                      "--home", str(tmp_path)])
    assert speaker_identity.main() == 0
    report = capsys.readouterr().out
    assert json.loads(report) == {"allowed": False, "code": "speaker_unavailable"}
    monkeypatch.setattr("ai_os.speaker_filter.subprocess.run", lambda argv, **kwargs:
                        subprocess.CompletedProcess(argv, 0, report, ""))

    service, phases = capture(
        tmp_path, monkeypatch, lambda path: filter_utterance(path, tmp_path),
        lambda path: pytest.fail("An unverified speaker reached Whisper"),
    )
    service.last_transcription_language = "hi"
    assert service._capture_and_transcribe(VOICE * 16, len(VOICE)) == ""
    assert service.last_transcription_language is None
    assert service.last_capture_error.code == "speaker_rejected"
    assert "verification unavailable" in str(service.last_capture_error)
    assert "transcribing" not in phases and not list(tmp_path.glob("*.wav"))
    status = json.loads((tmp_path / "run/speaker-status.json").read_text())
    assert status["matched"] is False
    assert str(tmp_path) not in json.dumps(status) and "embedding" not in json.dumps(status)


def test_rejected_speaker_audio_is_deleted_without_transcribing(tmp_path, monkeypatch):
    observed = []

    def reject(path):
        observed.append(path)
        assert path.is_file()
        with wave.open(str(path), "rb") as audio:
            assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
        return False, "Synthetic speaker mismatch"

    service, phases = capture(tmp_path, monkeypatch, reject,
                              lambda _: pytest.fail("Rejected speaker reached Whisper"))
    assert service._capture_and_transcribe(VOICE * 16, len(VOICE)) == ""
    assert service.last_capture_error.code == "speaker_rejected"
    assert str(service.last_capture_error) == "Synthetic speaker mismatch"
    assert observed and all(not path.exists() for path in observed)
    assert "transcribing" not in phases


def test_accepted_speaker_is_transcribed_after_filter_and_preserves_language(tmp_path, monkeypatch):
    events, paths = [], []

    def approve(path):
        events.append("gate")
        paths.append(path)
        assert path.is_file()
        return True, "Synthetic local match; no privileges granted"

    def transcribe(path):
        events.append("transcribe")
        assert path == paths[0] and path.is_file()
        return TranscriptionResult(True, "mera sawal", detected_language="hi")

    service, phases = capture(tmp_path, monkeypatch, approve, transcribe)
    assert service._capture_and_transcribe(VOICE * 16, len(VOICE)) == "mera sawal"
    assert events == ["gate", "transcribe"]
    assert phases == ["transcribing"] and service.last_transcription_language == "hi"
    assert service.last_capture_error is None
    assert all(not path.exists() for path in paths)


def test_unexpected_filter_exception_is_closed_and_cleans_audio(tmp_path, monkeypatch):
    paths = []

    def broken_filter(path):
        paths.append(path)
        raise OSError("Synthetic filter failure")

    service, _ = capture(tmp_path, monkeypatch, broken_filter,
                         lambda _: pytest.fail("Broken filter reached Whisper"))
    assert service._capture_and_transcribe(VOICE * 16, len(VOICE)) == ""
    assert paths and all(not path.exists() for path in paths)
    assert service.last_transcription_language is None
    assert "verification unavailable" in str(service.last_capture_error)
    assert "Synthetic filter failure" not in str(service.last_capture_error)


def test_wrapper_backend_exception_does_not_expose_private_diagnostics(tmp_path, monkeypatch):
    setup(tmp_path, enabled=True)

    def fail(*args, **kwargs):
        raise RuntimeError("Private transcript, embedding and similarity score")

    monkeypatch.setattr("ai_os.speaker_filter.subprocess.run", fail)
    allowed, message = filter_utterance(Path("synthetic.wav"), tmp_path)
    assert not allowed and "Private transcript" not in message
    status = (tmp_path / "run/speaker-status.json").read_text()
    assert "Private transcript" not in status and json.loads(status)["matched"] is False


@pytest.mark.parametrize("failure", ["timeout", "nonzero", "malformed", "inconsistent", "oversized"])
def test_worker_failure_is_bounded_shell_free_and_closed(tmp_path, monkeypatch, failure):
    setup(tmp_path, enabled=True)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert argv[:4] == [sys.executable, "-m", "ai_os.speaker_identity", "--check"]
        assert argv[-2:] == ["--home", str(tmp_path)]
        assert kwargs["shell"] is False and kwargs["timeout"] == 10
        assert kwargs["stdin"] is subprocess.DEVNULL and kwargs["stderr"] is subprocess.DEVNULL
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, 10, output="private output")
        output = {"nonzero": "private output", "malformed": "not JSON",
                  "inconsistent": '{"allowed":true,"code":"speaker_rejected"}',
                  "oversized": "x" * 2049}[failure]
        return subprocess.CompletedProcess(argv, 1 if failure == "nonzero" else 0, output, "")

    monkeypatch.setattr("ai_os.speaker_filter.subprocess.run", run)
    allowed, message = filter_utterance(tmp_path / "unused.wav", tmp_path)
    assert not allowed and len(calls) == 1
    status = json.loads((tmp_path / "run/speaker-status.json").read_text())
    assert status["code"] == ("speaker_timeout" if failure == "timeout" else "speaker_unavailable")
    assert "private output" not in json.dumps(status) + message


def test_real_check_subprocess_missing_profile_returns_public_json_only(tmp_path):
    setup(tmp_path, enabled=True)
    result = subprocess.run(
        [sys.executable, "-m", "ai_os.speaker_identity", "--check", str(tmp_path / "absent.wav"),
         "--home", str(tmp_path)], capture_output=True, text=True, timeout=10, shell=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"allowed": False, "code": "speaker_unavailable"}
    assert "embedding" not in result.stdout and str(tmp_path) not in result.stdout


def test_successful_check_returns_no_embedding_or_backend_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["speaker_identity", "--check", "synthetic.wav", "--home", str(tmp_path)])
    monkeypatch.setattr(speaker_identity, "speaker_status", lambda home: (True, "Private setup message"))
    monkeypatch.setattr(speaker_identity, "speaker_allowed", lambda path, home:
                        (True, "Private embedding and similarity score"))
    assert speaker_identity.main() == 0
    report = capsys.readouterr().out
    assert json.loads(report) == {"allowed": True, "code": "speaker_matched"}
    setup(tmp_path, enabled=True)
    monkeypatch.setattr("ai_os.speaker_filter.subprocess.run", lambda argv, **kwargs:
                        subprocess.CompletedProcess(argv, 0, report, ""))
    assert filter_utterance(tmp_path / "synthetic.wav", tmp_path) == (True, "Enrolled voice matched.")
    status = (tmp_path / "run/speaker-status.json").read_text()
    assert json.loads(status)["matched"] is True and "Private" not in status


def test_one_shot_surfaces_speaker_rejection_and_reaps_recorder(tmp_path, monkeypatch):
    from ai_os.config import load_config
    from ai_os.services import voice_input
    from ai_os.services.voice_errors import VoicePipelineError
    stopped = []

    class Listener:
        def __init__(self, **kwargs):
            self.last_capture_error = VoicePipelineError("speaker_rejected", "Voice did not pass the enrolled-speaker filter.")

        def _read_audio(self, size):
            return VOICE[:size]

        def has_speech(self, audio):
            return True

        def _capture_and_transcribe(self, first, size):
            return ""

        def stop(self):
            stopped.append(True)

    monkeypatch.setattr(voice_input, "AlwaysListeningService", Listener)
    monkeypatch.setattr(voice_input.WhisperCppTranscriber, "availability", lambda _: (True, "ready"))
    monkeypatch.setattr(voice_input.subprocess, "Popen", lambda *args, **kwargs: object())
    with pytest.raises(VoicePipelineError, match="enrolled-speaker") as error:
        voice_input.capture_once(load_config(tmp_path))
    assert error.value.code == "speaker_rejected" and stopped == [True]
