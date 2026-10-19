"""Bounded, opt-in hardware speech from local facts, never model instructions."""

from __future__ import annotations

import json
import subprocess
import threading
import time
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from ai_os.companion_state import publish_state, read_state
from ai_os.config import atomic_json, load_config, load_raw_config
from ai_os.device_context import DisplayTracker
from ai_os.speech_lease import speech_lease
from ai_os.speech_queue import SpeechQueue


def device_reaction(action: str, subsystem: str, device_type: str, language="en") -> str | None:
    """Use only a fixed category and action, never labels, serials or mount paths."""
    categories = {
        ("usb", "usb_device"): ("USB device", "यूएसबी डिवाइस"),
        ("block", "disk"): ("storage device", "स्टोरेज डिवाइस"),
        ("sound", ""): ("audio device", "ऑडियो डिवाइस"),
    }
    category = categories.get((subsystem, device_type))
    if category is None or action not in {"add", "remove", "change"}:
        return None
    if language == "hi":
        suffix = {"add": "जुड़ गया है।", "remove": "हट गया है।", "change": "में बदलाव हुआ है।"}[action]
        return f"{'ओह, ' if action == 'add' else ''}{category[1]} {suffix}"
    if action == "add":
        return f"Oh, a {category[0]} is connected."
    if action == "remove":
        return f"The {category[0]} has been disconnected."
    return f"The {category[0]} connection changed."


@dataclass(frozen=True)
class PendingReaction:
    text: str
    created: float
    language: str = "en"


class HardwareReactions:
    """Keep up to eight recent reactions while a conversation owns the assistant."""

    def __init__(self, home: Path, *, clock=time.monotonic):
        self.home = home
        self.clock = clock
        self.pending: deque[PendingReaction] = deque(maxlen=8)
        self.recent: dict[str, float] = {}

    def expire(self):
        now = self.clock()
        while self.pending and now - self.pending[0].created > 60:
            self.pending.popleft()
        self.recent = {text: timestamp for text, timestamp in self.recent.items()
                       if now - timestamp < 3}

    def clear(self):
        self.pending.clear()
        self.recent.clear()

    def enqueue(self, text: str, config: dict):
        self.expire()
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            return
        now = self.clock()
        if text in self.recent:
            return
        self.recent[text] = now
        if config["hardware_speech_enabled"] and config["speech_enabled"]:
            self.pending.append(PendingReaction(text, now, config["whisper_language"]))
        atomic_json(self.home / "run/hardware-event.json", {
            "message": text, "updated": time.time(), "pending_count": len(self.pending),
        })

    def dispatch(self, config: dict):
        self.expire()
        if not (config["hardware_notifications_enabled"] and config["hardware_speech_enabled"]
                and config["speech_enabled"]):
            self.clear()
            return
        if not self.pending or read_state(self.home)["phase"] not in {"idle", "armed"}:
            return
        with speech_lease(self.home) as acquired:
            if not acquired:
                return
            prior = read_state(self.home)
            if prior["phase"] not in {"idle", "armed"}:
                return
            # Recheck opt-ins after obtaining ownership; queued events never
            # speak later after the user disables either switch.
            current = load_raw_config(self.home)
            if not (current["hardware_notifications_enabled"] and current["hardware_speech_enabled"]
                    and current["speech_enabled"]):
                self.clear()
                return
            item = self.pending.popleft()
            if item.language != current["whisper_language"]:
                atomic_json(self.home / "run/hardware-event.json", {
                    "message": "Queued device reaction skipped after the conversation language changed.",
                    "updated": time.time(), "pending_count": len(self.pending),
                })
                return  # Do not speak queued text in a previously selected language.
            voice = load_config(self.home)
            speech = SpeechQueue(voice.piper_model, hindi_model=voice.piper_hindi_model,
                                 length_scale=voice.piper_length_scale,
                                 emotion_enabled=current["speech_emotion_enabled"])
            owned_state = publish_state("speaking", home=self.home)
            try:
                speech.speak_text(item.text)
                atomic_json(self.home / "run/hardware-event.json", {
                    "message": item.text, "updated": time.time(), "pending_count": len(self.pending),
                })
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, wave.Error):
                atomic_json(self.home / "run/hardware-event.json", {
                    "message": item.text, "updated": time.time(), "pending_count": len(self.pending),
                    "speech_error": "Hardware speech failed; check Piper voice assets and playback.",
                })
            finally:
                speech.stop()
                # A listener/UI may have published newer activity. Never erase it.
                path = self.home / "run/avatar_state.json"
                try:
                    if path.stat().st_size <= 16384 and json.loads(path.read_text()) == owned_state:
                        publish_state(prior["phase"], home=self.home)
                except (OSError, ValueError):
                    pass


def watch_devices(home: Path, stop: threading.Event):
    """Observe with pyudev and periodically retry DRM facts after hotplug settles."""
    def unavailable():
        atomic_json(home / "run/hardware-event.json", {
            "message": "Device monitor unavailable; check pyudev and session permissions", "updated": time.time(),
        })

    try:
        import pyudev
        monitor = pyudev.Monitor.from_netlink(pyudev.Context())
        monitor.start()
    except (ImportError, OSError, ValueError):
        unavailable()
        return
    reactions = HardwareReactions(home)
    tracker = None
    last_display_poll = -10.0
    while not stop.is_set():
        try:
            config = load_raw_config(home)
            enabled = config["hardware_notifications_enabled"]
            if not enabled:
                tracker = None
                reactions.clear()
            elif tracker is None:
                # Establish a baseline BEFORE waiting for the next event. A
                # first hotplug after enabling is therefore not the baseline.
                tracker = DisplayTracker(home)
            device = monitor.poll(timeout=0.5)
            if stop.is_set():
                break
            config = load_raw_config(home)
            if not config["hardware_notifications_enabled"]:
                tracker = None
                reactions.clear()
                continue
            if tracker is None:
                # Monitoring was enabled during poll: current hardware becomes
                # the baseline; collection while disabled is intentionally off.
                tracker = DisplayTracker(home)
            now = time.monotonic()
            if now - last_display_poll >= 1 or (device is not None and device.subsystem == "drm"):
                for notice in tracker.poll(config["whisper_language"]):
                    reactions.enqueue(notice, config)
                last_display_poll = now
            if device is not None:
                text = device_reaction(device.action, device.subsystem, device.device_type or "",
                                       config["whisper_language"])
                if text:
                    reactions.enqueue(text, config)
            reactions.dispatch(config)
        except (OSError, ValueError):
            unavailable()
            stop.wait(1)
