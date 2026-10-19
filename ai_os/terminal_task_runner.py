"""Visible terminal worker. Output/password input stays in the terminal only."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from ai_os.terminal_tasks import (
    _checked_arguments, _job_path, _read_private, _task_directory, _write_private,
)


def _bounded_argv(spec: dict) -> list[str]:
    argv = spec["command"]
    if argv[0] == "/usr/bin/sudo":
        # A user process cannot kill arbitrary root children. Start the fixed
        # foreground deadline helper *after* sudo authentication, as root too.
        return [argv[0], "/usr/bin/timeout", "--foreground", "--signal=TERM",
                "--kill-after=2s", f"{spec['timeout_sec']}s", *argv[1:]]
    return argv


def _stop_process_group(process) -> bool:
    """Report when cleanup cannot be established, especially for root children."""
    stopped = True
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        stopped = False
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        stopped = False
    return stopped


def _execute(spec: dict) -> dict:
    started = time.monotonic()
    tty = sys.stdin.fileno()
    previous_group = os.tcgetpgrp(tty)
    old_handler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    def cancelled(signum, frame):
        raise InterruptedError("The visible terminal task was interrupted")
    interrupted_signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    old_interrupt_handlers = {sig: signal.signal(sig, cancelled) for sig in interrupted_signals}
    process = None
    cleanup_confirmed = True
    try:
        process = subprocess.Popen(_bounded_argv(spec), cwd=spec["cwd"], shell=False, process_group=0)
        # Keep the child's /dev/tty authentication interactive while placing
        # descendants in a separate process group for timeout cleanup.
        os.tcsetpgrp(tty, process.pid)
        os.killpg(process.pid, signal.SIGCONT)
        try:
            result = process.wait(timeout=spec["timeout_sec"])
            status = ("timed_out" if spec["command"][0] == "/usr/bin/sudo"
                      and result in {124, 137} else "completed")
        except subprocess.TimeoutExpired:
            result = None
            status = "timed_out"
        finally:
            cleanup_confirmed = _stop_process_group(process)
    finally:
        try:
            if process is not None and process.poll() is None:
                cleanup_confirmed = _stop_process_group(process) and cleanup_confirmed
        finally:
            try:
                os.tcsetpgrp(tty, previous_group)
            finally:
                signal.signal(signal.SIGTTOU, old_handler)
                for sig, handler in old_interrupt_handlers.items():
                    signal.signal(sig, handler)
    return {"status": status if cleanup_confirmed else "cleanup_unconfirmed", "returncode": result,
            "duration_sec": round(time.monotonic() - started, 3), "updated_at": time.time()}


def run_job(home: Path, job_id: str) -> int:
    directory = _task_directory(home, create=False)
    claim = _job_path(directory, job_id, ".claim")
    try:
        fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(fd)
    except FileExistsError:
        return 2
    job_path = _job_path(directory, job_id, ".json")
    status_path = _job_path(directory, job_id, ".status.json")
    try:
        value = _read_private(job_path)
        if value.pop("version", None) != 1 or not sys.stdin.isatty():
            raise ValueError("A valid job in a visible interactive terminal is required")
        spec = _checked_arguments(value)
        _write_private(status_path, {"status": "running", "updated_at": time.time()}, replace=True)
        print("REgenOS: the exact command you approved is running in this terminal.")
        print("Enter any authentication password here only. Output is not saved or sent to the AI.", flush=True)
        result = _execute(spec)
        _write_private(status_path, result, replace=True)
        print(f"\nREgenOS task {result['status']}; exit code: {result['returncode']}", flush=True)
        return 0 if result["status"] == "completed" and result["returncode"] == 0 else 1
    except (OSError, ValueError, subprocess.SubprocessError):
        _write_private(status_path, {"status": "failed", "updated_at": time.time()}, replace=True)
        print("REgenOS could not run this reviewed terminal task.", file=sys.stderr)
        return 1
    finally:
        # Exact argv may contain private data; retain only bounded exit metadata.
        job_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    return run_job(args.home, args.job)


if __name__ == "__main__":
    raise SystemExit(main())
