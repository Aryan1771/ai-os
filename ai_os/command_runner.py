"""Noninteractive command capture with a shared output cap and process-group cleanup."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time


def run_bounded(argv, *, cwd, timeout, output_limit=65536):
    process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               shell=False, start_new_session=True)
    output = {"stdout": bytearray(), "stderr": bytearray()}
    def stop():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)
    try:
        deadline = time.monotonic() + timeout
        capped = False
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(argv, timeout, output=bytes(output["stdout"]).decode(errors="replace"))
                for key, _ in selector.select(min(0.1, max(0, deadline-time.monotonic()))):
                    chunk = os.read(key.fileobj.fileno(), 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    remaining = output_limit - sum(map(len, output.values()))
                    output[key.data].extend(chunk[:max(0, remaining)])
                    if len(chunk) > remaining:
                        capped = True
                        break
                if capped:
                    break
        if capped:
            stop()
            error = "\nCommand stopped: combined output exceeded 64 KiB. Narrow the command or its result limit."
            return subprocess.CompletedProcess(argv, -9, output["stdout"].decode(errors="replace"),
                                               output["stderr"].decode(errors="replace") + error)
        process.wait(timeout=max(0.01, deadline-time.monotonic()))
        return subprocess.CompletedProcess(argv, process.returncode,
                                           output["stdout"].decode(errors="replace"),
                                           output["stderr"].decode(errors="replace"))
    finally:
        # Also terminate descendants that outlive a successfully exited parent.
        stop()
        process.stdout.close()
        process.stderr.close()
