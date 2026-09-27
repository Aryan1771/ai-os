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
