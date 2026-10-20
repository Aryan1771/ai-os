from __future__ import annotations

import shutil
import re
import time
import subprocess
import json
import os
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path


STT_ERRORS = {
    "transcriber_unavailable": "Whisper is unavailable. Check the local executable and selected model.",
    "audio_missing": "The temporary microphone recording is unavailable. Please record again.",
    "transcription_timeout": "Whisper transcription timed out. Check the local model size and processing load.",
    "transcription_failed": "Transcription failed in Whisper. Check the executable, multilingual model and selected language.",
    "transcription_storage": "Private transcription storage is unavailable. Check temporary-directory permissions and free space.",
    "language_metadata": "Whisper language metadata unavailable. Use a multilingual model and a CLI with JSON output support.",
    "transcription_script_mismatch": "Hindi was detected, but Whisper produced a different writing system. No request was submitted; repeat more clearly or use a more accurate multilingual model.",
}


def backend_selection(stderr: str) -> str:
    """Return fixed evidence from upstream initialization lines, never raw logs."""
    if not isinstance(stderr, str) or len(stderr) > 1_000_000:
        return "unknown"
    selected = set(re.findall(r"(?m)^whisper_backend_init_gpu:\s+using (CUDA\d+) backend\s*$", stderr))
    failed = set(re.findall(r"(?m)^whisper_backend_init_gpu:\s+failed to initialize (CUDA\d+) backend\s*$", stderr))
    buffers = re.findall(r"(?m)^whisper_model_load:\s+(CUDA\d+)\s+total size\s*=\s*(\d+(?:\.\d+)?) MB\s*$", stderr)
    if any(device in selected - failed and float(size) > 0 for device, size in buffers):
        return "cuda"
    if re.search(r"(?m)^whisper_backend_init_gpu:\s+no GPU found\s*$", stderr):
        return "cpu"
    return "unknown"


@dataclass(frozen=True)
class TranscriptionResult:
    ok: bool
    text: str
    error: str = ""
    detected_language: str | None = None
    error_code: str = ""


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
        self.last_duration_sec = None
        self.last_backend = "unknown"

    def availability(self) -> tuple[bool, str]:
        if (self.language == "hi" or self.detect_language) and ".en" in self.model.name:
            return False, "Hindi/language matching requires a multilingual Whisper model, not an .en model."
        if not shutil.which(self.executable):
            return False, "The selected Whisper executable is not installed or not on PATH."
        if not self.model.is_file():
            return False, "The selected local Whisper model is missing."
        return True, "ready"

    def transcribe_file(self, audio_file: Path) -> TranscriptionResult:
        self.last_duration_sec = None
        self.last_backend = "unknown"
        ready, reason = self.availability()
        if not ready:
            return TranscriptionResult(False, "", reason, error_code="transcriber_unavailable")
        if not audio_file.is_file():
            return self.failure("audio_missing")

        started = time.monotonic()
        # Match mode reads Whisper's actual result.language, never a script guess
        # or the requested params.language. Private temporary JSON is always removed.
        try:
            temporary = (tempfile.TemporaryDirectory(prefix="regenos-stt-", dir=os.environ.get("AI_OS_VOICE_TMP"))
                         if self.detect_language else nullcontext(None))
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
                        timeout=self.timeout_sec, shell=False, stdin=subprocess.DEVNULL,
                    )
                except OSError:
                    return self.failure("transcription_failed")
                if result.returncode != 0:
                    return self.failure("transcription_failed")
                self.last_backend = backend_selection(result.stderr)
                language = None
                text = result.stdout.strip()
                if self.detect_language:
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
                    except (OSError, ValueError, KeyError, TypeError, AttributeError):
                        return self.failure("language_metadata")
        except subprocess.TimeoutExpired:
            return self.failure("transcription_timeout")
        except OSError:
            return self.failure("transcription_storage")
        if len(text) > 20000:
            return self.failure("transcription_failed")
        if language == "hi" or self.language == "hi":
            # A known small-model failure is Hindi metadata with Urdu-script
            # output. Do not turn that unreliable transcript into commands or
            # guess a transliteration; ordinary Romanized Hindi remains valid.
            arabic_letters = len(re.findall(r"[\u0620-\u064a\u066e-\u06d3]", text))
            devanagari_letters = len(re.findall(r"[\u0900-\u097f]", text))
            if arabic_letters >= 3 and arabic_letters > devanagari_letters * 2:
                return self.failure("transcription_script_mismatch")
        self.last_duration_sec = round(time.monotonic() - started, 3)
        # Whisper non-speech markers must never turn into a conversation or command.
        text = re.sub(r"(?i)\[(?:blank_audio|silence|music|applause|inaudible)\]", "", text).strip()
        return TranscriptionResult(bool(text), text, "" if text else "No speech recognized", language)

    @staticmethod
    def failure(code: str) -> TranscriptionResult:
        return TranscriptionResult(False, "", STT_ERRORS[code], error_code=code)
