from __future__ import annotations

import json
import re
import shlex
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import psutil


class RiskLevel(str, Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DESTRUCTIVE = "destructive"
    PROHIBITED = "prohibited"


@dataclass(frozen=True)
class CommandAssessment:
    command: list[str]
    risk: RiskLevel
    reason: str
    requires_approval: bool


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    assessment: CommandAssessment
    returncode: int | None
    stdout: str
    stderr: str
    duration_sec: float


SAFE_READ_COMMANDS = {
    "awk",
    "basename",
    "cat",
    "date",
    "df",
    "dirname",
    "du",
    "echo",
    "file",
    "find",
    "free",
    "grep",
    "head",
    "hostnamectl",
    "id",
    "ip",
    "journalctl",
    "ls",
    "lsblk",
    "lscpu",
    "lspci",
    "lsusb",
    "nvidia-smi",
    "pacman",
    "pgrep",
    "ps",
    "pwd",
    "rg",
    "sed",
    "sensors",
    "ss",
    "stat",
    "systemctl",
    "tail",
    "uname",
    "uptime",
    "wc",
    "which",
    "whoami",
    "wpctl",
    "brightnessctl",
}

MODERATE_COMMANDS = {"kill", "killall", "pkill", "mv", "cp", "chmod", "chown", "chgrp"}

DESTRUCTIVE_COMMANDS = {
    "dd",
    "fdisk",
    "mkfs",
    "mount",
    "pacman",
    "parted",
    "poweroff",
    "reboot",
    "rm",
    "rmdir",
    "sgdisk",
    "shutdown",
    "systemctl",
    "umount",
    "userdel",
    "wipefs",
    "yay",
    "paru",
}

PROHIBITED_PATTERNS = [
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r"\bdd\s+.*\bof=/dev/",
    r"\bmkfs(\.\w+)?\b",
    r"\bwipefs\b",
    r"\brm\s+(-[^\s]*[rf][^\s]*|-rf|-fr)\s+/(?:\s|$)",
    r">\s*/dev/sd[a-z]",
    r">\s*/dev/nvme\d+n\d+",
]


def _normalize_command(command: str | list[str]) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return [str(part) for part in command]


def assess_command(command: str | list[str]) -> CommandAssessment:
    argv = _normalize_command(command)
    if not argv:
        return CommandAssessment(argv, RiskLevel.PROHIBITED, "Empty command.", True)

    raw = " ".join(shlex.quote(part) for part in argv)
    executable = Path(argv[0]).name

    for pattern in PROHIBITED_PATTERNS:
        if re.search(pattern, raw):
            return CommandAssessment(
                argv, RiskLevel.PROHIBITED, f"Matched prohibited pattern: {pattern}", True
            )

    if executable in {"sudo", "su", "doas"}:
        return CommandAssessment(argv, RiskLevel.DESTRUCTIVE, "Privilege escalation requested.", True)

    if any(token in raw for token in ["&&", "||", ";", "|", "`", "$(", ">", ">>", "<"]):
        return CommandAssessment(argv, RiskLevel.MODERATE, "Shell syntax requires review.", True)

    if executable == "pacman":
        readonly_flags = {"-Q", "-Qs", "-Qi", "-Ql", "-Qq", "-Qe", "-Qu"}
        if any(flag in argv for flag in readonly_flags):
            return CommandAssessment(argv, RiskLevel.SAFE, "Read-only pacman query.", False)
        return CommandAssessment(argv, RiskLevel.DESTRUCTIVE, "Package database mutation possible.", True)

    if executable == "systemctl":
        readonly_verbs = {"status", "is-active", "is-enabled", "list-units", "list-unit-files"}
        if len(argv) >= 2 and argv[1] in readonly_verbs:
            return CommandAssessment(argv, RiskLevel.SAFE, "Read-only systemctl query.", False)
        return CommandAssessment(argv, RiskLevel.DESTRUCTIVE, "Service state mutation possible.", True)

    if executable in MODERATE_COMMANDS:
        return CommandAssessment(argv, RiskLevel.MODERATE, f"{executable} changes process/files.", True)

    if executable in DESTRUCTIVE_COMMANDS:
        return CommandAssessment(argv, RiskLevel.DESTRUCTIVE, f"{executable} can modify system state.", True)

    if executable in SAFE_READ_COMMANDS:
        return CommandAssessment(argv, RiskLevel.SAFE, "Recognized read/query command.", False)

    return CommandAssessment(argv, RiskLevel.MODERATE, "Unknown command requires approval.", True)


def run_command(
    command: str | list[str],
    *,
    timeout_sec: int = 15,
    cwd: str | None = None,
    approve: bool = False,
) -> CommandResult:
    assessment = assess_command(command)
    start = time.monotonic()

    if assessment.risk == RiskLevel.PROHIBITED:
        return CommandResult(False, assessment, None, "", "Command prohibited by safety policy.", 0.0)

    if assessment.requires_approval and not approve:
        return CommandResult(
            False,
            assessment,
            None,
            "",
            "Command requires explicit user approval.",
            0.0,
        )

    try:
        proc = subprocess.run(
            assessment.command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            shell=False,
        )
        return CommandResult(
            ok=proc.returncode == 0,
            assessment=assessment,
            returncode=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            duration_sec=round(time.monotonic() - start, 3),
        )
    except FileNotFoundError as exc:
        return CommandResult(False, assessment, None, "", str(exc), round(time.monotonic() - start, 3))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.strip() if isinstance(exc.stdout, str) else ""
        return CommandResult(
            False,
            assessment,
            None,
            stdout,
            f"Command timed out after {timeout_sec}s.",
            round(time.monotonic() - start, 3),
        )


def list_processes(limit: int = 25) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "cmdline"]):
        try:
            info = proc.info
            rows.append(
                {
                    "pid": info["pid"],
                    "name": info["name"],
                    "user": info["username"],
                    "cpu_percent": info["cpu_percent"],
                    "memory_percent": round(info["memory_percent"], 2),
                    "cmdline": " ".join(info["cmdline"] or [])[:240],
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    rows.sort(key=lambda row: (row["cpu_percent"], row["memory_percent"]), reverse=True)
    return rows[: max(1, int(limit))]


def terminate_process(pid: int, *, approve: bool = False, force: bool = False) -> dict[str, Any]:
    if not approve:
        return {"ok": False, "risk": RiskLevel.MODERATE.value, "error": "Approval required."}
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.send_signal(sig)
        return {"ok": True, "pid": pid, "name": name, "signal": sig.name}
    except psutil.NoSuchProcess:
        return {"ok": False, "pid": pid, "error": "Process does not exist."}
    except psutil.AccessDenied:
        return {"ok": False, "pid": pid, "error": "Access denied."}


def get_nvidia_stats() -> dict[str, Any] | None:
    result = run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ],
        timeout_sec=5,
    )
    if not result.ok:
        return None
    parts = [part.strip() for part in result.stdout.split(",", 6)]
    if len(parts) != 7:
        return {"raw": result.stdout}
    return {
        "name": parts[0],
        "memory_total_mb": int(float(parts[1])),
        "memory_used_mb": int(float(parts[2])),
        "memory_free_mb": int(float(parts[3])),
        "gpu_util_percent": int(float(parts[4])),
        "temperature_c": int(float(parts[5])),
        "power_draw_w": None if parts[6] == "[Not Supported]" else float(parts[6]),
    }


