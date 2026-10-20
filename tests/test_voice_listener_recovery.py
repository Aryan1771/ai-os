"""Recover rejected synthetic utterances without a microphone or real models."""
from __future__ import annotations

import wave
from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest

from ai_os.services import listener as listener_module
from ai_os.services.listener import AlwaysListeningService
from ai_os.services.stt import STT_ERRORS, TranscriptionResult
from ai_os.services.voice_errors import VoicePipelineError, diagnostic

SAMPLES = 1280
VOICE = (2000).to_bytes(2, "little", signed=True) * SAMPLES
WAKE = (3000).to_bytes(2, "little", signed=True) * SAMPLES
QUIET = b"\0" * (SAMPLES * 2)
PAUSE = [QUIET] * 13  # The minimum supported one-second endpoint at 16 kHz.
TAIL = [QUIET] * 8


def listener(tmp_path, monkeypatch, frames, transcribe, *, require_wake_word=False):
    state = SimpleNamespace(clock=0.0, transcripts=[], errors=[], phases=[],
                            starts=[], discarded=[], resets=[], detections=[], events=[])

    def accepted(text):
        state.transcripts.append(text)
        service._stop.set()

    def activity(phase):
        state.phases.append(phase)
        state.events.append(phase)

    service = AlwaysListeningService(
        run_dir=tmp_path, transcriber=SimpleNamespace(transcribe_file=transcribe),
        on_transcript=accepted, require_wake_word=require_wake_word,
        silence_seconds=1, max_utterance_seconds=10,
        on_error=state.errors.append, on_activity=activity,
    )
    remaining = deque(frames)

    def read(size):
        state.clock += size / (2 * 16000)
        if not remaining:
            service._stop.set()
            return QUIET[:size]
        return remaining.popleft()[:size]

    def start(*args, **kwargs):
        state.starts.append((args, kwargs))
        return SimpleNamespace(stdout=object(), poll=lambda: 0)

    def detect(frame):
        state.detections.append(int(frame[0]))
        return frame[0] == 3000

    def reset():
        state.resets.append(True)
        state.events.append("reset")

    def discard():
        state.discarded.append(True)
        state.events.append("discard")

    service.wake_word = SimpleNamespace(detect_frame=detect, reset=reset)
    monkeypatch.setattr(service, "availability", lambda: (True, "synthetic readiness"))
    monkeypatch.setattr(service, "_read_audio", read)
    monkeypatch.setattr(service, "_discard_backlog", discard)
    monkeypatch.setattr(listener_module.time, "monotonic", lambda: state.clock)
    monkeypatch.setattr(listener_module.subprocess, "Popen", start)
    return service, state


@pytest.mark.parametrize("code", [
    "transcription_script_mismatch", "transcription_timeout", "transcription_failed",
    "transcription_storage", "language_metadata",
])
def test_rejected_transcription_next_utterance_works_without_worker_restart(tmp_path, monkeypatch, code):
    recordings = []

    def transcribe(path):
        with wave.open(str(path), "rb") as audio:
            assert audio.getframerate() == 16000 and audio.getnchannels() == 1
            recordings.append(audio.getnframes())
        if len(recordings) == 1:
            return TranscriptionResult(False, "", STT_ERRORS[code], error_code=code)
        return TranscriptionResult(True, "A clear English follow-up.", detected_language="en")

    service, state = listener(tmp_path, monkeypatch,
                              [VOICE] * 3 + PAUSE + TAIL + [VOICE] * 3 + PAUSE, transcribe)
    service.run_forever()
    assert len(state.starts) == 1 and len(recordings) == 2
    assert state.transcripts == ["A clear English follow-up."]
    assert len(state.errors) == 1 and state.errors[0].code == code
    assert state.phases.count("armed") >= 2
    assert len(state.discarded) == 2
    assert all(state.events[index + 1:index + 3] == ["reset", "armed"]
               for index, event in enumerate(state.events) if event == "discard")
    assert service.last_transcription_language == "en"
    assert not list(tmp_path.iterdir())


def test_unfinished_utterance_is_not_submitted_and_next_complete_one_works(tmp_path, monkeypatch):
    recordings = []

    def transcribe(path):
        with wave.open(str(path), "rb") as audio:
            recordings.append(np.frombuffer(audio.readframes(audio.getnframes()), dtype=np.int16))
        return TranscriptionResult(True, "Only the completed request.")

    service, state = listener(tmp_path, monkeypatch,
                              [VOICE] * 125 + TAIL + [VOICE] * 3 + PAUSE, transcribe)
    service.run_forever()
    assert len(state.starts) == len(recordings) == 1
    assert state.transcripts == ["Only the completed request."]
    assert np.count_nonzero(recordings[0]) == 3 * SAMPLES
    assert len(state.errors) == 1 and state.errors[0].code == "utterance_too_long"
    assert not list(tmp_path.iterdir())


