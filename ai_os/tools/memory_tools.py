from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_os.config import AI_OS_HOME


@dataclass(frozen=True)
class MemoryPaths:
    habits: Path = AI_OS_HOME / "habit_engine.json"
    slang: Path = AI_OS_HOME / "slang_vocab.json"
    events: Path = AI_OS_HOME / "data" / "events.jsonl"


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_habits(paths: MemoryPaths = MemoryPaths()) -> dict[str, Any]:
    return _read_json(paths.habits, {"defaults": {}, "temporary_overrides": {}, "notes": []})


def set_habit(key: str, value: Any, paths: MemoryPaths = MemoryPaths()) -> dict[str, Any]:
    habits = get_habits(paths)
    habits.setdefault("defaults", {})[key] = value
    _write_json(paths.habits, habits)
    remember_event("habit_updated", {"key": key, "value": value}, paths)
    return {"ok": True, "key": key, "value": value}


def set_temporary_override(key: str, value: Any, ttl_sec: int = 3600, paths: MemoryPaths = MemoryPaths()) -> dict[str, Any]:
    habits = get_habits(paths)
    habits.setdefault("temporary_overrides", {})[key] = {
        "value": value,
        "expires_at": int(time.time()) + max(1, int(ttl_sec)),
    }
    _write_json(paths.habits, habits)
    remember_event("temporary_override_set", {"key": key, "value": value, "ttl_sec": ttl_sec}, paths)
    return {"ok": True, "key": key, "value": value, "ttl_sec": ttl_sec}


def resolve_preference(key: str, paths: MemoryPaths = MemoryPaths()) -> Any:
    habits = get_habits(paths)
    override = habits.get("temporary_overrides", {}).get(key)
    if override and int(override.get("expires_at", 0)) > int(time.time()):
        return override.get("value")
    return habits.get("defaults", {}).get(key)


def get_slang(paths: MemoryPaths = MemoryPaths()) -> dict[str, Any]:
    return _read_json(paths.slang, {"replacements": {}, "protected_terms": []})


def apply_slang_replacements(text: str, paths: MemoryPaths = MemoryPaths()) -> dict[str, Any]:
    slang = get_slang(paths)
    protected = set(slang.get("protected_terms", []))
    replacements = slang.get("replacements", {})
    tokens = text.split()
    changed: list[dict[str, str]] = []
    output: list[str] = []
    for token in tokens:
        clean = token.strip(".,!?;:").lower()
        if clean in protected:
            output.append(token)
        elif clean in replacements:
            output.append(replacements[clean])
            changed.append({"from": token, "to": replacements[clean]})
        else:
            output.append(token)
    return {"text": " ".join(output), "changes": changed}


def remember_event(kind: str, payload: dict[str, Any], paths: MemoryPaths = MemoryPaths()) -> dict[str, Any]:
    paths.events.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": int(time.time()), "kind": kind, "payload": payload}
    with paths.events.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return {"ok": True, "event": event}


def search_recent_events(query: str, limit: int = 20, paths: MemoryPaths = MemoryPaths()) -> list[dict[str, Any]]:
    if not paths.events.exists():
        return []
    rows: list[dict[str, Any]] = []
    needle = query.lower()
    for line in reversed(paths.events.read_text(encoding="utf-8").splitlines()):
        if needle in line.lower():
            rows.append(json.loads(line))
        if len(rows) >= limit:
            break
    return rows

