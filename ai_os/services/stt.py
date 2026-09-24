from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranscriptionResult:
    ok: bool
    text: str
    error: str = ""


class WhisperCppTranscriber:
    """Minimal, shell-free adapter for a locally installed whisper.cpp CLI."""

    def __init__(self, executable: str, model: Path, timeout_sec: int = 120) -> None:
        self.executable = executable
        self.model = model
        self.timeout_sec = timeout_sec

    def availability(self) -> tuple[bool, str]:
        if not shutil.which(self.executable):
            return False, f"{self.executable} is not installed or not on PATH."
        if not self.model.is_file():
            return False, f"Whisper model is missing: {self.model}"
        return True, "ready"

    def transcribe_file(self, audio_file: Path) -> TranscriptionResult:
        ready, reason = self.availability()
        if not ready:
            return TranscriptionResult(False, "", reason)
        if not audio_file.is_file():
            return TranscriptionResult(False, "", f"Audio file is missing: {audio_file}")

        try:
            result = subprocess.run(
                [self.executable, "-m", str(self.model), "-f", str(audio_file), "-nt"],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeout_sec,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return TranscriptionResult(False, "", str(exc))
        if result.returncode != 0:
            return TranscriptionResult(False, "", result.stderr.strip() or "Whisper failed.")
        return TranscriptionResult(True, result.stdout.strip())
