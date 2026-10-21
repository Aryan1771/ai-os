"""Private native-dialog text events. Never publish these as public progress."""
from __future__ import annotations

import json

LIMITS = {"transcript": (8000, 16384), "reply": (2000, 8192)}
FIELDS = {"event", "kind", "text"}


def private_ui_text(value):
    if (type(value) is not dict or set(value) != FIELDS or value.get("event") != "voice_ui_text"
            or type(value.get("kind")) is not str or value["kind"] not in LIMITS
            or type(value.get("text")) is not str):
        return None
    text = value["text"]
    characters, byte_limit = LIMITS[value["kind"]]
    if not text.strip() or len(text) > characters:
        return None
    try:
        if (len(text.encode("utf-8")) > byte_limit
                or len(json.dumps(text, ensure_ascii=False).encode("utf-8")) > byte_limit + 2):
            return None
    except UnicodeError:
        return None
    return dict(value)


def text_event(kind, text):
    event = private_ui_text({"event": "voice_ui_text", "kind": kind, "text": text})
    if event is None:
        raise ValueError("Invalid native voice-check text")
    return event


def encoded_text_event(value):
    event = private_ui_text(value)
    if event is None:
        return None
    # UTF-8 keeps Hindi/emoji within the actual byte budget; ASCII escapes can
    # multiply a valid transcript enough to exhaust the 64 KiB dialog stream.
    return (json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
