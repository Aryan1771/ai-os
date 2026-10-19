"""Bounded read-only monitor facts; identifiers stay hashed in private runtime data."""
from __future__ import annotations

import hashlib
import json
from itertools import islice
from pathlib import Path

from ai_os.config import atomic_json


def displays(root=Path("/sys/class/drm")):
    found = {}
    for connector in sorted(root.glob("card*-*"))[:32]:
        try:
            if (connector / "status").read_text()[:32].strip() != "connected":
                continue
            try:
                with (connector / "edid").open("rb") as handle:
                    edid = handle.read(4096)
            except OSError:
                edid = b""
            # Invalid/missing EDID uses connection identity, never an invented model ID.
            valid = len(edid) >= 128 and edid[:8] == b"\x00\xff\xff\xff\xff\xff\xff\x00" and sum(edid[:128]) % 256 == 0
            identity = hashlib.sha256(edid if valid else connector.name.encode()).hexdigest()
            modes = []
            with (connector / "modes").open() as handle:
                for line in islice(handle, 128):
                    parts = line.strip().split("x")
                    if len(parts) == 2 and all(p.isdigit() and len(p) <= 5 for p in parts):
                        width, height = map(int, parts)
                        if 1 <= width <= 16384 and 1 <= height <= 16384:
                            modes.append((width, height))
            width, height = max(modes, key=lambda m: m[0]*m[1], default=(0, 0))
            found[identity] = {"width": width, "height": height}
        except (OSError, ValueError):
            continue
    return found


class DisplayTracker:
    def __init__(self, home, root=Path("/sys/class/drm")):
        self.path = home / "data/private/known-displays.json"
        self.root = root
        try:
            saved = json.loads(self.path.read_text())
            self.known = {k: v for k, v in saved.items()
                          if isinstance(k, str) and len(k) == 64 and isinstance(v, dict)
                          and type(v.get("width")) is int and type(v.get("height")) is int
                          and 0 <= v["width"] <= 16384 and 0 <= v["height"] <= 16384}
        except (OSError, ValueError, AttributeError):
            self.known = {}
        self.active = displays(root)
        for identity, specs in self.active.items():
            if specs["width"] or identity not in self.known:
                self.known[identity] = specs
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        self.known = dict(list(self.known.items())[-128:])
        atomic_json(self.path, self.known)
        self.path.chmod(0o600)

    def poll(self, language="en"):
        current = displays(self.root)
        notices = []
        best = max((v["width"] * v["height"] for v in self.known.values()), default=0)
        for identity, specs in current.items():
            previous = self.active.get(identity)
            newly_ready = previous is not None and not previous["width"] and bool(specs["width"])
            if previous is not None and not newly_ready:
                continue
            new = identity not in self.known
            width, height = specs["width"], specs["height"]
            if language == "hi":
                text = ("मॉनिटर की जानकारी अब उपलब्ध है।" if newly_ready else
                        "ओह, नया मॉनिटर जुड़ा है।" if new else "मॉनिटर फिर से जुड़ गया है।")
                if width:
                    text += f" यह {width} बाई {height} रिज़ॉल्यूशन का समर्थन करता है।"
                    if (width, height) in {(3840, 2160), (4096, 2160)}:
                        text += " यह 4K है।"
            else:
                text = ("The monitor's display details are ready." if newly_ready else
                        "Oh, a new monitor! More room to work together." if new else "Our monitor is back.")
                if width:
                    text += f" It supports {width} by {height}."
                    if (width, height) in {(3840, 2160), (4096, 2160)}:
                        text += " That's 4K."
                if new and best and width * height > best:
                    text += " That's more pixels than the displays I've seen here before."
            notices.append(text)
        self.active = current
        for identity, specs in current.items():
            if specs["width"] or identity not in self.known:
                self.known[identity] = specs
        self.save()
        return notices
