"""Short-lived native review inbox. Never a model-callable approval service."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import time

TOOLS = {"run_terminal_command", "research_topic", "cleanup_files", "power_action"}


def _canonical(proposal):
    if not isinstance(proposal, dict) or proposal.get("tool") not in TOOLS or not isinstance(proposal.get("arguments"), dict):
        raise ValueError("Unsupported pending action")
    value = {"tool": proposal["tool"], "arguments": proposal["arguments"]}
    encoded = json.dumps(value, sort_keys=True, allow_nan=False)
    if len(encoded) > 16384:
        raise ValueError("Pending action is too large")
    return encoded


def _connect(home):
    root = Path(home)
    for component in (None, "run", "private", "reviews"):
        root = root if component is None else root / component
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("Review storage must use owned directories without symlinks")
    if root.stat().st_mode & 0o077:
        raise ValueError("Review storage must be private")
    path = root / "pending.sqlite3"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("Unsafe review database")
    finally:
        os.close(descriptor)
    connection = sqlite3.connect(path, timeout=2)
    connection.execute("CREATE TABLE IF NOT EXISTS pending(session TEXT PRIMARY KEY, proposal TEXT, expires REAL)")
    return connection


def save(home, session, proposal):
    encoded = _canonical(proposal)
    if not isinstance(session, str) or not 1 <= len(session) <= 80:
        raise ValueError("Invalid review session")
    with closing(_connect(home)) as connection:
        connection.execute("DELETE FROM pending WHERE expires<?", (time.time(),))
        if connection.execute("SELECT COUNT(*) FROM pending").fetchone()[0] >= 64:
            raise ValueError("Pending review limit reached")
        connection.execute("INSERT OR REPLACE INTO pending VALUES(?,?,?)", (session, encoded, time.time() + 120))
        connection.commit()


def read(home, session):
    with closing(_connect(home)) as connection:
        row = connection.execute("SELECT proposal,expires FROM pending WHERE session=?", (session,)).fetchone()
    if not row or row[1] <= time.time():
        return None
    return json.loads(row[0])


def discard(home, session, proposal):
    """Clear only what was actually reviewed; preserve any newer queued request."""
    encoded = _canonical(proposal)
    with closing(_connect(home)) as connection:
        connection.execute("DELETE FROM pending WHERE session=? AND proposal=?", (session, encoded))
        connection.commit()
