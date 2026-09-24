from __future__ import annotations

from collections.abc import Iterable


class WakeWordService:
    """Optional openWakeWord adapter; importing the package remains lazy."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = max(0.0, min(1.0, float(threshold)))
        self._model = None

    def start(self) -> tuple[bool, str]:
        try:
            from openwakeword.model import Model
        except ImportError:
            return False, "openwakeword is not installed in the AI-OS virtual environment."
        self._model = Model()
        return True, "ready"

    def detect(self, pcm_frames: Iterable[object]) -> bool:
        if self._model is None:
            raise RuntimeError("WakeWordService.start() must be called first.")
        for frame in pcm_frames:
            scores = self._model.predict(frame)
            if any(float(score) >= self.threshold for score in scores.values()):
                return True
        return False
