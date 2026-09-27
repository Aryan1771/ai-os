"""Human-confirmed session grants. Never register these functions as model tools."""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

import psutil

from ai_os.tools.system_tools import assess_command, RiskLevel

MAX_SECONDS = 86400
SCOPE = ("Timed scope: reviewed diagnostics and new-file mkdir/touch/cp operations in "
         "Documents, Downloads or /tmp. No overwrites, deletion, sudo, shells, scripts, "
         "package/service changes or protected disk access. Other commands require individual approval.")
NUMBERS = dict(zip(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
NUMBERS.update(dict(zip("twenty thirty forty fifty sixty".split(), range(20, 61, 10))))


def duration(text):
    if re.search(r"(?:^|\s)-\d", text):
        raise ValueError("Duration must be positive")
    words = text.lower().replace("-", " ").split()
    normalized = []
    for word in words:
        if word in NUMBERS:
            if normalized and normalized[-1].isdigit() and int(normalized[-1]) >= 20 and NUMBERS[word] < 10:
                normalized[-1] = str(int(normalized[-1]) + NUMBERS[word])
            else:
                normalized.append(str(NUMBERS[word]))
        elif word in {"a", "an"}:
            normalized.append("1")
        elif word != "and":
            normalized.append(word)
    value = " ".join(normalized)
    pattern = r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)"
    total = 0.0
    position = 0
    for match in re.finditer(pattern, value):
        if value[position:match.start()].strip():
            raise ValueError("Use seconds, minutes or hours")
        total += float(match[1]) * (3600 if match[2].startswith("h") else 60 if match[2].startswith("m") else 1)
        position = match.end()
    if value[position:].strip() or not 1 <= total <= MAX_SECONDS or not math.isfinite(total):
        raise ValueError("Duration must be between 1 second and 24 hours")
    return math.ceil(total)


def intent(text):
    value = text.strip().lower().rstrip(".!?")
    if value in {"revoke access", "revoke full access", "revoke all access", "stop full access"}:
        return {"kind": "revoke", "all_sessions": value == "revoke all access"}
    if value == "i give you full access to this command":
        return {"kind": "once", "seconds": 120}
    prefix = "i give you full access for "
    if value.startswith(prefix):
        return {"kind": "timed", "seconds": duration(value[len(prefix):])}
    return None


def command_spec(arguments):
    if not isinstance(arguments, dict) or set(arguments) - {"command", "cwd", "timeout_sec"}:
        raise ValueError("Unsupported command arguments")
    assessment = assess_command(arguments.get("command", []))
    if assessment.risk == RiskLevel.PROHIBITED:
        raise ValueError("Prohibited commands cannot receive grants")
    cwd = arguments.get("cwd") or os.getcwd()
    if not isinstance(cwd, str) or not cwd.isprintable():
        raise ValueError("Invalid working directory")
    return {"command": assessment.command, "cwd": str(Path(cwd).resolve()),
            "timeout_sec": max(1, min(60, int(arguments.get("timeout_sec", 15))))}


def timed_allowed(spec, home):
    """Deliberately small audited scope. Unknown executables never inherit a grant."""
    argv = spec["command"]
    assessment = assess_command(argv)
    if assessment.risk == RiskLevel.SAFE:
        return True
    name = Path(argv[0]).name
    if argv[0] not in {name, "/usr/bin/" + name} or name not in {"mkdir", "touch", "cp"}:
        return False
    args = argv[1:]
    if name == "mkdir" and args[:1] == ["-p"]:
        args = args[1:]
    if len(args) != (2 if name == "cp" else 1) or any(a.startswith("-") for a in args):
        return False
    roots = [Path.home()/"Documents", Path.home()/"Downloads", Path("/tmp")]
    paths = []
    for arg in args:
        path = Path(spec["cwd"]) / arg
        if any(part.startswith(".") and part not in {".", ".."} for part in path.parts):
            return False
        resolved = path.resolve()
        if resolved.is_relative_to(home.resolve()) or not any(resolved.is_relative_to(root.resolve()) and resolved != root.resolve() for root in roots):
            return False
        paths.append(resolved)
    if name == "cp" and (not paths[0].is_file() or paths[1].exists()):
        return False
    if name == "touch" and paths[0].exists():
        return False
    return True


class GrantStore:
    def __init__(self, home):
        self.home = home
        self.path = home / "run/private/access.sqlite3"

    @contextmanager
    def transaction(self, session):
        if not isinstance(session, str) or not 1 <= len(session) <= 80:
            raise ValueError("Invalid session")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        db = sqlite3.connect(self.path, timeout=1)
        try:
            self.path.chmod(0o600)
            db.execute("CREATE TABLE IF NOT EXISTS sessions (name TEXT PRIMARY KEY, state TEXT)")
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM sessions WHERE name=?", (session,)).fetchone()
            state = json.loads(row[0]) if row else {}
            if not isinstance(state, dict):
                state = {}
            boot = str(psutil.boot_time())
            now = time.monotonic()
            for key in list(state):
                item = state[key]
                valid = (key in {"command", "request", "grant"} and isinstance(item, dict)
                         and all(type(item.get(field)) in (int, float) and math.isfinite(item[field])
                                 for field in ("deadline", "wall_deadline")))
                if (not valid or item.get("boot") != boot or now >= item.get("deadline", 0)
                        or item["deadline"] > now + MAX_SECONDS + 120
                        or time.time() >= item.get("wall_deadline", 0)
                        or (key in {"request", "grant"} and item.get("kind") not in {"once", "timed"})):
                    del state[key]
            yield state
            db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?)", (session, json.dumps(state)))
            db.commit()
        finally:
            db.close()

    @staticmethod
    def stamp(ttl, **values):
        return values | {"boot": str(psutil.boot_time()), "deadline": time.monotonic()+ttl,
                         "wall_deadline": time.time()+ttl}

    def pending_command(self, session, arguments):
        spec = command_spec(arguments)
        with self.transaction(session) as state:
            state["command"] = self.stamp(120, spec=spec)
            state.pop("request", None)

    def request(self, session, choice):
        if choice.get("kind") not in {"once", "timed"} or type(choice.get("seconds")) is not int or not 1 <= choice["seconds"] <= MAX_SECONDS:
            raise ValueError("Invalid access grant")
        with self.transaction(session) as state:
            spec = None
            if choice["kind"] == "once":
                if "command" not in state:
                    raise ValueError("No pending command. Request the action first; pending commands expire after two minutes.")
                spec = state["command"]["spec"]
            state["request"] = self.stamp(120, token=secrets.token_hex(16),
                                          kind=choice["kind"], seconds=choice["seconds"], spec=spec)
            return dict(state["request"])

    def confirm(self, session, token, *, human_confirmed=False):
        if human_confirmed is not True:
            raise PermissionError("Human confirmation required")
        with self.transaction(session) as state:
            request = state.get("request")
            if not request or request["token"] != token:
                raise PermissionError("Grant request expired, changed or revoked")
            state["grant"] = self.stamp(request["seconds"], kind=request["kind"], spec=request["spec"])
            del state["request"]
            state.pop("command", None)
            return dict(state["grant"])

    def status(self, session):
        with self.transaction(session) as state:
            return json.loads(json.dumps(state))

    def revoke(self, session):
        with self.transaction(session) as state:
            state.clear()

    def clear_pending(self, session):
        with self.transaction(session) as state:
            state.pop("command", None)
            state.pop("request", None)

    def consume(self, session, arguments):
        from ai_os.config import load_raw_config
        if load_raw_config(self.home)["command_access"] != "supervised":
            self.revoke(session)
            return None
        spec = command_spec(arguments)
        with self.transaction(session) as state:
            grant = state.get("grant")
            if not grant:
                return None
            if grant["kind"] == "once":
                if grant["spec"] != spec:
                    return None
                del state["grant"]  # Atomic one-use claim before execution, including failures.
            elif not timed_allowed(spec, self.home):
                return None
            else:
                spec["command"][0] = "/usr/bin/" + Path(spec["command"][0]).name
                spec["timeout_sec"] = min(spec["timeout_sec"], max(1, int(grant["deadline"]-time.monotonic())))
                if Path(spec["command"][0]).name == "cp":
                    spec["command"].insert(1, "--no-clobber")
            return spec


def revoke_all(home):
    path = GrantStore(home).path
    if path.exists():
        with sqlite3.connect(path, timeout=1) as db:
            db.execute("DELETE FROM sessions")
