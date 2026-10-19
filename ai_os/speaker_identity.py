"""Optional local speaker matching; never an authentication or approval mechanism.

Only normalized embeddings are persisted. Recordings are supplied by the caller and
must be ephemeral. A recording/replayed voice can pass this filter.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import importlib.util
import json
import math
import os
import stat
import sys
import tempfile
import threading
import wave
from pathlib import Path
from typing import Callable, Iterable

from ai_os.config import AI_OS_HOME, load_raw_config

PROFILE_NAME = "speaker-profile.json"


def profile_path(home: Path) -> Path:
    return Path(home) / "data" / "private" / "speaker" / PROFILE_NAME
MAX_DIMENSION = 2048
MAX_MODEL_BYTES = 1024 * 1024 * 1024
MAX_AUDIO_SECONDS = 150
ENROLLMENT_SAMPLES = 4
_ENGINE_CACHE: dict[tuple[str, str], object] = {}
_HASH_CACHE: dict[tuple[object, ...], str] = {}
_LOCK = threading.RLock()


class SpeakerError(ValueError):
    """A safe, user-facing speaker setup error."""


def normalized(values: Iterable[float]) -> list[float]:
    vector = [float(value) for value in values]
    if not 16 <= len(vector) <= MAX_DIMENSION or not all(math.isfinite(v) for v in vector):
        raise SpeakerError("The speaker embedding has an invalid shape or values.")
    norm = math.sqrt(sum(v * v for v in vector))
    if norm < 1e-9 or not math.isfinite(norm):
        raise SpeakerError("The speaker embedding is empty.")
    return [v / norm for v in vector]


def similarity(first: Iterable[float], second: Iterable[float]) -> float:
    a, b = normalized(first), normalized(second)
    if len(a) != len(b):
        raise SpeakerError("Speaker profile and model dimensions do not match.")
    return max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))


def model_digest(model: Path) -> str:
    model = Path(model).expanduser()
    try:
        info = model.stat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_MODEL_BYTES:
            raise SpeakerError("Choose a local speaker ONNX model smaller than 1 GiB.")
        key = (str(model.resolve()), info.st_dev, info.st_ino, info.st_size,
               info.st_mtime_ns, info.st_ctime_ns)
        with _LOCK:
            if key not in _HASH_CACHE:
                digest = hashlib.sha256()
                with model.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                _HASH_CACHE.clear()
                _HASH_CACHE[key] = digest.hexdigest()
            return _HASH_CACHE[key]
    except OSError as exc:
        raise SpeakerError("The local speaker model cannot be read.") from exc


def backend_available() -> bool:
    return (importlib.util.find_spec("sherpa_onnx") is not None
            and importlib.util.find_spec("numpy") is not None)


def read_wave(path: Path):
    """Read bounded 16 kHz, mono, 16-bit PCM, rejecting empty/silent audio."""
    try:
        with wave.open(str(path), "rb") as source:
            frames = source.getnframes()
            if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
                raise SpeakerError("Speaker samples must be 16 kHz mono, 16-bit PCM WAV.")
            if not 16000 <= frames <= 16000 * MAX_AUDIO_SECONDS:
                raise SpeakerError("Record between one and 150 seconds of speech.")
            data = source.readframes(frames)
        if len(data) != frames * 2:
            raise SpeakerError("The recording is incomplete.")
        samples = array.array("h")
        samples.frombytes(data)
        if sys.byteorder != "little":
            samples.byteswap()
        rms = math.sqrt(sum(float(v) ** 2 for v in samples) / len(samples))
        if rms < 80 or sum(abs(v) > 200 for v in samples) < 1600:
            raise SpeakerError("No clear speech was recorded. Check the microphone and try again.")
        if sum(abs(v) >= 32760 for v in samples) > len(samples) * .05:
            raise SpeakerError("The microphone is clipping. Lower its level and retry.")
        return samples
    except (OSError, EOFError, wave.Error) as exc:
        raise SpeakerError("The speaker recording could not be read.") from exc


class SpeakerEncoder:
    """CPU-only neural embedding extractor using the optional sherpa-onnx API."""
    def __init__(self, model: Path):
        self.model = Path(model).expanduser()
        self.digest = model_digest(self.model)
        if not backend_available():
            raise SpeakerError("Optional sherpa-onnx and numpy are missing from the venv; nothing was downloaded.")
        try:
            import sherpa_onnx
            config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(self.model), num_threads=2, debug=False, provider="cpu")
            if not config.validate():
                raise SpeakerError("This file is not a supported speaker embedding ONNX model.")
            self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
        except SpeakerError:
            raise
        except Exception as exc:
            raise SpeakerError("The local speaker embedding model could not be loaded.") from exc
        self.lock = threading.Lock()

    def __call__(self, audio_path: Path) -> list[float]:
        import numpy as np
        samples = np.asarray(read_wave(audio_path), dtype=np.float32) / 32768.0
        try:
            with self.lock:
                stream = self.extractor.create_stream()
                stream.accept_waveform(sample_rate=16000, waveform=samples)
                stream.input_finished()
                if not self.extractor.is_ready(stream):
                    raise SpeakerError("The sample did not contain enough speech for speaker matching.")
                return normalized(self.extractor.compute(stream))
        except SpeakerError:
            raise
        except Exception as exc:
            raise SpeakerError("Speaker matching could not process the sample.") from exc


def encoder_for(model: Path) -> SpeakerEncoder:
    key = (str(Path(model).expanduser().resolve()), model_digest(model))
    with _LOCK:
        if key not in _ENGINE_CACHE:
            _ENGINE_CACHE.clear()
            _ENGINE_CACHE[key] = SpeakerEncoder(model)
        return _ENGINE_CACHE[key]


def _private_home(home: Path, *, create: bool = False):
    home = Path(home)
    for directory in (home, home / "data", home / "data" / "private", profile_path(home).parent):
        if create:
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or directory.is_symlink()):
            raise SpeakerError("Speaker storage must be an owned, private directory.")
    # Never chmod an existing directory with potentially unrelated data.
    if profile_path(home).parent.stat().st_mode & 0o077:
        raise SpeakerError("Private speaker storage must have permissions 0700 before enrollment.")


def load_profile(home: Path) -> dict:
    path = profile_path(home)
    try:
        _private_home(home)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_size > 65536):
                raise SpeakerError("Speaker profile is not a private, valid file.")
            profile = json.load(stream)
        if (not isinstance(profile, dict) or profile.get("version") != 1
                or profile.get("samples") != ENROLLMENT_SAMPLES
                or not isinstance(profile.get("model_sha256"), str)
                or len(profile["model_sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in profile["model_sha256"])):
            raise SpeakerError("The speaker profile is invalid; enroll again.")
        profile["embedding"] = normalized(profile["embedding"])
        return profile
    except SpeakerError:
        raise
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise SpeakerError("No valid private speaker profile is available; enroll again.") from exc


def delete_profile(home: Path = AI_OS_HOME) -> None:
    """Explicit native user action only. An enabled filter will subsequently deny."""
    path = profile_path(home)
    try:
        if not path.parent.exists():
            return
        _private_home(home)
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise SpeakerError("The speaker profile could not be deleted.") from exc


class Enrollment:
    """Injectable enrollment core: four diverse samples plus held-out verification."""
    def __init__(self, model_sha256: str, threshold: float = .75,
                 encoder: Callable[[Path], Iterable[float]] | None = None):
        if len(model_sha256) != 64 or any(c not in "0123456789abcdef" for c in model_sha256):
            raise SpeakerError("The speaker model identity is invalid.")
        if not .4 <= threshold <= .95:
            raise SpeakerError("Choose a speaker similarity threshold between 0.40 and 0.95.")
        self.digest, self.threshold, self.encoder = model_sha256, threshold, encoder
        self.samples: list[list[float]] = []
        self.verified = False

    def add(self, embedding: Iterable[float]) -> None:
        if len(self.samples) >= ENROLLMENT_SAMPLES:
            raise SpeakerError("Enrollment samples are already complete.")
        candidate = normalized(embedding)
        if self.samples and similarity(self.centroid(), candidate) < self.threshold:
            raise SpeakerError("This sample differs from the earlier voice. Retry in a quiet place.")
        self.samples.append(candidate)
        self.verified = False

    def add_audio(self, path: Path) -> None:
        if self.encoder is None:
            raise SpeakerError("No speaker encoder was supplied.")
        self.add(self.encoder(path))

    def centroid(self) -> list[float]:
        if not self.samples:
            raise SpeakerError("Record enrollment samples first.")
        return normalized(sum(items) for items in zip(*self.samples))

    def verify(self, embedding: Iterable[float]) -> bool:
        if len(self.samples) != ENROLLMENT_SAMPLES:
            raise SpeakerError("Complete all four samples before verification.")
        self.verified = similarity(self.centroid(), embedding) >= self.threshold
        return self.verified

    def save(self, home: Path) -> None:
        if not self.verified:
            raise SpeakerError("A separate successful verification recording is required.")
        _private_home(home, create=True)
        profile = {"version": 1, "model_sha256": self.digest,
                   "samples": len(self.samples), "embedding": self.centroid()}
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix=".speaker-profile-", dir=profile_path(home).parent)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(profile, stream, separators=(",", ":"), allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, profile_path(home))
        except OSError as exc:
            raise SpeakerError("The private speaker profile could not be saved.") from exc
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


def speaker_status(home: Path = AI_OS_HOME) -> tuple[bool, str]:
    try:
        config = load_raw_config(home)
        model = Path(config.get("speaker_model", "")).expanduser()
        if not config.get("speaker_model"):
            raise SpeakerError("Choose a local speaker embedding ONNX model first.")
        digest = model_digest(model)
        if not backend_available():
            raise SpeakerError("Optional sherpa-onnx and numpy are not installed in this venv.")
        profile = load_profile(home)
        if profile["model_sha256"] != digest:
            raise SpeakerError("The model changed. Enroll again with the selected model.")
        return True, "Local speaker profile is ready; this is not authentication."
    except (SpeakerError, OSError, ValueError):
        return False, "Speaker setup is incomplete: check the local model, optional backend and private profile."


def speaker_allowed(audio_path: Path, home: Path = AI_OS_HOME) -> tuple[bool, str]:
    try:
        config = load_raw_config(home)
        if not config.get("speaker_recognition_enabled", False):
            return True, "Speaker filtering is off."
        if not config.get("speaker_model"):
            raise SpeakerError("Speaker filtering is on but no model is configured.")
        model = Path(config["speaker_model"]).expanduser()
        profile = load_profile(home)
        if profile["model_sha256"] != model_digest(model):
            raise SpeakerError("The speaker model changed; enrollment is required.")
        threshold = float(config.get("speaker_threshold", .75))
        if not math.isfinite(threshold) or not .4 <= threshold <= .95:
            raise SpeakerError("The speaker threshold is invalid.")
        vector = encoder_for(model)(audio_path)
        if similarity(profile["embedding"], vector) < threshold:
            return False, "The voice did not match the local speaker profile."
        return True, "The voice matched the local conversation filter; this is not authorization."
    except Exception:
        # Deny on backend/profile/model/audio failure without leaking private paths/logs.
        return False, "Speaker filtering could not verify this recording. Check setup or disable the filter in Settings."


def main() -> int:
    """Bounded-by-caller extraction/check worker; never records or downloads."""
    parser = argparse.ArgumentParser(description="Local speaker embedding worker")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--extract", nargs=2, metavar=("MODEL", "WAV"))
    operation.add_argument("--check", type=Path, metavar="WAV")
    parser.add_argument("--home", type=Path, default=AI_OS_HOME)
    args = parser.parse_args()
    if args.check is not None:
        # Verification workers return only admission and a fixed public code.
        # Unlike --extract, this path never emits embeddings or model identity.
        try:
            ready, _message = speaker_status(args.home)
            if ready:
                allowed, _message = speaker_allowed(args.check, args.home)
                code = "speaker_matched" if allowed else "speaker_rejected"
            else:
                allowed, code = False, "speaker_unavailable"
        except Exception:
            allowed, code = False, "speaker_unavailable"
        print(json.dumps({"allowed": bool(allowed), "code": code}))
        return 0
    try:
        model, audio = map(Path, args.extract)
        encoder = encoder_for(model)
        vector = encoder(audio)
        print(json.dumps({"embedding": vector, "model_sha256": encoder.digest}, allow_nan=False))
        return 0
    except Exception:
        print(json.dumps({"error": "Speaker extraction failed; check the model, backend and microphone sample."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
