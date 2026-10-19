"""Exact, human-reviewed interactive commands in a visible native terminal.

Never expose ``launch_terminal_command`` as a model tool. A launch acknowledgement
means only that a terminal was requested, not that the command ran or succeeded.
This is a same-account review boundary, not an independent privilege broker.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time

from ai_os.tools.system_tools import RiskLevel, assess_command

MAX_TASK_SECONDS = 900
MAX_FILE_BYTES = 32768
JOB_PATTERN = re.compile(r"[0-9a-f]{32}\Z")
_DISK_TOOLS = {
    "dd", "fdisk", "cfdisk", "sfdisk", "parted", "gparted", "sgdisk", "gdisk",
    "wipefs", "cryptsetup", "mount", "umount", "losetup", "swapon", "swapoff",
    "mkswap", "grub-install", "bootctl", "efibootmgr", "mkinitcpio", "dracut",
    "arch-chroot", "chroot", "nsenter", "unshare", "pkexec", "su", "doas", "sudo",
}
_CODE_RUNNERS = {
    "sh", "bash", "dash", "zsh", "fish", "ksh", "csh", "tcsh", "env",
    "python", "python3", "perl", "ruby", "node", "nodejs", "php", "lua",
    "luajit", "awk", "gawk", "mawk", "xargs", "eval", "exec", "busybox", "toybox",
    "flatpak-spawn", "systemd-run", "chrt", "nice", "nohup", "timeout", "setsid",
}


def _checked_arguments(arguments: dict) -> dict:
    if not isinstance(arguments, dict) or set(arguments) - {"command", "cwd", "timeout_sec"}:
        raise ValueError("Only command, cwd and timeout_sec are supported")
    assessment = assess_command(arguments.get("command", []))
    if assessment.risk == RiskLevel.PROHIBITED:
        raise ValueError("This command is prohibited by the disk/safety policy")
    argv = assessment.command
    target = argv
    if Path(argv[0]).name == "sudo":
        target = argv[1:]
        if not target or target[0].startswith("-"):
            raise ValueError("Use sudo followed directly by the program; passwords stay in the terminal")
        if not os.access("/usr/bin/timeout", os.X_OK):
            raise ValueError("Interactive sudo requires the system timeout helper")
    name = Path(target[0]).name
    nested = assess_command(target)
    if (nested.risk == RiskLevel.PROHIBITED or name in _DISK_TOOLS
            or name.startswith(("mkfs", "fsck"))):
        raise ValueError("Disk, mount, boot and privilege-wrapper commands need a separate workflow")
    if name in _CODE_RUNNERS or re.fullmatch(r"python\d+(?:\.\d+)?", name):
        raise ValueError("Shell/interpreter snippets and command wrappers are not supported by terminal review")
    if name == "find" and any(a in {"-exec", "-execdir", "-ok", "-okdir"} for a in target[1:]):
        raise ValueError("Indirect command execution needs a separate reviewed command")
    cwd = arguments.get("cwd") or str(Path.home())
    if not isinstance(cwd, str) or not cwd.isprintable() or len(cwd) > 4096:
        raise ValueError("Working directory must be a printable path")
    cwd_path = Path(cwd).expanduser().resolve(strict=True)
    if not cwd_path.is_dir():
        raise ValueError("Working directory does not exist")
    executable = shutil.which(target[0])
    if executable is None:
        raise ValueError("Requested executable is not installed or executable")
    executable_path = Path(executable).resolve(strict=True)
    resolved_name = executable_path.name
    if (resolved_name in _DISK_TOOLS or resolved_name in _CODE_RUNNERS
            or resolved_name.startswith(("mkfs", "fsck"))
            or re.fullmatch(r"python\d+(?:\.\d+)?", resolved_name)):
        raise ValueError("Executable aliases cannot bypass command review restrictions")
    # Human review covers installed binaries, not editable scripts which could
    # silently hide another command or bypass the explicit disk boundary.
    with executable_path.open("rb") as stream:
        if stream.read(2) == b"#!":
            raise ValueError("Script executables need a separate audited workflow")
    target = [str(executable_path), *target[1:]]
    argv = (["/usr/bin/sudo", *target] if Path(argv[0]).name == "sudo" else target)
    seconds = arguments.get("timeout_sec", MAX_TASK_SECONDS)
    if type(seconds) is not int or not 1 <= seconds <= MAX_TASK_SECONDS:
        raise ValueError(f"Duration must be an integer from 1 to {MAX_TASK_SECONDS} seconds")
    return {"command": argv, "cwd": str(cwd_path), "timeout_sec": seconds}


def propose_terminal_command(command, cwd=None, timeout_sec=MAX_TASK_SECONDS) -> dict:
    """Return an exact proposal; this function never starts a program."""
    arguments = _checked_arguments({"command": command, "cwd": cwd, "timeout_sec": timeout_sec})
    return {"ok": False,
            "message": "Review this exact command in the native confirmation. It runs in a visible terminal; enter any sudo password there only.",
            "approval_required": {"tool": "run_terminal_command", "arguments": arguments}}


def _task_directory(home: Path, *, create: bool) -> Path:
    home = Path(home).expanduser().absolute()
    current = home
    for part in (None, "run", "private", "terminal_tasks"):
        if part is not None:
            current = current / part
        if create:
            current.mkdir(mode=0o700, exist_ok=True)
        info = current.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or (part == "terminal_tasks" and stat.S_IMODE(info.st_mode) & 0o077)):
            raise ValueError("Terminal task storage must be owned, private directories without symlinks")
    return current


def _job_path(directory: Path, job_id: str, suffix: str) -> Path:
    if not isinstance(job_id, str) or JOB_PATTERN.fullmatch(job_id) is None:
        raise ValueError("Invalid terminal job ID")
    return directory / (job_id + suffix)


def _write_private(path: Path, value: dict, *, replace=False) -> None:
    data = json.dumps(value, ensure_ascii=True).encode("utf-8")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Terminal job metadata exceeds its size limit")
    target = path.with_name(path.name + "." + secrets.token_hex(6) + ".tmp") if replace else path
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        if replace:
            os.replace(target, path)
    finally:
        if replace:
            target.unlink(missing_ok=True)


def _read_private(path: Path) -> dict:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > MAX_FILE_BYTES):
            raise ValueError("Unsafe terminal job metadata")
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Terminal job metadata exceeds its size limit")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("Invalid terminal job metadata")
    return value


def _find_terminal() -> list[str]:
    for executable, options in (
        ("/usr/bin/gnome-terminal", ["--title=REgenOS reviewed command", "--"]),
        ("/usr/bin/kitty", ["--title", "REgenOS reviewed command", "--"]),
        ("/usr/bin/konsole", ["--separate", "-e"]),
        ("/usr/bin/xterm", ["-T", "REgenOS reviewed command", "-e"]),
    ):
        if Path(executable).is_file() and os.access(executable, os.X_OK):
            return [executable, *options]
    raise ValueError("Install a supported terminal: GNOME Terminal, Kitty, Konsole or xterm")


def launch_terminal_command(arguments: dict, *, home=None, human_confirmed=False) -> dict:
    """Trusted native approval path only. Never register this as a model tool."""
    if human_confirmed is not True:
        return {"ok": False, "error": "Exact native human confirmation is required"}
    from ai_os.config import AI_OS_HOME

    spec = _checked_arguments(arguments)
    terminal = _find_terminal()
    directory = _task_directory(Path(home) if home is not None else AI_OS_HOME, create=True)
    job_id = secrets.token_hex(16)
    job_path = _job_path(directory, job_id, ".json")
    status_path = _job_path(directory, job_id, ".status.json")
    _write_private(job_path, {"version": 1, **spec})
    _write_private(status_path, {"status": "queued", "updated_at": time.time()})
    launcher = terminal + [sys.executable, "-m", "ai_os.terminal_task_runner",
                           "--home", str(directory.parents[2]), "--job", job_id]
    try:
        subprocess.Popen(launcher, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, shell=False, start_new_session=True)
    except OSError:
        job_path.unlink(missing_ok=True)
        _write_private(status_path, {"status": "launch_failed", "updated_at": time.time()}, replace=True)
        return {"ok": False, "job_id": job_id, "error": "The terminal could not be started"}
    return {"ok": True, "job_id": job_id, "status": "queued",
            "message": "Terminal launch requested; command completion is not confirmed. Check terminal_task_status for the exit result."}


def terminal_task_status(job_id: str, *, home=None) -> dict:
    """Read bounded status only; never return command text, output or passwords."""
    from ai_os.config import AI_OS_HOME

    try:
        directory = _task_directory(Path(home) if home is not None else AI_OS_HOME, create=False)
        value = _read_private(_job_path(directory, job_id, ".status.json"))
    except FileNotFoundError:
        return {"ok": False, "job_id": job_id, "status": "not_found"}
    allowed = {"status", "updated_at", "returncode", "duration_sec"}
    result = {key: value[key] for key in allowed & value.keys()}
    return {"ok": True, "job_id": job_id, **result}
