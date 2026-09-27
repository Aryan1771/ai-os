import subprocess

import pytest

from ai_os.services.stt import WhisperCppTranscriber
from ai_os.speech_queue import SpeechQueue


def test_whisper_passes_language_without_translation(tmp_path, monkeypatch):
    model, audio = tmp_path / "model.bin", tmp_path / "sample.wav"
    model.touch()
    audio.touch()
    monkeypatch.setattr("ai_os.services.stt.shutil.which", lambda name: name)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "नमस्ते", "")

    monkeypatch.setattr("ai_os.services.stt.subprocess.run", run)
    result = WhisperCppTranscriber("whisper-cli", model, language="hi").transcribe_file(audio)
    assert result.text == "नमस्ते"
    assert calls[0][-2:] == ["-l", "hi"] and "-tr" not in calls[0]
    assert not WhisperCppTranscriber(
        "whisper-cli", tmp_path / "base.en.bin", language="hi"
    ).availability()[0]
    with pytest.raises(ValueError):
        WhisperCppTranscriber("whisper-cli", model, language="--command")


def test_hindi_requires_explicit_voice_and_splits_danda(tmp_path):
    english = tmp_path / "en.onnx"
    english.touch()
    speech = SpeechQueue(english)
    with pytest.raises(RuntimeError, match="language"):
        speech.speak_text("नमस्ते")
    assert list(speech.sentence_chunks("नमस्ते। Hello. Goodbye!")) == ["नमस्ते।", "Hello.", "Goodbye!"]
