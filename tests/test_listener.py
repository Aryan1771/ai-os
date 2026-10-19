import subprocess
from unittest.mock import Mock

from ai_os.services.listener import AlwaysListeningService
from ai_os.services.stt import WhisperCppTranscriber


def test_listener_fails_closed_when_recorder_is_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("ai_os.services.listener.shutil.which", lambda _name: None)
    listener = AlwaysListeningService(
        run_dir=tmp_path,
        transcriber=WhisperCppTranscriber("whisper-cli", tmp_path / "model.bin"),
        on_transcript=lambda _text: None,
    )

    assert listener.availability() == (False, "pw-record is unavailable; install PipeWire utilities.")


def test_listener_stop_reaps_recorder_and_escalates_on_timeout(tmp_path):
    listener = AlwaysListeningService(
        run_dir=tmp_path,
        transcriber=WhisperCppTranscriber("whisper-cli", tmp_path / "model.bin"),
        on_transcript=lambda _text: None,
    )
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("pw-record", 2), 0]
    listener._process = process

    listener.stop()

    assert listener._stop.is_set()
    process.terminate.assert_called_once_with()
    process.kill.assert_called_once_with()
    assert process.wait.call_count == 2
    process.wait.assert_called_with(timeout=2)

    process.poll.return_value = 0
    listener.stop()
    process.terminate.assert_called_once_with()


def test_conversation_mode_skips_wake_model_but_requires_transcriber(tmp_path, monkeypatch):
    transcriber = Mock()
    transcriber.availability.return_value = (True, "ready")
    monkeypatch.setattr("ai_os.services.listener.shutil.which", lambda _name: "/usr/bin/pw-record")
    listener = AlwaysListeningService(
        run_dir=tmp_path, transcriber=transcriber, on_transcript=lambda _text: None,
        require_wake_word=False,
    )
    assert listener.availability() == (True, "conversation listening")
    assert not listener.has_speech(b"\x00" * 320)
    assert listener.has_speech((2000).to_bytes(2, "little", signed=True) * 160)


def test_transcription_removes_temporary_audio_even_after_failure(tmp_path, monkeypatch):
    transcriber = Mock()
    transcriber.transcribe_file.return_value = Mock(ok=False)
    listener = AlwaysListeningService(run_dir=tmp_path, transcriber=transcriber,
                                      on_transcript=lambda _text: None)
    listener._process = Mock()
    monkeypatch.setattr(listener, "_read_audio", lambda size: b"\x00" * size)
    import pytest
    with pytest.raises(RuntimeError, match="Transcription failed"):
        listener._capture_and_transcribe(b"\x00" * 2560, 2560)
    assert not list(tmp_path.glob("*.wav"))


def test_stalled_read_can_be_cancelled_without_waiting_for_audio(tmp_path):
    import os
    import threading
    reader, writer = os.pipe()
    listener = AlwaysListeningService(run_dir=tmp_path, transcriber=Mock(), on_transcript=lambda _: None)
    results = []
    with os.fdopen(reader, "rb", buffering=0) as stream:
        listener._process = Mock(stdout=stream)
        thread = threading.Thread(target=lambda: results.append(listener._read_audio(2560)))
        thread.start()
        listener._stop.set()
        thread.join(timeout=1)
        os.close(writer)
        assert not thread.is_alive() and results == [b""]
