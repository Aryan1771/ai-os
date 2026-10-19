from __future__ import annotations

import shutil
import re
import time
import subprocess
import json
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranscriptionResult:
    ok: bool
    text: str
    error: str = ""
    detected_language: str | None = None


class WhisperCppTranscriber:
    """Minimal, shell-free adapter for a locally installed whisper.cpp CLI."""

    def __init__(
        self, executable: str, model: Path, timeout_sec: int = 120, *, language: str = "auto",
        detect_language: bool = False,
    ) -> None:
        self.executable = executable
        self.model = model
        if language not in {"auto", "en", "hi"}:
            raise ValueError("Whisper language must be auto, en or hi")
        self.language = "auto" if detect_language else language
        self.detect_language = detect_language
        self.timeout_sec = max(1, min(180, timeout_sec))

    def availability(self) -> tuple[bool, str]:
        if (self.language == "hi" or self.detect_language) and ".en" in self.model.name:
            return False, "Hindi/language matching requires a multilingual Whisper model, not an .en model."
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

        started = time.monotonic()
        # Match mode reads Whisper's actual result.language, never a script guess
        # or the requested params.language. Private temporary JSON is always removed.
        temporary = tempfile.TemporaryDirectory(prefix="regenos-stt-") if self.detect_language else nullcontext(None)
        with temporary as directory:
            output = Path(directory) / "result" if directory else None
            argv = [
                    self.executable,
                    "-m",
                    str(self.model),
                    "-f",
                    str(audio_file),
                    "-nt",
                    "-l",
                    self.language,
            ]
            if self.detect_language:
                argv.extend(["-oj", "-of", str(output)])
            try:
                result = subprocess.run(
                    argv, capture_output=True, check=False, text=True,
                    timeout=self.timeout_sec,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return TranscriptionResult(False, "", str(exc))
            language = None
            text = result.stdout.strip()
            if result.returncode == 0 and self.detect_language:
                try:
                    report_path = output.with_suffix(".json")
                    if report_path.stat().st_size > 2_000_000:
                        raise ValueError("Whisper metadata is too large")
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    if report.get("model", {}).get("multilingual") is not True:
                        raise ValueError("Language matching requires a multilingual Whisper model")
                    segments = report["transcription"]
                    if not isinstance(segments, list) or not all(
                        isinstance(segment, dict) and isinstance(segment.get("text"), str)
                        for segment in segments
                    ):
                        raise ValueError("Invalid Whisper transcription metadata")
                    text = "".join(segment["text"] for segment in segments).strip()
                    detected = report.get("result", {}).get("language")
                    language = detected if detected in {"en", "hi"} else None
                except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                    return TranscriptionResult(False, "", f"Whisper language metadata unavailable: {exc}")
        if result.returncode != 0:
            return TranscriptionResult(False, "", result.stderr.strip() or "Whisper failed.")
        self.last_duration_sec = round(time.monotonic() - started, 3)
        # Whisper non-speech markers must never turn into a conversation or command.
        text = re.sub(r"(?i)\[(?:blank_audio|silence|music|applause|inaudible)\]", "", text).strip()
        return TranscriptionResult(bool(text), text, "" if text else "No speech recognized", language)
