from __future__ import annotations

import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


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
    ) -> None:
        self.piper_model = piper_model
        self.length_scale = max(0.5, min(2.0, float(length_scale)))
        self._counter_lock = threading.Lock()
        self.last_error: str | None = None
        self._queue: queue.PriorityQueue[tuple[int, int, SpeechItem]] = queue.PriorityQueue()
        self._counter = 0
        self._stop = threading.Event()
        self._speaking = threading.Event()
        self.on_activity = on_activity or (lambda _phase, _text, _avatar: None)

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def enqueue(self, text: str, priority: int = 10, *, avatar: dict | None = None) -> None:
        with self._counter_lock:
            self._counter += 1
            self._queue.put(
                (priority, self._counter, SpeechItem(text=text, priority=priority, avatar=avatar))
            )

    def enqueue_bridge(self, text: str) -> None:
        self.enqueue(f"Oh, by the way. {text}", priority=5)

    def stop(self) -> None:
        self._stop.set()

    def sentence_chunks(self, text: str) -> Iterable[str]:
        for chunk in re.split(r"(?<=[.!?])\s+", text.strip()):
            if chunk:
                yield chunk

    def speak_text(self, text: str) -> None:
        if not self.piper_model or not self.piper_model.is_file():
            raise RuntimeError("Piper voice model is missing.")
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
        with tempfile.TemporaryDirectory(prefix="regenos-speech-") as directory:
            output = Path(directory) / "speech.wav"
            subprocess.run(
                [
                    piper,
                    "--model",
                    str(self.piper_model),
                    "--output_file",
                    str(output),
                    "--length_scale",
                    str(self.length_scale),
                ],
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=60,
                check=True,
            )
            with wave.open(str(output), "rb") as wav:
                if not wav.getnframes() or not 8000 <= wav.getframerate() <= 192000:
                    raise ValueError("Piper generated an invalid or empty WAV.")
                duration = wav.getnframes() / wav.getframerate()
                if duration > 180:
                    raise ValueError("Speech output exceeds the playback duration limit.")
            if not self._stop.is_set():
                subprocess.run(
                    [player, str(output)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=duration + 10,
                    check=True,
                )

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
                    self.speak_text(sentence)
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
                if not failed:
                    self.last_error = None
                    self.on_activity("idle", "", None)
                self._queue.task_done()