def test_recovery_retains_wake_requirement_and_resets_detector(tmp_path, monkeypatch):
    calls = []

    def transcribe(path):
        calls.append(path)
        if len(calls) == 1:
            return TranscriptionResult(False, "", STT_ERRORS["transcription_script_mismatch"],
                                       error_code="transcription_script_mismatch")
        return TranscriptionResult(True, "A separately awakened request.")

    service, state = listener(tmp_path, monkeypatch,
                              [WAKE] + PAUSE + TAIL + [VOICE] * 3 + PAUSE + [WAKE] + PAUSE,
                              transcribe, require_wake_word=True)
    service.run_forever()
    assert len(calls) == 2 and len(state.starts) == 1
    assert state.transcripts == ["A separately awakened request."]
    assert len(state.discarded) == 2
    assert all(state.events[index + 1] == "reset"
               for index, event in enumerate(state.events) if event == "discard")
    assert 2000 in state.detections  # Ordinary speech between wake words did not submit.
    assert not list(tmp_path.iterdir())


def test_expected_failures_use_existing_code_and_fifteen_second_rate_limit(tmp_path, monkeypatch):
    frames = ([VOICE] * 3 + TAIL) * 4
    service, state = listener(tmp_path, monkeypatch, frames,
                              lambda _: pytest.fail("Synthetic rejected text was transcribed"))
    failures = deque([
        (1, "transcription_script_mismatch"), (6, "transcription_script_mismatch"),
        (17, "transcription_script_mismatch"), (18, "transcription_timeout"),
    ])

    def capture(*_args):
        state.clock, code = failures.popleft()
        raise VoicePipelineError(code, "SYNTHETIC_PRIVATE_BACKEND_TEXT")

    monkeypatch.setattr(service, "_capture_and_transcribe", capture)
    service.run_forever()
    assert not failures and not state.transcripts
    assert [exc.code for exc in state.errors] == [
        "transcription_script_mismatch", "transcription_script_mismatch", "transcription_timeout",
    ]
    assert len(state.starts) == 1 and len(state.discarded) == 4
    assert all(state.events[index + 1] == "reset"
               for index, event in enumerate(state.events) if event == "discard")
    assert all("SYNTHETIC_PRIVATE_BACKEND_TEXT" not in diagnostic(exc, "transcribing")[1]
               for exc in state.errors)


@pytest.mark.parametrize("error", [RuntimeError("Synthetic stream stalled"), OSError("Synthetic transport failed")])
@pytest.mark.parametrize("failure_point", ["before_capture", "during_capture"])
def test_recorder_transport_failures_remain_fatal_and_do_not_submit(tmp_path, monkeypatch, error, failure_point):
    service, state = listener(tmp_path, monkeypatch, [VOICE] * 3,
                              lambda _: pytest.fail("A transport failure reached transcription"))
    read = service._read_audio
    received = []

    def fail(_size):
        if failure_point == "during_capture" and len(received) < 3:
            received.append(True)
            return read(_size)
        raise error

    monkeypatch.setattr(service, "_read_audio", fail)
    with pytest.raises(type(error), match="Synthetic"):
        service.run_forever()
    assert service._stop.is_set() and not state.transcripts and not state.errors


def test_processing_failure_after_valid_transcript_is_not_misclassified_as_capture(tmp_path, monkeypatch):
    service, state = listener(tmp_path, monkeypatch, [VOICE] * 3 + PAUSE,
                              lambda _: TranscriptionResult(True, "A completed request."))

    def reject_processing(_text):
        raise VoicePipelineError("model_timeout", "Synthetic reasoning timeout")

    service.on_transcript = reject_processing
    with pytest.raises(VoicePipelineError, match="reasoning timeout"):
        service.run_forever()
    assert service._stop.is_set() and not state.errors
    assert not list(tmp_path.iterdir())


def test_unexpected_transcriber_exception_remains_fatal_and_removes_wav(tmp_path, monkeypatch):
    def fail(_path):
        raise ValueError("Synthetic unexpected backend bug")

    service, state = listener(tmp_path, monkeypatch, [VOICE] * 3 + PAUSE, fail)
    with pytest.raises(ValueError, match="unexpected backend bug"):
        service.run_forever()
    assert service._stop.is_set() and not state.transcripts and not state.errors
    assert not list(tmp_path.iterdir())
