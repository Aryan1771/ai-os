"""Synthetic PCM verifies endpointing without opening a real microphone."""

from collections import deque
import math
from types import SimpleNamespace
import wave

import numpy as np
import pytest

from ai_os.services import listener as listener_module
from ai_os.services import voice_input
from ai_os.services.listener import AlwaysListeningService

RATE = 16_000
SAMPLES = 1_280
FRAME_BYTES = SAMPLES * 2
VOICE = (2_000).to_bytes(2, "little", signed=True) * SAMPLES
QUIET = b"\x00" * FRAME_BYTES


def capture(tmp_path, monkeypatch, frames, **settings):
    recorded = []

    def transcribe(path):
        with wave.open(str(path), "rb") as audio:
            recorded.append(np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16))
        return SimpleNamespace(ok=True, text="A complete synthetic utterance")

    transcriber = SimpleNamespace(transcribe_file=transcribe)
    service = AlwaysListeningService(
        run_dir=tmp_path, transcriber=transcriber,
        on_transcript=lambda _: None, **settings,
    )
    service._process = SimpleNamespace(stdout=object())
    remaining = deque(frames)
    elapsed = [0.0]
    reads = []

    def read(size):
        reads.append(size)
        frame = remaining.popleft() if remaining else QUIET
        elapsed[0] += size / (2 * RATE)
        return frame[:size]

    monkeypatch.setattr(service, "_read_audio", read)
    monkeypatch.setattr(listener_module.time, "monotonic", lambda: elapsed[0])
    result = service._capture_and_transcribe(VOICE, FRAME_BYTES)
    return service, result, recorded, reads


def test_full_sentence_survives_old_eight_second_bound_and_waits_five_seconds(tmp_path, monkeypatch):
    service, result, recorded, reads = capture(
        tmp_path, monkeypatch, [VOICE] * 150 + [QUIET] * 64,
        command_seconds=8,
    )
    assert result == "A complete synthetic utterance"
    assert service.silence_seconds == 5
    assert np.count_nonzero(recorded[0]) == 151 * SAMPLES
    quiet_frames = math.ceil(5 * RATE / SAMPLES)
    assert len(reads) == 150 + quiet_frames
    assert len(recorded[0]) == 151 * SAMPLES + RATE // 5
    assert not list(tmp_path.glob("*.wav"))


def test_speech_resets_contiguous_silence_deadline(tmp_path, monkeypatch):
    _, _, recorded, reads = capture(
        tmp_path, monkeypatch, [QUIET] * 62 + [VOICE] + [QUIET] * 64,
    )
    assert np.count_nonzero(recorded[0]) == 2 * SAMPLES
    assert len(reads) == 62 + 1 + 63


def test_ongoing_speech_at_hard_bound_does_not_submit_a_partial_request(tmp_path, monkeypatch):
    from ai_os.services.voice_errors import VoicePipelineError

    with pytest.raises(VoicePipelineError, match="No request was submitted") as error:
        capture(tmp_path, monkeypatch, [VOICE] * 1500, max_utterance_seconds=12)
    assert error.value.code == "utterance_too_long"
    assert not list(tmp_path.glob("*.wav"))


def test_complete_silence_endpoint_at_hard_bound_is_accepted(tmp_path, monkeypatch):
    # Two seconds of silence end exactly at the ten-second PCM bound.
    _, _, recorded, _ = capture(
        tmp_path, monkeypatch, [VOICE] * 99 + [QUIET] * 25,
        silence_seconds=2, max_utterance_seconds=10,
    )
    assert len(recorded[0]) == 8 * RATE + RATE // 5


@pytest.mark.parametrize("silence,maximum,expected_silence,expected_maximum", [
    (0, 1, 1, 10), (5, 120, 5, 120), (50, 500, 10, 120),
])
def test_endpoint_bounds_are_clamped(tmp_path, silence, maximum, expected_silence, expected_maximum):
    service = AlwaysListeningService(
        run_dir=tmp_path, transcriber=SimpleNamespace(), on_transcript=lambda _: None,
        silence_seconds=silence, max_utterance_seconds=maximum,
    )
    assert service.silence_seconds == expected_silence
    assert service.max_utterance_seconds == expected_maximum


