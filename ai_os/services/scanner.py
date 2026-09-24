from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScanResult:
    ok: bool
    infected: bool
    output: str
    error: str = ""


def scan_file(path: Path, timeout_sec: int = 180) -> ScanResult:
    if not path.is_file():
        return ScanResult(False, False, "", f"File is missing: {path}")
    if not shutil.which("clamscan"):
        return ScanResult(False, False, "", "clamscan is not installed.")
    try:
        result = subprocess.run(
            ["clamscan", "--no-summary", "--", str(path)],
            capture_output=True,
            check=False,
            text=True,
            timeout=max(1, int(timeout_sec)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ScanResult(False, False, "", str(exc))
    infected = result.returncode == 1
    if result.returncode not in {0, 1}:
        return ScanResult(False, False, result.stdout.strip(), result.stderr.strip())
    return ScanResult(True, infected, result.stdout.strip(), result.stderr.strip())
