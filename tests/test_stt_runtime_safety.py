"""Synthetic Whisper process/metadata failures; no real audio or model inference."""
import json
from pathlib import Path
import subprocess

import pytest

from ai_os.services import stt


@pytest.fixture
def transcriber(tmp_path, monkeypatch):
    model, audio = tmp_path / "synthetic.bin", tmp_path / "synthetic.wav"
    model.touch()
    audio.touch()
    monkeypatch.setattr(stt.shutil, "which", lambda _: "/usr/bin/whisper-cli")
    return stt.WhisperCppTranscriber("whisper-cli", model, detect_language=True), audio


def metadata(argv, text, language="hi"):
    target = Path(argv[argv.index("-of") + 1] + ".json")
    target.write_text(json.dumps({"model": {"multilingual": True},
                                  "result": {"language": language},
                                  "transcription": [{"text": text}]}))
    return target


@pytest.mark.parametrize("kind,code", [("timeout", "transcription_timeout"),
                                      ("exit", "transcription_failed"),
                                      ("start", "transcription_failed")])
def test_process_failures_never_echo_command_or_stderr(transcriber, monkeypatch, kind, code):
    engine, audio = transcriber
    private = "private transcript and filesystem path"

    def run(argv, **kwargs):
        assert kwargs["shell"] is False and kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["timeout"] <= 180
        if kind == "timeout":
            raise subprocess.TimeoutExpired([private], 120, stderr=private)
        if kind == "start":
            raise OSError(private)
        return subprocess.CompletedProcess(argv, 1, private, private)

    monkeypatch.setattr(stt.subprocess, "run", run)
    result = engine.transcribe_file(audio)
    assert not result.ok and not result.text
    assert result.error_code == code
    assert private not in result.error
    assert engine.last_duration_sec is None


def test_temporary_storage_failure_is_public_result_and_never_launches(transcriber, monkeypatch):
    engine, audio = transcriber

    def fail(**kwargs):
        raise PermissionError("private temporary directory")

    monkeypatch.setattr(stt.tempfile, "TemporaryDirectory", fail)
    monkeypatch.setattr(stt.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not launch"))
    result = engine.transcribe_file(audio)
    assert not result.ok and result.error_code == "transcription_storage"
    assert "private temporary directory" not in result.error


@pytest.mark.parametrize("text,success", [("یہ ایک جملہ ہے", False), ("नमस्ते, आज कैसा दिन है?", True),
                                         ("mera naam kya hai", True)])
def test_hindi_script_conflicts_fail_closed_without_guessing(transcriber, monkeypatch, text, success):
    engine, audio = transcriber
    outputs = []

    def run(argv, **kwargs):
        outputs.append(metadata(argv, text))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(stt.subprocess, "run", run)
    result = engine.transcribe_file(audio)
    assert result.ok is success
    assert result.error_code == ("" if success else "transcription_script_mismatch")
    assert result.text == (text if success else "")
    assert not outputs[0].exists() and not outputs[0].parent.exists()


def test_metadata_lives_in_supervised_private_directory(transcriber, tmp_path, monkeypatch):
    engine, audio = transcriber
    directory = tmp_path / "voice-worker"
    directory.mkdir(mode=0o700)
    monkeypatch.setenv("AI_OS_VOICE_TMP", str(directory))

    def run(argv, **kwargs):
        output = metadata(argv, "A fresh question", language="en")
        assert output.parent.parent == directory
        assert output.parent.stat().st_mode & 0o777 == 0o700
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(stt.subprocess, "run", run)
    assert engine.transcribe_file(audio).ok
    assert list(directory.iterdir()) == []


def test_failed_retry_does_not_keep_previous_latency(transcriber, monkeypatch):
    engine, audio = transcriber

    def run(argv, **kwargs):
        metadata(argv, "A synthetic question", language="en")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(stt.subprocess, "run", run)
    assert engine.transcribe_file(audio).ok and engine.last_duration_sec is not None
    audio.unlink()
    result = engine.transcribe_file(audio)
    assert result.error_code == "audio_missing" and engine.last_duration_sec is None


@pytest.mark.parametrize("stderr, expected", [
    ("ggml_cuda_init: found 1 CUDA devices\n", "unknown"),
    ("whisper_backend_init_gpu: using CUDA0 backend\n", "unknown"),
    ("whisper_backend_init_gpu: using CUDA0 backend\nwhisper_model_load: CUDA0 total size = 149.00 MB\n", "cuda"),
    ("whisper_backend_init_gpu: using CUDA0 backend\nwhisper_model_load: CUDA0 total size = 149.00 MB\nwhisper_backend_init_gpu: failed to initialize CUDA0 backend\n", "unknown"),
    ("whisper_backend_init_gpu: no GPU found\n", "cpu"),
    ("A private transcript says using CUDA0 backend\n", "unknown"),
])
def test_backend_evidence_requires_known_selection_and_device_model_buffer(stderr, expected):
    assert stt.backend_selection(stderr) == expected


def test_backend_evidence_resets_before_failed_retry(transcriber, monkeypatch):
    engine, audio = transcriber

    def run(argv, **kwargs):
        metadata(argv, "A synthetic question", language="en")
        return subprocess.CompletedProcess(argv, 0, "", "whisper_backend_init_gpu: no GPU found\n")

    monkeypatch.setattr(stt.subprocess, "run", run)
    assert engine.transcribe_file(audio).ok and engine.last_backend == "cpu"
    audio.unlink()
    assert not engine.transcribe_file(audio).ok and engine.last_backend == "unknown"
