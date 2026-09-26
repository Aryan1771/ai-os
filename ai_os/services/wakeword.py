from __future__ import annotations

from collections.abc import Iterable


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
