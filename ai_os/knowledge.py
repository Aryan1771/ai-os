"""Explicit official-manual refresh and bounded offline retrieval; never executes pages."""
import argparse
import hashlib
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path

import requests

from ai_os.config import AI_OS_HOME, atomic_json

SOURCES = {name: f"https://man.archlinux.org/man/{name}.{section}.en"
           for name, section in {"pacman": 8, "systemctl": 1, "journalctl": 1,
                                 "ip": 8, "lsblk": 8, "nmcli": 1}.items()}


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def refresh(name: str, home: Path = AI_OS_HOME):
    url = SOURCES[name]  # Only a fixed official catalog; no user/model URL fetches.
    start = time.monotonic()
    with requests.Session() as session:
        session.trust_env = False
        with session.get(url, timeout=(5, 15), stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError(f"Official manual returned HTTP {response.status_code}; cache unchanged")
            content = bytearray()
            for chunk in response.iter_content(8192):
                content.extend(chunk)
                if len(content) > 1_000_000 or time.monotonic() - start > 30:
                    raise ValueError("Manual exceeded download limit; cache unchanged")
    parser = PageText()
    parser.feed(content.decode("utf-8"))
    text = "\n".join(parser.parts)[:250000]
    if len(text) < 100 or name not in text.lower():
        raise ValueError("Manual response does not look usable; cache unchanged")
    result = {"source": url, "fetched_at": time.time(), "sha256": hashlib.sha256(content).hexdigest(), "text": text}
    atomic_json(home / "data/knowledge" / f"{name}.json", result)
    return {k: v for k, v in result.items() if k != "text"}


def search(query: str, home: Path = AI_OS_HOME):
    words = set(re.findall(r"[a-z0-9_-]{3,}", query.lower()))
    results = []
    for name in SOURCES:
        if name not in words:
            continue
        path = home / "data/knowledge" / f"{name}.json"
        try:
            if path.stat().st_size > 1_100_000:
                continue
            data = json.loads(path.read_text())
            if data["source"] != SOURCES[name] or not isinstance(data["text"], str):
                continue
            lines = data["text"].splitlines()
            ranked = sorted(enumerate(lines), key=lambda p: len(words & set(re.findall(r"[a-z0-9_-]+", p[1].lower()))), reverse=True)
            indices = sorted({j for i, _ in ranked[:4] for j in range(max(0, i-1), min(len(lines), i+4))})
            results.append({"source": data["source"], "fetched_at": data["fetched_at"],
                            "excerpt": "\n".join(lines[i] for i in indices)[:1800]})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return results[:2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["refresh", "search"])
    parser.add_argument("topic", help="Official topic to refresh, or quoted search text")
    parser.add_argument("--home", type=Path, default=AI_OS_HOME)
    args = parser.parse_args()
    if args.action == "refresh" and args.topic not in SOURCES:
        parser.error("Choose: " + ", ".join(SOURCES))
    print(json.dumps(refresh(args.topic, args.home) if args.action == "refresh" else search(args.topic, args.home), indent=2))


if __name__ == "__main__":
    main()
