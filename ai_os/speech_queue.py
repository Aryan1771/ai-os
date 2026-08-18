from __future__ import annotations

import queue
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SpeechItem:
    text: str
    priority: int = 10


class SpeechQueue:
    def __init__(self, piper_model: Path | None = None) -> None:
        self.piper_model = piper_model
        self._queue: queue.PriorityQueue[tuple[int, int, SpeechItem]] = queue.PriorityQueue()
        self._counter = 0
        self._stop = threading.Event()

    def enqueue(self, text: str, priority: int = 10) -> None:
        self._counter += 1
        self._queue.put((priority, self._counter, SpeechItem(text=text, priority=priority)))

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
            subprocess.run(
                ["piper", "--model", str(self.piper_model), "--output-raw"],
                input=text,
                text=True,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        print(f"[speech] {text}", flush=True)

    def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                _, _, item = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            for sentence in self.sentence_chunks(item.text):
                if self._stop.is_set():
                    break
                self.speak_text(sentence)
            self._queue.task_done()

