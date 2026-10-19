"""Previewed, recoverable file cleanup with explicitly remembered narrow rules.

This is a same-account application policy, not a filesystem sandbox. It never
permanently deletes, recurses, removes directories, or calls sudo.
"""
from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import subprocess
import time
from contextlib import closing

from ai_os.config import AI_OS_HOME

MAX_FILES = 200
MAX_BYTES = 1024 ** 3
PREVIEW_SECONDS = 120
RULE_SECONDS = 30 * 86400
RULE_USES = 20
PROTECTED_NAMES = {"bin", "sbin", "lib", "lib64", "venv", "site-packages", "node_modules"}


def requested_by_user(text):
    """Conservative action gate; models still choose the paths and patterns."""
    return bool(re.search(r"\b(delete|remove|trash|clean|clear|declutter)\b|हटा|मिटा|साफ", text, re.IGNORECASE))


def _storage(home):
    root = Path(home).expanduser().absolute()
    for part in (None, "run", "private", "cleanup"):
        root = root if part is None else root / part
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("Cleanup storage must be an owned directory without symlinks")
    if root.stat().st_mode & 0o077:
        raise ValueError("Cleanup storage must be private (0700)")
    return root


def _db(home):
    path = _storage(home) / "rules.sqlite3"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("Unsafe cleanup permission database")
    finally:
        os.close(descriptor)
    connection = sqlite3.connect(path, timeout=2)
    connection.execute("CREATE TABLE IF NOT EXISTS rules (directory TEXT, pattern TEXT, expires REAL, uses INTEGER, max_files INTEGER, max_bytes INTEGER, device INTEGER, inode INTEGER, PRIMARY KEY(directory,pattern))")
    return connection


def _directory(value):
    if not isinstance(value, str) or not value.isprintable() or len(value) > 4096:
        raise ValueError("Choose an explicit local directory")
    path = Path(value).expanduser().absolute()
    user_home = Path.home().resolve()
    if path == user_home or not path.is_relative_to(user_home):
        raise ValueError("Cleanup is limited to a selected directory below your home")
    # Inspect every component before resolving: no hidden/system/runtime roots,
    # symlink traversal or source-controlled projects can become cleanup targets.
    for parent in (path, *path.parents):
        if parent == user_home:
            break
        if parent.name.startswith(".") or parent.name in PROTECTED_NAMES:
            raise ValueError("Hidden, application and runtime directories are protected")
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("Choose an owned directory without symlinks")
        if (parent / ".git").exists() or (parent / "pyvenv.cfg").exists():
            raise ValueError("Source repositories and Python environments need a separate manual review")
    return path.resolve(strict=True)


def _pattern(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:\*\.[A-Za-z0-9_-]{1,20}|[A-Za-z0-9][A-Za-z0-9 ._-]{0,119})", value):
        raise ValueError("Use an exact filename or a single extension pattern such as *.py")
    return value


def _scan(directory, pattern):
    path, pattern = _directory(directory), _pattern(pattern)
    files = []
    total = 0
    examined = 0
    for item in path.iterdir():
        examined += 1
        if examined > 10000:
            raise ValueError("Directory is too large; choose a smaller cleanup directory")
        if item.name.startswith(".") or not fnmatch.fnmatchcase(item.name, pattern):
            continue
        info = item.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise ValueError("Matching symlinks, directories and shared files are protected")
        files.append({"name": item.name, "size": info.st_size, "dev": info.st_dev,
                      "inode": info.st_ino, "mtime": info.st_mtime_ns, "ctime": info.st_ctime_ns})
        total += info.st_size
        if len(files) > MAX_FILES or total > MAX_BYTES:
            raise ValueError("Cleanup exceeds 200 files or 1 GiB; narrow the request")
    info = path.stat()
    return {"directory": str(path), "pattern": pattern, "directory_device": info.st_dev, "directory_inode": info.st_ino,
            "files": sorted(files, key=lambda item: item["name"]), "bytes": total}


def list_rules(home=AI_OS_HOME):
    with closing(_db(home)) as connection:
        rows = connection.execute("SELECT directory,pattern,expires,uses,max_files,max_bytes FROM rules WHERE expires>? AND uses>0", (time.time(),)).fetchall()
    return [dict(zip(("directory", "pattern", "expires", "uses", "max_files", "max_bytes"), row)) for row in rows]


