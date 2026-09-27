from __future__ import annotations

from collections.abc import Iterable
from collections import deque
import re
import tempfile
import time
import wave

import numpy as np


class ReWhisperWakeWord:
    """Experimental local name detector; not speaker verification or authentication.

    Two-second overlapping windows are transcribed every second. Only an isolated
    name (optionally Hey/Hello) is accepted. Temporary audio is always removed.
    """

    def __init__(self, transcriber, run_dir):
        from ai_os.services.stt import WhisperCppTranscriber
        self.transcriber = WhisperCppTranscriber(transcriber.executable, transcriber.model,
                                                timeout_sec=5, language="en")
        self.run_dir = run_dir
        self.frames = deque(maxlen=25)
        self.since = 0
        self.cooldown = 0.0

    def start(self):
        return self.transcriber.availability()

    def reset(self):
        self.frames.clear()
        self.since = 0

    @staticmethod
    def matches(text):
        normalized = re.sub(r"[^a-z ]", "", text.lower()).strip()
        return re.fullmatch(r"(?:(?:hey|hello|hi)\s+)?(?:r\s*e|ar\s*ee|are\s*ee|ary)", normalized) is not None

    def detect_frame(self, pcm_frame):
        if time.monotonic() < self.cooldown:
            return False
        self.frames.append(np.asarray(pcm_frame, dtype=np.int16).tobytes())
        self.since += 1
        if len(self.frames) < 25 or self.since < 13:
            return False
        self.since = 0
        pcm = b"".join(self.frames)
        if np.abs(np.frombuffer(pcm, dtype=np.int16).astype(np.int32)).max() < 300:
            return False
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="re-wake-", dir=self.run_dir) as directory:
            from pathlib import Path
            path = Path(directory) / "wake.wav"
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(pcm)
            result = self.transcriber.transcribe_file(path)
        if result.ok and self.matches(result.text):
            self.reset()
            self.cooldown = time.monotonic() + 3
            return True
        return False


class WakeWordService:
    """Optional openWakeWord adapter; importing the package remains lazy."""

    def __init__(self, threshold: float = 0.5, model_path: str = "") -> None:
        self.threshold = max(0.0, min(1.0, float(threshold)))
        self.model_path = model_path
        self._model = None

    def start(self) -> tuple[bool, str]:
        try:
            from openwakeword.model import Model
        except ImportError:
            return False, "openwakeword is not installed in the AI-OS virtual environment."
        try:
            if self.model_path:
                from pathlib import Path

                path = Path(self.model_path)
                if not path.is_file() or path.suffix not in {".onnx", ".tflite"}:
                    return False, "Choose an existing .onnx or .tflite wake-word model."
                self._model = Model(
                    wakeword_models=[str(path)],
                    inference_framework="onnx" if path.suffix == ".onnx" else "tflite",
                )
            else:
                self._model = Model()
        except (OSError, ValueError, RuntimeError) as exc:
            return False, f"Wake-word model could not start: {exc}"
        return True, "ready"

    def detect(self, pcm_frames: Iterable[object]) -> bool:
        if self._model is None:
            raise RuntimeError("WakeWordService.start() must be called first.")
        for frame in pcm_frames:
            scores = self._model.predict(frame)
            if any(float(score) >= self.threshold for score in scores.values()):
                return True
        return False

    def detect_frame(self, pcm_frame: object) -> bool:
        return self.detect([pcm_frame])