def test_playback_starting_during_capture_is_not_transcribed(tmp_path, monkeypatch):
    active = [False]
    service = AlwaysListeningService(
        run_dir=tmp_path,
        transcriber=SimpleNamespace(transcribe_file=lambda _: pytest.fail("Playback must not become a command")),
        on_transcript=lambda _: pytest.fail("Playback was submitted"),
        playback_active=lambda: active[0],
    )
    service._process = SimpleNamespace(stdout=object())

    def read(_size):
        active[0] = True
        return VOICE

    monkeypatch.setattr(service, "_read_audio", read)
    assert service._capture_and_transcribe(VOICE, FRAME_BYTES) == ""
    assert not list(tmp_path.glob("*.wav"))


def test_cancellation_does_not_transcribe_or_leave_temporary_audio(tmp_path, monkeypatch):
    transcriptions = []
    service = AlwaysListeningService(
        run_dir=tmp_path,
        transcriber=SimpleNamespace(transcribe_file=lambda path: transcriptions.append(path)),
        on_transcript=lambda _: None,
    )
    service._process = SimpleNamespace(stdout=object())

    def cancel(size):
        service._stop.set()
        return QUIET[:size]

    monkeypatch.setattr(service, "_read_audio", cancel)
    assert service._capture_and_transcribe(VOICE, FRAME_BYTES) == ""
    assert not transcriptions
    assert not list(tmp_path.glob("*.wav"))


def test_synchronous_reply_tail_cannot_trigger_a_second_request(tmp_path, monkeypatch):
    elapsed = [0.0]
    transcripts = []
    service = AlwaysListeningService(
        run_dir=tmp_path, transcriber=SimpleNamespace(), require_wake_word=False,
        on_transcript=lambda text: (transcripts.append(text), elapsed.__setitem__(0, elapsed[0] + 1)),
    )
    frames = deque([VOICE] * 3 + [VOICE] * 3 + [QUIET] * 7 + [VOICE] * 3)
    captures = []

    def read(size):
        elapsed[0] += SAMPLES / RATE
        if not frames:
            service._stop.set()
            return QUIET
        return frames.popleft()

    def transcribe(preroll, size):
        captures.append(preroll)
        return "A real user utterance"

    monkeypatch.setattr(service, "availability", lambda: (True, "synthetic"))
    monkeypatch.setattr(service, "_read_audio", read)
    monkeypatch.setattr(service, "_capture_and_transcribe", transcribe)
    monkeypatch.setattr(service, "_discard_backlog", lambda: None)
    monkeypatch.setattr(listener_module.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(listener_module.subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(stdout=object(), poll=lambda: 0))
    service.run_forever()
    # The three speech frames immediately following synchronous playback are
    # suppressed; a later user utterance still works after the tail expires.
    assert len(transcripts) == len(captures) == 2


@pytest.mark.parametrize("transcription_fails", [False, True])
def test_one_shot_passes_endpoint_preferences_and_always_stops(tmp_path, monkeypatch, transcription_fails):
    settings = []
    stopped = []

    class SyntheticListener:
        def __init__(self, **kwargs):
            settings.append(kwargs)

        def _read_audio(self, size):
            return VOICE[:size]

        def has_speech(self, audio):
            return True

        def _capture_and_transcribe(self, audio, chunk_bytes):
            assert len(audio) == 3 * FRAME_BYTES
            if transcription_fails:
                raise RuntimeError("Synthetic transcription failure")
            return "Synthetic completed sentence"

        def stop(self):
            stopped.append(True)

    class SyntheticTranscriber:
        def __init__(self, *args, **kwargs):
            pass

        def availability(self):
            return True, "ready"

    monkeypatch.setattr(voice_input, "AlwaysListeningService", SyntheticListener)
    monkeypatch.setattr(voice_input, "WhisperCppTranscriber", SyntheticTranscriber)
    monkeypatch.setattr(voice_input.subprocess, "Popen", lambda *args, **kwargs: object())
    monkeypatch.setattr(voice_input, "publish_state", lambda *args, **kwargs: None)
    config = SimpleNamespace(
        home=tmp_path, whisper_cli="whisper-cli", whisper_model=tmp_path / "model.bin",
        whisper_language="en", voice_command_seconds=8,
        voice_silence_seconds=5, voice_max_utterance_seconds=120,
    )
    if transcription_fails:
        with pytest.raises(RuntimeError, match="Synthetic transcription failure"):
            voice_input.capture_once(config)
    else:
        assert voice_input.capture_once(config) == "Synthetic completed sentence"
    assert settings[0]["silence_seconds"] == 5
    assert settings[0]["max_utterance_seconds"] == 120
    assert settings[0]["command_seconds"] == 8
    assert stopped == [True]
