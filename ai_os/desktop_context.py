"""Opt-in, local-only accessibility context; no screen images or persistent text."""
import json
from pathlib import Path
import subprocess

from ai_os.config import load_raw_config


def read_desktop(home: Path, *, metadata_only=False):
    config = load_raw_config(home)
    permitted = config["activity_memory_enabled"] if metadata_only else config["desktop_context_enabled"]
    if not permitted:
        return {"ok": False, "reason": "Accessibility context is disabled in Companion settings"}
    command = ["/usr/bin/python", "-I", str(Path(__file__).with_name("desktop_probe.py"))]
    if metadata_only:
        command.append("--metadata-only")
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=4, shell=False)
        if result.returncode or len(result.stdout) > 30000:
            raise ValueError("Invalid accessibility response")
        data = json.loads(result.stdout)
        latest = load_raw_config(home)
        if not latest["activity_memory_enabled" if metadata_only else "desktop_context_enabled"]:
            return {"ok": False, "reason": "Observation permission revoked"}
        if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
            raise ValueError("Invalid accessibility response")
        if data["ok"] and not isinstance(data.get("application") if metadata_only else data.get("text"), str):
            raise ValueError("Invalid accessibility content")
        if metadata_only:
            return {"ok": data["ok"], "application": str(data.get("application", ""))[:80]}
        return {"ok": data["ok"], "text": str(data.get("text", ""))[:6000],
                "application": str(data.get("application", ""))[:80],
                "reason": str(data.get("reason", ""))[:300], "source": "accessibility"}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"ok": False, "reason": "Accessibility unavailable or timed out; no desktop data retained"}
