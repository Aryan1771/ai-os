from __future__ import annotations

import queue
import re
import shutil
import subprocess
import threading
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
    ) -> None:
        self.piper_model = piper_model
        self._queue: queue.PriorityQueue[tuple[int, int, SpeechItem]] = queue.PriorityQueue()
        self._counter = 0
        self._stop = threading.Event()
        self._speaking = threading.Event()
        self.on_activity = on_activity or (lambda _phase, _text, _avatar: None)

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def enqueue(self, text: str, priority: int = 10, *, avatar: dict | None = None) -> None:
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
        if self.piper_model and self.piper_model.exists():
            player = shutil.which("pw-play")
            if player and shutil.which("piper"):
                try:
                    piper = subprocess.Popen(
                        ["piper", "--model", str(self.piper_model), "--output-raw"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                    )
                    player_process = subprocess.Popen(
                        [
                            player,
                            "--raw",
                            "--rate",
                            "22050",
                            "--channels",
                            "1",
                            "--format",
                            "s16",
                            "-",
                        ],
                        stdin=piper.stdout,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if piper.stdin:
                        piper.stdin.write(text.encode("utf-8"))
                        piper.stdin.close()
                    piper.wait(timeout=30)
                    player_process.wait(timeout=30)
                    return
                except (OSError, subprocess.TimeoutExpired):
                    if "piper" in locals():
                        piper.kill()
                    if "player_process" in locals():
                        player_process.kill()
        print(f"[speech] {text}", flush=True)

    def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                _, _, item = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            self._speaking.set()
            try:
                for sentence in self.sentence_chunks(item.text):
                    if self._stop.is_set():
                        break
                    self.on_activity("speaking", sentence, item.avatar)
                    self.speak_text(sentence)
            finally:
                self._speaking.clear()
                self.on_activity("idle", "", None)
                self._queue.task_done()
