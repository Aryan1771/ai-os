"""Public operational events only: no chain of thought, arguments or output."""
import os
import re
import time

from ai_os.config import atomic_json

STATES = {"model", "tool_started", "tool_finished", "approval", "error", "cancelled", "reply"}


def record(home, state, tool=None):
    request_id = os.environ.get("AI_OS_REQUEST_ID", "")
    if home is None or not re.fullmatch(r"[0-9a-f]{32}", request_id) or state not in STATES:
        return
    event = {"request_id": request_id, "state": state, "updated_at": time.time()}
    if isinstance(tool, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,60}", tool):
        event["tool"] = tool
    try:
        atomic_json(home / "run/request-progress.json", event)
    except OSError:
        pass  # Status must never turn a completed action into a retry.
