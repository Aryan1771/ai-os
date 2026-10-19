"""Exclusive local speech/conversation ownership between resident processes."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def speech_lease(home: Path):
    """Yield False immediately when another utterance owns speech; never wait.

    Linux flock releases ownership on process exit, so a stale lock file cannot
    leave speech permanently disabled. This is coordination, not authorization.
    Unsupported platforms fail closed instead of pretending to share a lock.
    """
    try:
        import fcntl
    except ImportError:
        yield False
        return
    directory = home / "run"
    directory.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        directory / "speech.lock",
        os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    acquired = False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            pass
        yield acquired
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