def get_hardware_stats() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")
    battery = psutil.sensors_battery()
    return {
        "cpu": {
            "percent": psutil.cpu_percent(interval=0.5),
            "per_core_percent": psutil.cpu_percent(interval=None, percpu=True),
            "logical_cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
        },
        "memory": {
            "total_gb": round(vm.total / 1024**3, 2),
            "used_gb": round(vm.used / 1024**3, 2),
            "available_gb": round(vm.available / 1024**3, 2),
            "percent": vm.percent,
        },
        "swap": {
            "total_gb": round(swap.total / 1024**3, 2),
            "used_gb": round(swap.used / 1024**3, 2),
            "percent": swap.percent,
        },
        "disk_root": {
            "total_gb": round(disk.total / 1024**3, 2),
            "used_gb": round(disk.used / 1024**3, 2),
            "free_gb": round(disk.free / 1024**3, 2),
            "percent": disk.percent,
        },
        "battery": None
        if battery is None
        else {
            "percent": battery.percent,
            "plugged": battery.power_plugged,
            "seconds_left": battery.secsleft,
        },
        "nvidia": get_nvidia_stats(),
    }


def get_volume() -> dict[str, Any]:
    result = run_command(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
    if not result.ok:
        return {"ok": False, "error": result.stderr}
    muted = "[MUTED]" in result.stdout
    match = re.search(r"Volume:\s+([0-9.]+)", result.stdout)
    volume_percent = round(float(match.group(1)) * 100) if match else None
    return {"ok": True, "volume_percent": volume_percent, "muted": muted, "raw": result.stdout}


def set_volume(percent: int) -> dict[str, Any]:
    bounded = max(0, min(150, int(percent)))
    result = run_command(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{bounded}%"], approve=True)
    return {"ok": result.ok, "volume_percent": bounded, "stderr": result.stderr}


def mute_volume(mute: bool) -> dict[str, Any]:
    result = run_command(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1" if mute else "0"], approve=True)
    return {"ok": result.ok, "muted": mute, "stderr": result.stderr}


def get_brightness() -> dict[str, Any]:
    current = run_command(["brightnessctl", "get"])
    maximum = run_command(["brightnessctl", "max"])
    if not current.ok or not maximum.ok:
        return {"ok": False, "error": current.stderr or maximum.stderr}
    cur = int(current.stdout)
    max_value = int(maximum.stdout)
    percent = round((cur / max_value) * 100) if max_value else 0
    return {"ok": True, "brightness_percent": percent, "raw_current": cur, "raw_max": max_value}


def set_brightness(percent: int) -> dict[str, Any]:
    bounded = max(1, min(100, int(percent)))
    result = run_command(["brightnessctl", "set", f"{bounded}%"], approve=True)
    return {"ok": result.ok, "brightness_percent": bounded, "stderr": result.stderr}


def dataclass_json(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    return value


if __name__ == "__main__":
    snapshot = {
        "hardware": get_hardware_stats(),
        "volume": get_volume(),
        "brightness": get_brightness(),
        "top_processes": list_processes(10),
        "safe_command_test": run_command(["uname", "-a"]),
        "destructive_command_test": run_command(["sudo", "pacman", "-S", "vim"]),
    }
    print(json.dumps(snapshot, indent=2, default=dataclass_json))

