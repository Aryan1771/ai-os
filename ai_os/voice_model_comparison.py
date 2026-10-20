"""Local synthetic English/Hindi STT comparison. Never records, plays or downloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import wave

from ai_os.command_runner import run_bounded
from ai_os.config import AI_OS_HOME, load_config
from ai_os.services.stt import TranscriptionResult, WhisperCppTranscriber, backend_selection

PHRASES = {
    "en": "Please tell me about the new display.",
    "hi": "कृपया नए मॉनिटर के बारे में बताइए।",
}
HINDI_HINT = "हिन्दी भाषा, देवनागरी लिपि।"
ADDITIONAL_HINDI = (
    "नमस्ते, आज का दिन अच्छा है।",
    "मुझे अपने काम की तैयारी करनी है।",
    "कृपया मुझे आज का मौसम बताइए।",
)
CUDA_SOURCE_COMMIT = "d1be6fde11ac6e0407606b4e42fe72d34add8037"
MAX_MODEL_BYTES = 3 * 1024**3
MAX_SECONDS = 180


class ComparisonError(ValueError):
    pass


def normalize(text):
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(ch if ch.isspace() or unicodedata.category(ch)[0] in "LMN" else " "
                             for ch in normalized).split())


def distance(first, second):
    previous = list(range(len(second) + 1))
    for row, left in enumerate(first, 1):
        current = [row]
        for column, right in enumerate(second, 1):
            current.append(min(previous[column] + 1, current[-1] + 1,
                               previous[column - 1] + (left != right)))
        previous = current
    return previous[-1]


def correctness(reference, transcript):
    if not isinstance(transcript, str) or len(transcript) > 20000:
        raise ComparisonError("The synthetic transcription was invalid or excessive.")
    expected, actual = normalize(reference), normalize(transcript)
    words = expected.split()
    characters = expected.replace(" ", "")
    return {"normalized_exact_match": expected == actual,
            "word_error_rate": round(distance(words, actual.split()) / max(1, len(words)), 4),
            "character_error_rate": round(distance(characters, actual.replace(" ", "")) / max(1, len(characters)), 4)}


def installed_asset(path, home, *, suffix, maximum):
    """Only regular, locally owned/root-owned assets inside this runtime's models."""
    candidate = Path(path).expanduser().absolute()
    root = Path(home).expanduser().absolute()
    models = root / "models"
    if (not candidate.is_relative_to(models) or ".." in candidate.parts or candidate.suffix != suffix
            or not candidate.name or any(ord(ch) < 32 for ch in str(candidate))):
        raise ComparisonError("Choose an existing model inside the runtime models directory.")
    for part in (root, models):
        if part.is_symlink():
            raise ComparisonError("Model paths and their directories must not be symlinks.")
    current = candidate
    while current != root:
        if current.is_symlink():
            raise ComparisonError("Model paths and their directories must not be symlinks.")
        current = current.parent
    info = candidate.stat()
    if not candidate.is_file() or info.st_uid not in {0, os.getuid()} or not 0 < info.st_size <= maximum:
        raise ComparisonError("The existing model asset is unavailable or has an unsupported size.")
    if suffix == ".bin":
        with candidate.open("rb") as stream:
            if stream.read(4) != b"lmgg":
                raise ComparisonError("The selected file is not a GGML Whisper model.")
    return candidate


def digest(path, deadline):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if time.monotonic() > deadline:
                raise ComparisonError("Comparison reached its total time limit.")
            checksum.update(chunk)
    return checksum.hexdigest()


def execute(argv, directory, deadline, timeout=35):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ComparisonError("Comparison reached its total time limit.")
    try:
        result = run_bounded(argv, cwd=str(directory), timeout=min(timeout, remaining), output_limit=65536)
    except (OSError, subprocess.SubprocessError):
        raise ComparisonError("A comparison subprocess failed or timed out; no raw backend output was retained.") from None
    if result.returncode:
        raise ComparisonError("A comparison subprocess failed; no raw backend output was retained.")
    return result.stdout


def audio_duration(path, *, rate=None):
    if path.is_symlink() or not 0 < path.stat().st_size <= 4 * 1024**2:
        raise ComparisonError("Synthetic audio exceeded its private file limit.")
    with wave.open(str(path), "rb") as source:
        actual_rate = source.getframerate()
        frames = source.getnframes()
        if (source.getnchannels() != 1 or source.getsampwidth() != 2
                or not 8000 <= actual_rate <= 192000 or rate is not None and rate != actual_rate
                or not 0 < frames <= actual_rate * 30):
            raise ComparisonError("The generated synthetic WAV has an unsupported format or duration.")
        return round(frames / actual_rate, 3)


