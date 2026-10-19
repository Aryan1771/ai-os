from __future__ import annotations

from collections.abc import Iterable
from collections import deque
import importlib.util
from pathlib import Path
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

    @staticmethod
    def module_available(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            return False

    def local_configuration(self) -> dict:
        """Inspect installed assets only; never import an inference model/download."""
        if not self.module_available("openwakeword"):
            return {"ready": False, "message": "openWakeWord is not installed in the REgenOS virtual environment."}
        try:
            spec = importlib.util.find_spec("openwakeword")
            resource_dir = Path(spec.origin).parent / "resources" / "models"
        except (AttributeError, TypeError, ImportError, ValueError):
            return {"ready": False, "message": "The installed openWakeWord package location is unavailable."}
        custom = Path(self.model_path).expanduser() if self.model_path else None
        if custom is not None and (not custom.is_file() or custom.suffix not in {".onnx", ".tflite"}):
            return {"ready": False, "message": "Choose an existing .onnx or .tflite wake-word model."}
        known_models = ("alexa_v0.1", "hey_mycroft_v0.1", "hey_jarvis_v0.1",
                        "hey_rhasspy_v0.1", "timer_v0.1", "weather_v0.1")
        frameworks = ([custom.suffix[1:]] if custom is not None else ["onnx", "tflite"])
        missing_runtime = True
        for framework in frameworks:
            runtime = "onnxruntime" if framework == "onnx" else "tflite_runtime"
            if not self.module_available(runtime):
                continue
            missing_runtime = False
            models = ([custom] if custom is not None else [resource_dir / (name + "." + framework)
                       for name in known_models if (resource_dir / (name + "." + framework)).is_file()])
            features = [resource_dir / (name + "." + framework)
                        for name in ("melspectrogram", "embedding_model")]
            if models and all(path.is_file() for path in features):
                return {"ready": True, "message": "Local wake assets are present; actual model loading and microphone detection are untested.",
                        "framework": framework, "models": [str(path) for path in models]}
        message = ("The inference runtime for the selected wake-word model is missing from the venv."
                   if missing_runtime else "Local openWakeWord wake/feature model assets are missing. Provision reviewed assets explicitly; nothing was downloaded.")
        return {"ready": False, "message": message}

    def availability(self) -> tuple[bool, str]:
        status = self.local_configuration()
        return status["ready"], status["message"]

    def start(self) -> tuple[bool, str]:
        self._model = None
        try:
            from openwakeword.model import Model
        except Exception:
            return False, "The openWakeWord backend is unavailable. Check its optional venv dependencies."
        try:
            if self.model_path:
                path = Path(self.model_path).expanduser()
                if not path.is_file() or path.suffix not in {".onnx", ".tflite"}:
                    return False, "Choose an existing .onnx or .tflite wake-word model."
                self._model = Model(
                    wakeword_models=[str(path)],
                    inference_framework="onnx" if path.suffix == ".onnx" else "tflite",
                )
            else:
                status = self.local_configuration()
                if not status["ready"]:
                    return False, status["message"]
                self._model = Model(wakeword_models=status["models"],
                                    inference_framework=status["framework"])
        except Exception:
            self._model = None
            return False, "Wake-word model could not start. Check the selected model, its shared feature assets and matching venv inference runtime."
        return True, "ready"

    def reset(self) -> None:
        if self._model is not None:
            self._model.reset()

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
