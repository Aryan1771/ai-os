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
