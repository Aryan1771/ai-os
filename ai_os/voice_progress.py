"""Bounded guided-check progress: fixed phases and numbers, never user content."""
from __future__ import annotations

import math
import time

PHASES = frozenset({"preparing", "checking_input", "waiting_for_speech", "capturing",
                    "microphone_off", "filtering", "transcribing", "thinking", "speaking"})
NUMBERS = frozenset({"captured_seconds", "silence_seconds", "required_silence_seconds"})
MAX_EVENTS = 512


def public_progress(value):
    if (type(value) is not dict or value.get("event") != "voice_progress"
            or type(value.get("phase")) is not str or value["phase"] not in PHASES
            or set(value) - ({"event", "phase"} | NUMBERS)):
        return None
    for key in NUMBERS.intersection(value):
        number = value[key]
        if type(number) not in (int, float) or not 0 <= number <= 180 or not math.isfinite(number):
            return None
    return {key: round(item, 2) if key in NUMBERS else item for key, item in value.items()}


class ProgressReporter:
    def __init__(self, callback=None):
        self.callback = callback
        self.last_phase = None
        self.last_time = 0
        self.count = 0

    def emit(self, phase, **numbers):
        if self.callback is None or self.count >= MAX_EVENTS:
            return
        event = public_progress({"event": "voice_progress", "phase": phase, **numbers})
        if event is None:
            return
        now = time.monotonic()
        if phase == self.last_phase and now - self.last_time < .25:
            return
        self.last_phase, self.last_time = phase, now
        self.count += 1
        self.callback(event)


def progress_message(event):
    phase = event["phase"]
    messages = {
        "preparing": "Preparing the voice check. Microphone has not started yet.",
        "checking_input": "Checking the selected input. Microphone has not started yet.",
        "waiting_for_speech": "● Microphone on — waiting for speech to begin (up to eight seconds).",
        "capturing": "● Microphone on — recording. Finish speaking, then pause.",
        "microphone_off": "Microphone off — recording finished.",
        "filtering": "Microphone off — checking the optional speaker filter.",
        "transcribing": "Microphone off — transcribing with local Whisper.",
        "thinking": "Microphone off — preparing the local reply.",
        "speaking": "Microphone off — preparing or playing the spoken reply.",
    }
    if phase == "capturing" and all(key in event for key in ("silence_seconds", "required_silence_seconds")):
        required = event["required_silence_seconds"]
        current = min(required, event["silence_seconds"])
        return ("● Microphone on — recording. Current quiet pause: "
                f"{current:.1f} / {required:.1f} seconds. Speech/noise restarts the pause.")
    return messages[phase]
