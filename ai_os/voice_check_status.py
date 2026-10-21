"""Latest explicitly requested voice-check metadata; never audio or user text."""
from __future__ import annotations

import contextlib
import json
import math
import os
import secrets
import stat
import time
from pathlib import Path

from ai_os.config import AI_OS_HOME
from ai_os.services.voice_errors import VOICE_MESSAGES
from ai_os.voice_progress import PHASES, public_progress
from ai_os.voice_timings import public_timings

FILENAME = "voice-check-status.json"
LOCKNAME = ".voice-check-status.lock"
MAX_BYTES = 4096
MAX_AGE_SECONDS = 180
STATES = PHASES | {"completed", "failed", "cancelled"}
CODES = set(VOICE_MESSAGES) | {"", "voice_check_unavailable", "cancelled"}
FIELDS = {"version", "action", "phase", "code", "timings", "started_at", "updated_at"}


def _timestamp(value):
    return type(value) in (int, float) and 0 <= value <= 1e12 and math.isfinite(value)


def _checked(value):
    if (type(value) is not dict or set(value) != FIELDS or type(value.get("version")) is not int
            or value["version"] != 1 or value.get("action") not in ("play", "record")
            or type(value.get("phase")) is not str or value["phase"] not in STATES
            or type(value.get("code")) is not str or value["code"] not in CODES
            or type(value.get("timings")) is not dict
            or value["timings"] != public_timings(value["timings"])
            or not _timestamp(value.get("started_at")) or not _timestamp(value.get("updated_at"))
            or value["updated_at"] < value["started_at"]):
        raise ValueError("Invalid voice-check metadata")
    return value


def _owned(info, *, directory=False, private=True):
    if ((not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode))
            or info.st_uid != os.getuid() or info.st_mode & (0o077 if private else 0o022)
            or not directory and info.st_nlink != 1):
        raise ValueError("Unsafe voice-check metadata storage")


@contextlib.contextmanager
def _directory(home, *, create=False):
    descriptors = []
    try:
        descriptor = os.open(Path(home).expanduser().absolute(),
                             os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(descriptor)
        _owned(os.fstat(descriptor), directory=True, private=False)
        for name in ("run", "private"):
            if create:
                try:
                    os.mkdir(name, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                 dir_fd=descriptor)
            descriptors.append(descriptor)
            _owned(os.fstat(descriptor), directory=True, private=name == "private")
        yield descriptor
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@contextlib.contextmanager
def _lock(directory):
    import fcntl
    descriptor = os.open(LOCKNAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                         0o600, dir_fd=directory)
    try:
        _owned(os.fstat(descriptor))
        if os.fstat(descriptor).st_size > MAX_BYTES:
            raise ValueError("Invalid voice-check metadata lock")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def _read(directory):
    descriptor = os.open(FILENAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        _owned(info)
        if info.st_size > MAX_BYTES:
            raise ValueError("Oversized voice-check metadata")
        payload = stream.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("Oversized voice-check metadata")
    return _checked(json.loads(payload))


def _write(directory, value):
    data = json.dumps(_checked(value), ensure_ascii=True, allow_nan=False).encode()
    if len(data) > MAX_BYTES:
        raise ValueError("Oversized voice-check metadata")
    try:
        existing = os.stat(FILENAME, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        _owned(existing)
    temporary = ".voice-check-" + secrets.token_hex(8) + ".tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, FILENAME, src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary, dir_fd=directory)


class VoiceCheckStatus:
    def __init__(self, home, action):
        self.home, self.action, self.started_at = home, action, None
        if action not in ("play", "record"):
            return
        try:
            with _directory(home, create=True) as directory, _lock(directory):
                try:
                    previous = _read(directory)
                except FileNotFoundError:
                    previous = None
                now = time.time()
                self.started_at = max(now, previous["started_at"] + .000001) if previous else now
                _write(directory, self._value("preparing", "", {}, now))
        except (OSError, ValueError, UnicodeError, RecursionError):
            self.started_at = None

    def _value(self, phase, code, timings, now):
        return {"version": 1, "action": self.action, "phase": phase, "code": code,
                "timings": public_timings(timings), "started_at": self.started_at,
                "updated_at": max(now, self.started_at)}

    def publish(self, phase, *, code="", timings=None):
        if self.started_at is None or type(phase) is not str or phase not in STATES:
            return False
        code = code if type(code) is str and code in CODES else "capture_failed"
        try:
            with _directory(self.home) as directory, _lock(directory):
                current = _read(directory)
                if current["started_at"] != self.started_at or current["action"] != self.action:
                    return False  # A superseded worker cannot overwrite the next check.
                _write(directory, self._value(phase, code, timings, time.time()))
            return True
        except (OSError, ValueError, UnicodeError, RecursionError):
            return False

    def progress(self, event):
        event = public_progress(event)
        return self.publish(event["phase"]) if event is not None else False


def read_status(home=AI_OS_HOME, *, now=None, max_age=MAX_AGE_SECONDS):
    """Bounded read-only public metadata; never return raw file/error content."""
    try:
        if not _timestamp(max_age) or not 0 < max_age <= MAX_AGE_SECONDS:
            raise ValueError("Invalid metadata freshness limit")
        with _directory(home) as directory:
            value = _read(directory)
        now = time.time() if now is None else now
        if not _timestamp(now):
            raise ValueError("Invalid metadata clock")
        age = now - value["updated_at"]
        if age < -1:
            raise ValueError("Future metadata")
        return {"status": "fresh", **value} if age <= max_age else {"status": "stale"}
    except (OSError, ValueError, UnicodeError, RecursionError):
        return {"status": "unavailable"}


def main():
    print(json.dumps(read_status(), ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
