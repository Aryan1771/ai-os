from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
import wave
import os
import selectors
import math
from collections import deque
from collections.abc import Callable
from pathlib import Path

import numpy as np

from ai_os.services.stt import WhisperCppTranscriber
from ai_os.services.wakeword import WakeWordService, ReWhisperWakeWord
from ai_os.voice_timings import elapsed_timing, record_timing
from ai_os.voice_progress import ProgressReporter


class AlwaysListeningService:
    """Local PipeWire capture gated by an optional wake word and local Whisper.cpp."""

    def __init__(
        self,
        *,
        run_dir: Path,
        transcriber: WhisperCppTranscriber,
        on_transcript: Callable[[str], None],
        wake_word_threshold: float = 0.5,
        command_seconds: int = 8,
        silence_seconds: float = 5.0,
        max_utterance_seconds: int = 120,
        sample_rate: int = 16_000,
        on_activity: Callable[[str], None] | None = None,
        playback_active: Callable[[], bool] | None = None,
        wake_word_model: str = "",
        wake_backend: str = "openwakeword",
        require_wake_word: bool = True,
        speaker_filter: Callable[[Path], tuple[bool, str]] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        input_target: str = "",
        on_capture_complete: Callable[[], None] | None = None,
        on_progress: Callable[[dict], None] | None = None,
    ) -> None:
        self.run_dir = run_dir
        self.require_wake_word = require_wake_word
        self.transcriber = transcriber
        self.on_transcript = on_transcript
        self.speaker_filter = speaker_filter
        self.last_transcription_language = None
        self.last_capture_error = None
        self.on_error = on_error or (lambda _error: None)
        self._last_reported_error = None
        if wake_backend not in {"openwakeword", "re_whisper"}:
            raise ValueError("Unsupported wake detector")
        self.wake_word = (ReWhisperWakeWord(transcriber, run_dir) if wake_backend == "re_whisper"
                          else WakeWordService(wake_word_threshold, wake_word_model))
        self.command_seconds = max(2, min(30, int(command_seconds)))
        self.silence_seconds = max(1.0, min(10.0, float(silence_seconds)))
        self.max_utterance_seconds = max(10, min(120, int(max_utterance_seconds)))
        self.sample_rate = sample_rate
        self.input_target = input_target
        self.on_capture_complete = on_capture_complete
        self.progress = ProgressReporter(on_progress)
        self.on_activity = on_activity or (lambda _phase: None)
        self.playback_active = playback_active or (lambda: False)
        self._stop = threading.Event()
        self._process: subprocess.Popen[bytes] | None = None

    def availability(self) -> tuple[bool, str]:
        if not shutil.which("pw-record"):
            return False, "pw-record is unavailable; install PipeWire utilities."
        ready, reason = self.transcriber.availability()
        if not ready:
            return False, reason
        return self.wake_word.start() if self.require_wake_word else (True, "conversation listening")

    @staticmethod
    def has_speech(audio: bytes) -> bool:
        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32)
        return bool(samples.size and np.sqrt(np.mean(samples * samples)) >= 450)

    def _read_audio(self, size: int) -> bytes:
        """Bound stalls and cancellation; pipe reads cannot block indefinitely."""
        if self._process is None or self._process.stdout is None:
            return b""
        data = bytearray()
        deadline = time.monotonic() + 3
        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            while len(data) < size and not self._stop.is_set():
                if time.monotonic() >= deadline:
                    raise RuntimeError("Microphone stream stalled; check PipeWire input device")
                if not selector.select(0.1):
                    continue
                part = os.read(self._process.stdout.fileno(), size - len(data))
                if not part:
                    if self._stop.is_set():
                        return b""
                    raise RuntimeError("PipeWire recorder exited unexpectedly")
                data.extend(part)
        return bytes(data)

    def _discard_backlog(self):
        if self._process is None or self._process.stdout is None:
            return
        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            for _ in range(64):
                if not selector.select(0):
                    break
                if not os.read(self._process.stdout.fileno(), 65536):
                    break

    def stop(self) -> None:
        self._stop.set()
        self.stop_recorder()

    def stop_recorder(self):
        """Reap owned capture without marking a completed utterance cancelled."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                return self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                return self._process.wait(timeout=2)
        if self._process is not None:
            return self._process.poll()

    def run_forever(self) -> None:
        ready, reason = self.availability()
        if not ready:
            raise RuntimeError(reason)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        chunk_samples = 1_280
        chunk_bytes = chunk_samples * 2
        from ai_os.audio_input import recorder_arguments
        self._process = subprocess.Popen(
            ["pw-record", *recorder_arguments(self.input_target, sample_rate=self.sample_rate)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
            shell=False,
        )
        if self._process.stdout is None:
            raise RuntimeError("PipeWire recorder did not provide an audio stream.")

        self.on_activity("armed")
        last_heartbeat = time.monotonic()
        preroll = deque(maxlen=5)
        speech_frames = 0
        playback_tail_until = 0.0
        try:
            while not self._stop.is_set():
                audio = self._read_audio(chunk_bytes)
                if len(audio) != chunk_bytes:
                    if self._process.poll() is not None:
                        raise RuntimeError("PipeWire recorder exited unexpectedly.")
                    continue
                frame = np.frombuffer(audio, dtype=np.int16)
                playing = self.playback_active()
                if playing:
                    playback_tail_until = time.monotonic() + 0.4
                if playing or time.monotonic() < playback_tail_until:
                    preroll.clear()
                    speech_frames = 0
                    if hasattr(self.wake_word, "reset"):
                        self.wake_word.reset()
                    continue
                preroll.append(audio)
                if time.monotonic() - last_heartbeat > 30:
                    if not self.playback_active():
                        self.on_activity("armed")
                    last_heartbeat = time.monotonic()
                speech_frames = speech_frames + 1 if self.has_speech(audio) else 0
                detected = (self.wake_word.detect_frame(frame) if self.require_wake_word
                            else speech_frames >= 3)
                if detected:
                    self.on_activity("listening")
                    from ai_os.services.voice_errors import VoicePipelineError
                    try:
                        transcript = self._capture_and_transcribe(b"".join(preroll), chunk_bytes)
                    except VoicePipelineError as exc:
                        # A rejected/unfinished utterance is not a failed recorder.
                        # Report it through the same bounded path as speaker
                        # rejection, discard its backlog, then re-arm normally.
                        self.last_capture_error = exc
                        transcript = ""
                    if transcript and not self._stop.is_set():
                        self.on_transcript(transcript)
                    elif self.last_capture_error is not None and not self._stop.is_set():
                        # A rejected speaker must be visible without killing the
                        # worker or producing repeated unsolicited speech.
                        code = getattr(self.last_capture_error, "code", "capture_failed")
                        now = time.monotonic()
                        previous = self._last_reported_error
                        if previous is None or code != previous[0] or now - previous[1] >= 15:
                            self.on_error(self.last_capture_error)
                            self._last_reported_error = (code, now)
                    self._discard_backlog()
                    # Reply handling is synchronous; playback can start and
                    # finish before playback_active is sampled by this loop.
                    playback_tail_until = time.monotonic() + 0.4
                    if hasattr(self.wake_word, "reset"):
                        self.wake_word.reset()
                    preroll.clear()
                    speech_frames = 0
                    if not self.playback_active():
                        self.on_activity("armed")
        finally:
            self.stop()

    def _capture_and_transcribe(self, first_chunk: bytes, chunk_bytes: int, *, metrics=None) -> str:
        self.last_transcription_language = None
        self.last_capture_error = None
        if self._process is None or self._process.stdout is None:
            return ""
        if self.playback_active():
            return ""
        chunks = [first_chunk]
        # The initial speech wait and the spoken utterance have separate bounds.
        # Count PCM samples for endpointing: recorder scheduling must not turn a
        # brief human pause into the end of a sentence or extend an utterance.
        capture_started = time.monotonic()
        deadline = capture_started + self.max_utterance_seconds
        max_samples = self.sample_rate * self.max_utterance_seconds
        captured_samples = len(first_chunk) // 2
        silence_samples = math.ceil(self.sample_rate * self.silence_seconds)
        silent_samples = 0
        endpoint_reached = False
        try:
            while (time.monotonic() < deadline and captured_samples < max_samples
                   and not self._stop.is_set()):
                audio = self._read_audio(min(chunk_bytes, (max_samples - captured_samples) * 2))
                if not audio:
                    break
                # A separately requested voice test or announcement can win the
                # output turn while recording. Never submit its sound as a command.
                if self.playback_active():
                    return ""
                chunks.append(audio)
                samples = len(audio) // 2
                captured_samples += samples
                silent_samples = 0 if self.has_speech(audio) else silent_samples + samples
                self.progress.emit("capturing", captured_seconds=captured_samples / self.sample_rate,
                                   silence_seconds=silent_samples / self.sample_rate,
                                   required_silence_seconds=self.silence_seconds)
                if silent_samples >= silence_samples:
                    endpoint_reached = True
                    break
        finally:
            elapsed_timing(metrics, "capture_seconds", capture_started)
            record_timing(metrics, "captured_audio_seconds", captured_samples / self.sample_rate)
            if endpoint_reached:
                record_timing(metrics, "ending_silence_audio_seconds", silent_samples / self.sample_rate)

        if self._stop.is_set():
            return ""
        if not endpoint_reached and (captured_samples >= max_samples or time.monotonic() >= deadline):
            from ai_os.services.voice_errors import VoicePipelineError
            raise VoicePipelineError(
                "utterance_too_long",
                "Speech exceeded the maximum utterance duration before the ending pause. "
                "No request was submitted; please repeat in shorter parts.",
            )

        if self.on_capture_complete is not None:
            if not endpoint_reached:
                from ai_os.services.voice_errors import VoicePipelineError
                raise VoicePipelineError("capture_failed", "Recording did not reach the ending pause; no request was submitted.")
            self.on_capture_complete()
            if self._stop.is_set():
                return ""

        with tempfile.NamedTemporaryFile(dir=self.run_dir, suffix=".wav", delete=False) as handle:
            audio_path = Path(handle.name)
        try:
            with wave.open(str(audio_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                audio = b"".join(chunks)
                # Wait for the full chosen pause, then avoid sending several
                # seconds of trailing silence through Whisper. Keep a short
                # tail so the final word is not clipped at the energy boundary.
                trim_samples = max(0, silent_samples - self.sample_rate // 5) if endpoint_reached else 0
                wav_file.writeframes(audio[:-trim_samples * 2] if trim_samples else audio)
            if self.speaker_filter is not None:
                self.progress.emit("filtering")
                from ai_os.services.voice_errors import VoicePipelineError, VOICE_MESSAGES
                from ai_os.speaker_filter import MESSAGES
                filter_started = time.monotonic() if metrics is not None else None
                try:
                    allowed, reason = self.speaker_filter(audio_path)
                except Exception:
                    allowed, reason = False, MESSAGES["speaker_unavailable"]
                finally:
                    elapsed_timing(metrics, "speaker_filter_seconds", filter_started)
                if not allowed:
                    code = next((key for key in ("speaker_rejected", "speaker_unavailable", "speaker_timeout")
                                 if reason == MESSAGES[key]), "speaker_rejected")
                    self.last_capture_error = VoicePipelineError(code, VOICE_MESSAGES[code])
                    return ""
            self.on_activity("transcribing")
            self.progress.emit("transcribing")
            stt_started = time.monotonic() if metrics is not None else None
            try:
                result = self.transcriber.transcribe_file(audio_path)
            finally:
                elapsed_timing(metrics, "stt_seconds", stt_started)
            if not result.ok:
                from ai_os.services.stt import STT_ERRORS
                from ai_os.services.voice_errors import VoicePipelineError
                if result.error == "No speech recognized":
                    return ""
                if getattr(result, "error_code", "") in STT_ERRORS:
                    raise VoicePipelineError(result.error_code, STT_ERRORS[result.error_code])
                raise VoicePipelineError("transcription_failed", "Transcription failed in Whisper. Check the executable, multilingual model and selected language.")
            self.last_transcription_language = getattr(result, "detected_language", None)
            return result.text
        finally:
            audio_path.unlink(missing_ok=True)
