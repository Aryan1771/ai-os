"""Compatibility entry point for the compiled C++ settings hub."""

from __future__ import annotations

import os
import subprocess
import sys

from ai_os.config import AI_OS_HOME


def main() -> int:
    name = "regenos-hub.exe" if os.name == "nt" else "regenos-hub"
    executable = AI_OS_HOME / "bin" / name
    if not executable.is_file():
        print("The C++ hub is not installed. Run: bash scripts/install_cpp_hub.sh", file=sys.stderr)
        return 1
    return subprocess.call([str(executable), "--python", sys.executable, *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
