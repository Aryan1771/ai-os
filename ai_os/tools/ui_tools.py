from __future__ import annotations

import os
from typing import Any

from ai_os.config import load_config
from ai_os.tools.system_tools import run_command


def ui_status() -> dict[str, Any]:
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    hyprland_instance = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    return {
        "ok": True,
        "session_type": session_type,
        "hyprland_detected": bool(hyprland_instance),
        "phase": "disabled_until_phase_5",
    }


def require_hyprland() -> tuple[bool, str]:
    if not load_config().hyprland_enabled:
        return False, "Hyprland automation is disabled in ~/.ai_os/config.json."
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return False, "Hyprland was not detected. Start a Hyprland session before using UI tools."
    return True, "Hyprland detected."


def list_windows() -> dict[str, Any]:
    ok, reason = require_hyprland()
    if not ok:
        return {"ok": False, "error": reason}
    result = run_command(["hyprctl", "clients", "-j"])
    if not result.ok:
        return {"ok": False, "error": result.stderr}
    try:
        import json

        return {"ok": True, "windows": json.loads(result.stdout)}
    except json.JSONDecodeError:
        return {"ok": False, "error": "hyprctl returned invalid JSON."}


def type_text(text: str, *, approve: bool = False) -> dict[str, Any]:
    ok, reason = require_hyprland()
    if not ok:
        return {"ok": False, "error": reason}
    if not approve:
        return {"ok": False, "error": "Typing into the active UI requires explicit approval."}
    result = run_command(["ydotool", "type", "--", text], approve=True)
    return {"ok": result.ok, "stderr": result.stderr}