def forget_rules(home=AI_OS_HOME, *, human_confirmed=False):
    if human_confirmed is not True:
        raise PermissionError("Native confirmation required to clear cleanup rules")
    with closing(_db(home)) as connection:
        connection.execute("DELETE FROM rules")
        connection.commit()


def _claim_rule(spec, home):
    with closing(_db(home)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT expires,uses,max_files,max_bytes,device,inode FROM rules WHERE directory=? AND pattern=?", (spec["directory"], spec["pattern"])).fetchone()
        if not row or row[0] <= time.time() or row[1] <= 0 or len(spec["files"]) > row[2] or spec["bytes"] > row[3] or (row[4], row[5]) != (spec["directory_device"], spec["directory_inode"]):
            return False
        connection.execute("UPDATE rules SET uses=uses-1 WHERE directory=? AND pattern=?", (spec["directory"], spec["pattern"]))
        connection.commit()
    return True


def _trash(spec):
    if _scan(spec["directory"], spec["pattern"]) != spec:
        raise ValueError("Files changed since preview; request a new preview")
    try:
        result = subprocess.run(["/usr/bin/gio", "trash", "--", *[str(Path(spec["directory"]) / f["name"]) for f in spec["files"]]],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=30, shell=False, check=False)
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "message": "Trash operation failed or timed out. Some files may have moved; inspect the directory and Trash before retrying."}
    return {"ok": result.returncode == 0, "count": len(spec["files"]) if result.returncode == 0 else None,
            "message": ("Moved the selected files to desktop Trash. Restore them there if needed."
                        if result.returncode == 0 else "Trash returned a failure; inspect both locations before retrying. No permanent deletion was attempted.")}


def propose_cleanup(directory: str, pattern: str, *, home=AI_OS_HOME):
    """Preview matched files, or use a previously human-approved narrow rule."""
    spec = _scan(directory, pattern)
    if not spec["files"]:
        return {"ok": True, "count": 0, "message": "No matching regular files were found. Nothing moved."}
    if _claim_rule(spec, home):
        return _trash(spec) | {"remembered_rule": True}
    token = secrets.token_hex(16)
    storage = _storage(home)
    if sum(1 for _ in storage.iterdir()) >= 256:
        raise ValueError("Cleanup preview limit reached; review private cleanup state before creating more previews")
    path = storage / (token + ".json")
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), "w") as stream:
        json.dump({"expires": time.time() + PREVIEW_SECONDS, "spec": spec}, stream)
    return {"ok": False, "message": "Review the exact file preview before moving anything to Trash.",
            "approval_required": {"tool": "cleanup_files", "arguments": {"token": token},
                                  "preview": spec}}


def read_preview(token, home=AI_OS_HOME):
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("Invalid cleanup preview")
    path = _storage(home) / (token + ".json")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "r") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 65536:
            raise ValueError("Unsafe cleanup preview")
        value = json.load(stream)
    if value["expires"] < time.time() or _scan(value["spec"]["directory"], value["spec"]["pattern"]) != value["spec"]:
        raise ValueError("Preview expired or files changed; request a new preview")
    return value["spec"]


def execute_cleanup(token, *, home=AI_OS_HOME, human_confirmed=False, remember=False):
    if human_confirmed is not True:
        raise PermissionError("Exact native confirmation required")
    spec = read_preview(token, home)
    # Single-use claim: two clients must not execute the same preview.
    path = _storage(home) / (token + ".json")
    claim = path.with_suffix(".claimed")
    with os.fdopen(os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), "w"):
        pass
    try:
        result = _trash(spec)
        if result["ok"] and remember is True:
            with closing(_db(home)) as connection:
                connection.execute("INSERT OR REPLACE INTO rules VALUES (?,?,?,?,?,?,?,?)",
                                   (spec["directory"], spec["pattern"], time.time() + RULE_SECONDS,
                                    RULE_USES, max(10, len(spec["files"])), max(10 * 1024 ** 2, spec["bytes"]),
                                    spec["directory_device"], spec["directory_inode"]))
                connection.commit()
        return result
    finally:
        path.unlink(missing_ok=True)
