from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

from ai_os.services.stt import WhisperCppTranscriber
from ai_os.services.wakeword import WakeWordService


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
        sample_rate: int = 16_000,
        on_activity: Callable[[str], None] | None = None,
        playback_active: Callable[[], bool] | None = None,
    ) -> None:
        self.run_dir = run_dir
        self.transcriber = transcriber
        self.on_transcript = on_transcript
        self.wake_word = WakeWordService(wake_word_threshold)
        self.command_seconds = max(2, min(30, int(command_seconds)))
        self.sample_rate = sample_rate
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
        return self.wake_word.start()

    def stop(self) -> None:
        self._stop.set()
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run_forever(self) -> None:
        ready, reason = self.availability()
        if not ready:
            raise RuntimeError(reason)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        chunk_samples = 1_280
        chunk_bytes = chunk_samples * 2
        self._process = subprocess.Popen(
            [
                "pw-record",
                "--raw",
                "--format",
                "s16",
                "--rate",
                str(self.sample_rate),
                "--channels",
                "1",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if self._process.stdout is None:
            raise RuntimeError("PipeWire recorder did not provide an audio stream.")

        try:
            while not self._stop.is_set():
                audio = self._process.stdout.read(chunk_bytes)
                if len(audio) != chunk_bytes:
                    if self._process.poll() is not None:
                        raise RuntimeError("PipeWire recorder exited unexpectedly.")
                    continue
                frame = np.frombuffer(audio, dtype=np.int16)
                if self.playback_active():
                    continue
                if self.wake_word.detect_frame(frame):
                    self.on_activity("listening")
                    transcript = self._capture_and_transcribe(audio, chunk_bytes)
                    if transcript:
                        self.on_transcript(transcript)
                    else:
                        self.on_activity("idle")
        finally:
            self.stop()

    def _capture_and_transcribe(self, first_chunk: bytes, chunk_bytes: int) -> str:
        if self._process is None or self._process.stdout is None:
            return ""
        chunks = [first_chunk]
        deadline = time.monotonic() + self.command_seconds
        while time.monotonic() < deadline and not self._stop.is_set():
            audio = self._process.stdout.read(chunk_bytes)
            if not audio:
                break
            chunks.append(audio)

        with tempfile.NamedTemporaryFile(dir=self.run_dir, suffix=".wav", delete=False) as handle:
            audio_path = Path(handle.name)
        try:
            with wave.open(str(audio_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(b"".join(chunks))
            self.on_activity("transcribing")
            result = self.transcriber.transcribe_file(audio_path)
            return result.text if result.ok else ""
        finally:
            audio_path.unlink(missing_ok=True)
