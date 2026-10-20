from __future__ import annotations

import queue
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from ai_os.voice_timings import elapsed_timing


def emotional_pace(base: float, avatar: dict | None) -> float:
    from ai_os.companion_state import visual_metadata
    levels = visual_metadata(avatar).get("emotions", {})
    # Small duration changes; Piper's fixed voice is not an expressive emotion model.
    adjustment = 0.12 * levels.get("concern", 0) / 100 - 0.08 * levels.get("energy", 50) / 100
    return max(0.5, min(2.0, base * (1 + adjustment)))


@dataclass(frozen=True)
class SpeechItem:
    text: str
    priority: int = 10
    avatar: dict | None = None


class SpeechQueue:
    def __init__(
        self,
        piper_model: Path | None = None,
        *,
        on_activity: Callable[[str, str, dict | None], None] | None = None,
        length_scale: float = 1.0,
        hindi_model: Path | None = None,
        emotion_enabled: bool = True,
    ) -> None:
        self.piper_model = piper_model
        self.hindi_model = hindi_model
        self.emotion_enabled = emotion_enabled
        self.length_scale = max(0.5, min(2.0, float(length_scale)))
        self._counter_lock = threading.Lock()
        self.last_error: str | None = None
        self._queue: queue.PriorityQueue[tuple[int, int, SpeechItem]] = queue.PriorityQueue()
        self._counter = 0
        self._pending = 0
        self._stop = threading.Event()
        self._speaking = threading.Event()
        self.on_activity = on_activity or (lambda _phase, _text, _avatar: None)

    def is_speaking(self) -> bool:
        # A queued reply already owns the output turn. Otherwise the listener can
        # reopen between enqueue and the worker starting Piper, capturing its reply.
        with self._counter_lock:
            return self._speaking.is_set() or self._pending > 0

    def enqueue(self, text: str, priority: int = 10, *, avatar: dict | None = None) -> None:
        with self._counter_lock:
            if self._stop.is_set():
                return
            self._counter += 1
            self._pending += 1
            self._queue.put(
                (priority, self._counter, SpeechItem(text=text, priority=priority, avatar=avatar))
            )

    def enqueue_bridge(self, text: str) -> None:
        self.enqueue(f"Oh, by the way. {text}", priority=5)

    def stop(self) -> None:
        self._stop.set()
        # Cancel unheard replies instead of leaving a stale backlog available to
        # a stopped queue. The current bounded playback finishes separately.
        with self._counter_lock:
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
                self._pending -= 1
                self._queue.task_done()

    def sentence_chunks(self, text: str) -> Iterable[str]:
        for chunk in re.split(r"(?<=[.!?।])\s+", text.strip()):
            if chunk:
                yield chunk

    def speak_text(self, text: str, *, avatar: dict | None = None, metrics=None) -> None:
        model = self.hindi_model if re.search(r"[\u0900-\u097f]", text) else self.piper_model
        if not model or not model.is_file():
            raise RuntimeError("Piper voice model for the requested language is missing.")
        player, piper = shutil.which("pw-play"), shutil.which("piper")
        venv_piper = Path(sys.executable).with_name(
            "piper.exe" if sys.platform == "win32" else "piper"
        )
        if venv_piper.is_file():
            piper = str(venv_piper)
        if not player or not piper:
            raise RuntimeError("Piper and pw-play must be installed to speak.")
        if not text.strip() or len(text) > 8000:
            raise ValueError("Speech text must contain 1-8000 characters.")
        # WAV metadata supplies each voice's real sample rate; no fixed raw PCM rate.
        with tempfile.TemporaryDirectory(prefix="regenos-speech-", dir=os.environ.get("AI_OS_VOICE_TMP")) as directory:
            output = Path(directory) / "speech.wav"
            synthesis_started = time.monotonic() if metrics is not None else None
            try:
                subprocess.run(
                    [
                        piper,
                        "--model",
                        str(model),
                        "--output_file",
                        str(output),
                        "--length_scale",
                        str(emotional_pace(self.length_scale, avatar) if self.emotion_enabled and avatar else self.length_scale),
                    ],
                    input=re.sub(r"\bRE\b", "R E", text).encode("utf-8"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=60,
                    check=True,
                )
            finally:
                elapsed_timing(metrics, "synthesis_seconds", synthesis_started, accumulate=True)
            with wave.open(str(output), "rb") as wav:
                if not wav.getnframes() or not 8000 <= wav.getframerate() <= 192000:
                    raise ValueError("Piper generated an invalid or empty WAV.")
                duration = wav.getnframes() / wav.getframerate()
                if duration > 180:
                    raise ValueError("Speech output exceeds the playback duration limit.")
            if not self._stop.is_set():
                playback_started = time.monotonic() if metrics is not None else None
                try:
                    subprocess.run(
                        [player, str(output)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        timeout=duration + 10,
                        check=True,
                    )
                finally:
                    elapsed_timing(metrics, "playback_seconds", playback_started, accumulate=True)

    def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                _, _, item = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            self._speaking.set()
            failed = False
            try:
                for sentence in self.sentence_chunks(item.text):
                    if self._stop.is_set():
                        break
                    self.on_activity("speaking", sentence, item.avatar)
                    self.speak_text(sentence, avatar=item.avatar)
            except (
                OSError,
                ValueError,
                RuntimeError,
                subprocess.SubprocessError,
                wave.Error,
            ) as exc:
                failed = True
                self.last_error = str(exc)
                self.on_activity("error", "Speech playback failed", None)
            finally:
                self._speaking.clear()
                with self._counter_lock:
                    self._pending -= 1
                if not failed:
                    self.last_error = None
                    self.on_activity("idle", "", None)
                self._queue.task_done()
