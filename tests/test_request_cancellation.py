"""Real harmless worker cancellation must unwind separately grouped commands."""
import json
import os
import signal
import subprocess
import sys
import time

import psutil

from ai_os.settings_store import save_settings


def test_bridge_sigterm_reaps_noninteractive_tool_group(tmp_path):
    save_settings({"command_access": "supervised"}, tmp_path, human_confirmed=True)
    environment = os.environ | {"AI_OS_HOME": str(tmp_path)}
    process = subprocess.Popen([sys.executable, "-m", "ai_os.hub_bridge"], stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               env=environment, start_new_session=True)
    child = None
    try:
        payload = {"action": "approved_command", "confirmed": True,
                   "arguments": {"command": ["/usr/bin/sleep", "30"], "cwd": str(tmp_path), "timeout_sec": 40}}
        process.stdin.write(json.dumps(payload).encode())
        process.stdin.close()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            children = psutil.Process(process.pid).children(recursive=True)
            if children:
                child = children[0]
                break
            time.sleep(.02)
        assert child is not None
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
        assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)
        if child is not None and child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
            child.kill()
