from __future__ import annotations

import os
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ai_os.config import AI_OS_HOME, load_config
from ai_os.tools.system_tools import run_command


def ui_status(home: Path = AI_OS_HOME) -> dict[str, Any]:
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    hyprland_instance = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    return {
        "ok": True,
        "session_type": session_type,
        "hyprland_detected": bool(hyprland_instance),
        "enabled": load_config(home).hyprland_enabled,
        "phase": "ready" if hyprland_instance and load_config(home).hyprland_enabled else "unavailable",
    }


def require_hyprland(home: Path = AI_OS_HOME) -> tuple[bool, str]:
    if not load_config(home).hyprland_enabled:
        return False, "Hyprland automation is disabled in ~/.ai_os/config.json."
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return False, "Hyprland was not detected. Start a Hyprland session before using UI tools."
    return True, "Hyprland detected."


def _hyprctl(*args):
    try:
        result = subprocess.run(["/usr/bin/hyprctl", *args], capture_output=True,
                                text=True, timeout=5, shell=False, stdin=subprocess.DEVNULL)
        if result.returncode:
            return {"ok": False, "error": result.stderr[:500] or result.stdout[:500]}
        return {"ok": True, "output": result.stdout[:1000000]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def list_windows(home: Path = AI_OS_HOME) -> dict[str, Any]:
    ok, reason = require_hyprland(home)
    if not ok:
        return {"ok": False, "error": reason}
    result = _hyprctl("-j", "clients")
    if not result["ok"]:
        return result
    try:
        windows = json.loads(result["output"])
        if not isinstance(windows, list):
            raise ValueError("Invalid client list")
        return {"ok": True, "windows": [{k: w.get(k) for k in ("address", "class", "title", "workspace")}
                                         for w in windows[:200] if isinstance(w, dict)]}
    except ValueError:
        return {"ok": False, "error": "hyprctl returned invalid JSON."}


def _dispatch(legacy, modern, home):
    ok, reason = require_hyprland(home)
    if not ok:
        return {"ok": False, "error": reason}
    version = _hyprctl("-j", "version")
    if not version["ok"]:
        return version
    try:
        match = re.search(r"(?:^|v)(\d+)\.(\d+)", json.loads(version["output"])["version"])
        if not match:
            raise ValueError("Unknown Hyprland version")
        lua = (int(match[1]), int(match[2])) >= (0, 55)
    except (ValueError, KeyError, TypeError):
        return {"ok": False, "error": "Cannot identify Hyprland dispatcher version"}
    # Modern dispatch expressions below are fixed templates with validated scalars.
    # Never accept arbitrary Lua, exec, batch dispatches or window regexes from models.
    return _hyprctl("dispatch", *([modern] if lua else legacy))


def switch_workspace(workspace: int, home: Path = AI_OS_HOME):
    if type(workspace) is not int or not 1 <= workspace <= 20:
        raise ValueError("Workspace must be an integer from 1 to 20")
    return _dispatch(["workspace", str(workspace)], f"hl.dsp.focus({{workspace={workspace}}})", home)


def focus_window(address: str, home: Path = AI_OS_HOME):
    if not isinstance(address, str) or not re.fullmatch(r"0x[0-9a-fA-F]{1,16}", address):
        raise ValueError("Use a window address from list_windows")
    windows = list_windows(home)
    if not windows["ok"]:
        return windows
    if address not in {w["address"] for w in windows["windows"]}:
        return {"ok": False, "error": "Window is no longer available"}
    return _dispatch(["focuswindow", "address:"+address],
                     f'hl.dsp.focus({{window="address:{address}"}})', home)


def type_text(text: str, *, approve: bool = False) -> dict[str, Any]:
    ok, reason = require_hyprland()
    if not ok:
        return {"ok": False, "error": reason}
    if not approve:
        return {"ok": False, "error": "Typing into the active UI requires explicit approval."}
    result = run_command(["ydotool", "type", "--", text], approve=True)
    return {"ok": result.ok, "stderr": result.stderr}