class GpuSamples:
    """Bounded whole-device samples; never process names, command lines or logs."""
    def __init__(self):
        self.samples = []
        self.failures = 0
        self.stop = threading.Event()
        self.thread = None

    def sample(self):
        try:
            result = run_bounded(["/usr/bin/nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                 cwd="/", timeout=1, output_limit=1024)
            values = [int(line) for line in result.stdout.splitlines()]
            if result.returncode or not 1 <= len(values) <= 16 or any(v < 0 for v in values):
                raise ValueError
            self.samples.append(values)
        except (OSError, ValueError, subprocess.SubprocessError):
            self.failures += 1

    def __enter__(self):
        if Path("/usr/bin/nvidia-smi").is_file():
            self.sample()
            def collect():
                while not self.stop.wait(.2) and len(self.samples) + self.failures < 1000:
                    self.sample()
            self.thread = threading.Thread(target=collect, daemon=True)
            self.thread.start()
        return self

    def __exit__(self, *_args):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=3)

    def report(self):
        consistent = self.samples and all(len(sample) == len(self.samples[0]) for sample in self.samples)
        return {"sample_count": len(self.samples), "sampling_failures": self.failures,
                "baseline_mib_by_device": self.samples[0] if self.samples else [],
                "sampled_peak_mib_by_device": [max(values) for values in zip(*self.samples)] if consistent else [],
                "scope": "Whole-device memory during sequential Piper/STT only; includes existing allocations, excludes Ollama inference/playback and is not a simultaneous peak."}


def installed_executables():
    piper = Path(sys.executable).with_name("piper")
    if not piper.is_file() or piper.is_symlink() or not Path("/usr/bin/ffmpeg").is_file() or not Path("/usr/bin/whisper-cli").is_file():
        raise ComparisonError("The existing venv Piper, system FFmpeg and system Whisper CLI are required.")
    return str(piper)


def validated_cli(candidate, home, deadline):
    if candidate is None:
        return "/usr/bin/whisper-cli", {"kind": "installed_system_cli"}
    path = Path(candidate).expanduser().absolute()
    root = Path(home).expanduser().absolute() / "build"
    if not path.is_relative_to(root) or ".." in path.parts:
        raise ComparisonError("A candidate CLI must be an explicitly verified private REgenOS CUDA build.")
    parts = path.relative_to(root).parts
    if (len(parts) != 4 or parts[1:] != ("build", "bin", "whisper-cli")
            or re.fullmatch(r"whisper-cpp-v1\.9\.5-cuda-d1be6fde-[a-z0-9_]+", parts[0]) is None):
        raise ComparisonError("The candidate CLI is outside the expected verified build layout.")
    current = path
    while current != root.parent:
        if current.is_symlink():
            raise ComparisonError("Candidate CLI paths must not contain symlinks.")
        current = current.parent
    workspace = root / parts[0]
    if workspace.stat().st_mode & 0o077 or not path.is_file() or path.stat().st_mode & 0o022 or not os.access(path, os.X_OK):
        raise ComparisonError("The candidate CLI build is not private or executable.")
    with path.open("rb") as stream:
        if stream.read(4) != b"\x7fELF":
            raise ComparisonError("The candidate CLI is not a compiled local ELF executable.")
    manifest_path = workspace / "regenos-build.json"
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > 65536 or manifest_path.stat().st_mode & 0o077:
        raise ComparisonError("The candidate CLI has no valid private build manifest.")
    manifest = json.loads(manifest_path.read_text())
    if (not isinstance(manifest, dict) or manifest.get("schema") != 1
            or manifest.get("source_url") != "https://github.com/ggml-org/whisper.cpp"
            or manifest.get("source_commit") != CUDA_SOURCE_COMMIT
            or manifest.get("source_tag") != "v1.9.5" or manifest.get("whisper_cli") != str(path)
            or manifest.get("whisper_cli_sha256") != digest(path, deadline)):
        raise ComparisonError("The candidate CLI does not match the verified upstream build manifest.")
    return str(path), {"kind": "verified_local_cuda_build", "source_commit": CUDA_SOURCE_COMMIT,
                       "sha256": manifest["whisper_cli_sha256"]}


def compare(models=None, *, home=AI_OS_HOME, script_hint=False, additional_hindi=False, whisper_cli=None):
    config = load_config(home)
    deadline = time.monotonic() + MAX_SECONDS
    candidates = [Path(path) for path in models] if models is not None else [config.whisper_model]
    if not 1 <= len(candidates) <= 3 or len(set(map(str, candidates))) != len(candidates):
        raise ComparisonError("Choose one to three distinct existing Whisper models.")
    candidates = [installed_asset(path, home, suffix=".bin", maximum=MAX_MODEL_BYTES) for path in candidates]
    if len(set(candidates)) != len(candidates):
        raise ComparisonError("Choose distinct existing Whisper model paths.")
    if not all(re.fullmatch(r"ggml-[A-Za-z0-9_.-]+\.bin", model.name) for model in candidates):
        raise ComparisonError("Only existing ggml Whisper model filenames are accepted.")
    voices = {"en": config.piper_model, "hi": config.piper_hindi_model}
    manifests = []
    for language, model in voices.items():
        if model is None:
            raise ComparisonError("Both installed Piper voices are required; no download was attempted.")
        model = installed_asset(model, home, suffix=".onnx", maximum=MAX_MODEL_BYTES)
        metadata = installed_asset(Path(str(model) + ".json"), home, suffix=".json", maximum=131072)
        voice_config = json.loads(metadata.read_text())
        if not str(voice_config.get("language", {}).get("code", "")).startswith(language + "_"):
            raise ComparisonError("The configured Piper voice language does not match this synthetic check.")
        voices[language] = model
        manifests.append({"language": language, "filename": model.name, "bytes": model.stat().st_size,
                          "sha256": digest(model, deadline), "config_sha256": digest(metadata, deadline),
                          "sample_rate": voice_config.get("audio", {}).get("sample_rate")})
    piper = installed_executables()
    executable, executable_info = validated_cli(whisper_cli, home, deadline)
    model_info = [{"filename": model.name, "bytes": model.stat().st_size, "sha256": digest(model, deadline)} for model in candidates]
    rows, synthesis = [], []
    with GpuSamples() as gpu, tempfile.TemporaryDirectory(prefix="regenos-model-compare-") as temporary:
        directory = Path(temporary)
        inputs = [(language, 0, phrase) for language, phrase in PHRASES.items()]
        if additional_hindi:
            inputs.extend(("hi", index, phrase) for index, phrase in enumerate(ADDITIONAL_HINDI, 1))
        for language, sample, phrase in inputs:
            name = language + ("-" + str(sample) if sample else "")
            source = directory / (name + ".txt")
            source.write_text(phrase, encoding="utf-8")
            source.chmod(0o600)
            original, resampled = directory / (name + ".wav"), directory / (name + "-16k.wav")
            started = time.monotonic()
            execute([piper, "--model", str(voices[language]), "--input_file", str(source), "--output_file", str(original)], directory, deadline)
            synthesis_seconds = round(time.monotonic() - started, 3)
            audio_duration(original)
            started = time.monotonic()
            execute(["/usr/bin/ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-i", str(original),
                     "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(resampled)], directory, deadline, timeout=10)
            synthesis.append({"language": language, "sample": sample, "reference": phrase, "piper_seconds": synthesis_seconds,
                              "resample_seconds": round(time.monotonic() - started, 3), "audio_seconds": audio_duration(resampled, rate=16000)})
            for model in candidates:
                for mode in (["selected", "match", "script_hint"] if script_hint and language == "hi" else ["selected", "match"]):
                    started = time.monotonic()
                    argv = [sys.executable, "-m", "ai_os.voice_model_comparison", "--worker", "--model", str(model),
                            "--audio", str(resampled), "--language", language, "--mode", mode, "--sample", str(sample), "--home", str(home)]
                    if whisper_cli is not None:
                        argv.extend(["--whisper-cli", executable])
                    raw = execute(argv, directory, deadline, timeout=45)
                    result = json.loads(raw)
                    if not isinstance(result, dict) or set(result) != {"accepted", "detected_language", "error_code", "correctness", "backend"}:
                        raise ComparisonError("The synthetic worker returned an unsupported result.")
                    rows.append({"model": model.name, "language": language, "sample": sample, "mode": mode,
                                 "stt_worker_seconds": round(time.monotonic() - started, 3), **result})
    return {"ok": True, "synthetic_only": True, "microphone_opened": False, "audible_playback": False,
            "settings_changed": False, "downloads": False, "whisper_cli": executable_info,
            "whisper_models": model_info, "piper_voices": manifests,
            "synthesis": synthesis, "results": rows, "gpu": gpu.report(),
            "elapsed_seconds": round(MAX_SECONDS - (deadline - time.monotonic()), 3),
            "limits": "Fixed synthetic phrases only; one cold process per mode/model/sample. Rates normalize punctuation/case and CER removes spaces. Rejected transcripts have no WER/CER. No microphone, speaker identity, wake, code-switching or general accuracy acceptance."}


def worker(model, audio, language, mode, home, *, sample=0, whisper_cli=None):
    model = installed_asset(model, home, suffix=".bin", maximum=MAX_MODEL_BYTES)
    audio = Path(audio)
    if language not in PHRASES or type(sample) is not int or not 0 <= sample <= len(ADDITIONAL_HINDI) or language == "en" and sample:
        raise ComparisonError("Choose an existing fixed synthetic phrase.")
    reference = PHRASES[language] if sample == 0 else ADDITIONAL_HINDI[sample - 1]
    name = language + ("-" + str(sample) if sample else "")
    executable, _info = validated_cli(whisper_cli, home, time.monotonic() + 40)
    if (audio.is_symlink() or not audio.parent.name.startswith("regenos-model-compare-")
            or audio.parent.is_symlink() or audio.parent.stat().st_mode & 0o077 or audio.parent.stat().st_uid != os.getuid()
            or audio.name != name + "-16k.wav"):
        raise ComparisonError("Only the private synthetic comparison WAV can be processed.")
    audio_duration(audio, rate=16000)
    backend = "unknown"
    if mode == "script_hint":
        if language != "hi":
            raise ComparisonError("The script-hint comparison is Hindi only.")
        report_base = audio.parent / "hint-result"
        process = subprocess.run([executable, "-m", str(model), "-f", str(audio), "-nt", "-l", "hi",
                                  "--prompt", HINDI_HINT, "-oj", "-of", str(report_base)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                 timeout=40, shell=False, check=False)
        path = report_base.with_suffix(".json")
        if process.returncode or not path.is_file() or path.stat().st_size > 2_000_000:
            raise ComparisonError("The isolated Hindi hint comparison failed.")
        report = json.loads(path.read_text())
        backend = backend_selection(process.stderr.decode(errors="replace"))
        if report.get("model", {}).get("multilingual") is not True:
            raise ComparisonError("The isolated Hindi hint comparison requires a multilingual model.")
        text = "".join(segment["text"] for segment in report["transcription"]).strip()
        text = re.sub(r"(?i)\[(?:blank_audio|silence|music|applause|inaudible)\]", "", text).strip()
        arabic_letters = len(re.findall(r"[\u0620-\u064a\u066e-\u06d3]", text))
        devanagari_letters = len(re.findall(r"[\u0900-\u097f]", text))
        accepted = bool(text) and not (arabic_letters >= 3 and arabic_letters > devanagari_letters * 2)
        result = TranscriptionResult(accepted, text if accepted else "", detected_language=None,
                                     error_code="" if accepted else "transcription_script_mismatch")
        path.unlink(missing_ok=True)
    else:
        # Keep any Whisper metadata inside the directory the parent removes even
        # after timeout/SIGKILL; this worker never touches listening preferences.
        os.environ["AI_OS_VOICE_TMP"] = str(audio.parent)
        transcriber = WhisperCppTranscriber(executable, model, timeout_sec=40,
                                           language=language, detect_language=mode == "match")
        result = transcriber.transcribe_file(audio)
        backend = getattr(transcriber, "last_backend", "unknown")
    return {"accepted": result.ok, "detected_language": result.detected_language, "error_code": result.error_code,
            "backend": backend,
            "correctness": correctness(reference, result.text) if result.ok else {
                "normalized_exact_match": False, "word_error_rate": None, "character_error_rate": None}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", type=Path)
    parser.add_argument("--home", type=Path, default=AI_OS_HOME)
    parser.add_argument("--script-hint", action="store_true", help="Also compare a fixed Hindi script context; never change runtime settings")
    parser.add_argument("--additional-hindi", action="store_true", help="Compare three additional fixed Hindi phrases")
    parser.add_argument("--whisper-cli", type=Path, help="Explicit CLI from a verified private CUDA build; never select it in runtime settings")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--audio", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--language", choices=("en", "hi"), help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=("selected", "match", "script_hint"), help=argparse.SUPPRESS)
    parser.add_argument("--sample", type=int, choices=range(4), default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.worker:
            if not args.model or len(args.model) != 1 or args.audio is None or args.language is None or args.mode is None:
                raise ComparisonError("Invalid isolated synthetic worker request.")
            result = worker(args.model[0], args.audio, args.language, args.mode, args.home,
                            sample=args.sample, whisper_cli=args.whisper_cli)
        else:
            result = compare(args.model, home=args.home, script_hint=args.script_hint,
                             additional_hindi=args.additional_hindi, whisper_cli=args.whisper_cli)
    except (ComparisonError, OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError, wave.Error):
        result = {"ok": False, "message": "Local synthetic comparison could not complete. Check existing model assets and executable readiness; no downloads, recordings or settings changes occurred."}
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
