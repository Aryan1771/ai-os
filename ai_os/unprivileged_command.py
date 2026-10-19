"""Narrow same-user execution namespace for confirmed broad session grants."""
from __future__ import annotations

import os
from pathlib import Path
import sys


def bubblewrap_argv(command: list[str], home: Path, cwd: Path) -> list[str]:
    bwrap = "/usr/bin/bwrap"
    if not Path(bwrap).is_file():
        raise RuntimeError("Broad access requires bubblewrap; no unsandboxed fallback is allowed")
    home = home.resolve()
    cwd = cwd.resolve()
    if not cwd.is_dir():
        raise ValueError("Command working directory must exist")
    return [
        bwrap, "--die-with-parent", "--new-session", "--unshare-user", "--unshare-pid",
        "--unshare-ipc", "--unshare-uts", "--cap-drop", "ALL",
        "--ro-bind", "/", "/", "--dev", "/dev",
        "--proc", "/proc", "--tmpfs", "/tmp", "--tmpfs", "/run/dbus",
        "--tmpfs", "/run/user", "--bind", str(home), str(home),
        "--chdir", str(cwd), "--setenv", "HOME", str(home),
        "--setenv", "AI_OS_HOME", str(home / ".ai_os"),
        "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin",
        "--setenv", "LANG", os.environ.get("LANG", "C.UTF-8"),
        "--", *command,
    ]


def main():
    if sys.platform != "linux" or os.geteuid() == 0 or len(sys.argv) < 2:
        raise SystemExit("Broad command access requires a non-root Linux user")
    home = Path.home()
    cwd = Path.cwd()
    argv = bubblewrap_argv(sys.argv[1:], home, cwd)
    # Clear inherited API keys, D-Bus/display handles, and other ambient grants.
    environment = {
        "HOME": str(home), "AI_OS_HOME": str(home / ".ai_os"),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    os.execve(argv[0], argv, environment)


if __name__ == "__main__":
    main()
