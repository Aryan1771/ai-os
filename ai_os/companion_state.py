from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any

from ai_os.config import AI_OS_HOME, DEFAULT_CONFIG, atomic_json

EMOTIONS = tuple(DEFAULT_CONFIG["avatar_emotions"])
PHASES = {
    "idle",
    "armed",
    "listening",
    "transcribing",
    "thinking",
    "working",
    "speaking",
    "reply",
    "error",
}
SHAPE_NAMES = (
    "core",
    "heart",
    "music",
    "code",
    "idea",
    "cloud",
    "gear",
    "shield",
    "folder",
    "chip",
    "search",
    "clock",
)
PHASE_LEVELS = {
    "idle": {},
    "armed": {"calm": 85, "curiosity": 55},
    "listening": {"curiosity": 85, "focus": 70},
    "transcribing": {"focus": 85, "energy": 60},
    "thinking": {"curiosity": 85, "focus": 90, "energy": 60},
    "working": {"focus": 95, "energy": 75, "calm": 55},
    "speaking": {"joy": 55, "energy": 70},
    "reply": {"joy": 65, "calm": 80},
    "error": {"concern": 85, "joy": 15, "calm": 35},
}
TOPICS = (
    (("music", "song", "melody", "audio", "volume"), "music"),
    (("love", "heart", "care", "happy"), "heart"),
    (("code", "python", "program", "script", "debug"), "code"),
    (("idea", "plan", "think"), "idea"),
    (("weather", "cloud", "rain"), "cloud"),
    (("security", "permission", "firewall", "sandbox"), "shield"),
    (("file", "folder", "directory", "document"), "folder"),
    (("hardware", "cpu", "gpu", "memory", "process"), "chip"),
    (("search", "find", "look"), "search"),
    (("time", "clock", "schedule", "wait"), "clock"),
)


def validate_pixels(value: Any) -> list[str] | None:
    """The model may describe pixels, never supply code, URLs, or file paths."""
    if not isinstance(value, list) or not 4 <= len(value) <= 24:
        return None
    if any(not isinstance(row, str) or not 4 <= len(row) <= 24 for row in value):
        return None
    if len({len(row) for row in value}) != 1:
        return None
    if any(set(row) - set(".#+*o") for row in value):
        return None
    return value if any(char != "." for row in value for char in row) else None


def visual_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    if value.get("shape") in SHAPE_NAMES:
        result["shape"] = value["shape"]
    pixels = validate_pixels(value.get("pixels"))
    if pixels:
        result["pixels"] = pixels
    levels = value.get("emotions", {})
    if isinstance(levels, dict):
        result["emotions"] = {
            key: max(0, min(100, int(number)))
            for key, number in levels.items()
            if key in EMOTIONS and type(number) in (int, float) and math.isfinite(number)
        }
    return result


def topic_shape(text: str, phase: str = "idle") -> str:
    words = set(re.findall(r"[a-z]+", text.lower().replace("_", " ")))
    for terms, shape in TOPICS:
        if words.intersection(terms):
            return shape
    return "gear" if phase == "working" else "core"


def publish_state(
    phase: str,
    text: str = "",
    *,
    home: Path = AI_OS_HOME,
    avatar: Any = None,
) -> dict[str, Any]:
    if phase not in PHASES:
        raise ValueError("Unsupported companion activity.")
    metadata = visual_metadata(avatar)
    emotions = PHASE_LEVELS[phase] | metadata.get("emotions", {})
    state = {
        "version": 1,
        "updated_at": time.time(),
        "phase": phase,
        "shape": metadata.get("shape", topic_shape(text, phase)),
        "emotions": emotions,
        "pixels": metadata.get("pixels"),
    }
    atomic_json(home / "run" / "avatar_state.json", state)
    return state


def read_state(home: Path = AI_OS_HOME, *, now: float | None = None) -> dict[str, Any]:
    idle = {"phase": "idle", "shape": "core", "emotions": {}, "pixels": None}
    try:
        path = home / "run" / "avatar_state.json"
        if path.stat().st_size > 16_384:
            return idle
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("phase") not in PHASES:
            return idle
        age = (time.time() if now is None else now) - float(state["updated_at"])
        ttl = 15 if state["phase"] in {"reply", "error"} else 180
        if not math.isfinite(age) or age < -5 or age > ttl:
            return idle
        return idle | visual_metadata(state) | {"phase": state["phase"]}
    except (OSError, ValueError, TypeError, KeyError):
        return idle


def emotion_levels(state: dict[str, Any], config: dict[str, Any]) -> dict[str, float]:
    baseline = DEFAULT_CONFIG["avatar_emotions"] | config.get("avatar_emotions", {})
    influence = config.get("avatar_reactivity", 75) / 100
    targets = PHASE_LEVELS.get(state["phase"], {}) | state.get("emotions", {})
    return {
        key: max(
            0,
            min(100, baseline[key] + (targets.get(key, baseline[key]) - baseline[key]) * influence),
        )
        for key in EMOTIONS
    }
