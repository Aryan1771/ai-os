"""Apply only the user's GNOME pointer size and verify the live settings readback."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from ai_os.config import AI_OS_HOME, load_raw_config
from ai_os.settings_store import save_settings, validate_setting


def apply(size: int, home: Path = AI_OS_HOME) -> int:
    validate_setting("cursor_size", size)
    size = int(size)

    def setting(*arguments):
        try:
            process = subprocess.run(
                ["/usr/bin/gsettings", *arguments], capture_output=True, text=True,
                timeout=3, check=False, shell=False, stdin=subprocess.DEVNULL,
            )
        except subprocess.SubprocessError as exc:
            raise RuntimeError("GNOME cursor settings timed out. Run from your desktop session.") from exc
        if process.returncode:
            raise RuntimeError("GNOME cursor settings are unavailable. Run from your desktop session.")
        return process.stdout.strip()

    schema = "org.gnome.desktop.interface"
    previous = int(setting("get", schema, "cursor-size"))
    backup = home / "backups/cursor-size.json"
    backup.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with backup.open("x", encoding="utf-8") as handle:
            backup.chmod(0o600)
            json.dump({"schema": schema, "key": "cursor-size", "previous": previous}, handle)
    except FileExistsError:
        pass  # Preserve the original value across repeated applications.
    setting("set", schema, "cursor-size", str(size))
    actual = int(setting("get", schema, "cursor-size"))
    if actual != size:
        raise RuntimeError(
            f"Cursor size was not applied: GNOME still reports {actual}, requested {size}. "
            "Run this command from your actual desktop terminal; no sudo is needed."
        )
    save_settings({"cursor_size": size}, home)
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=int(load_raw_config(AI_OS_HOME)["cursor_size"]))
    args = parser.parse_args()
    try:
        actual = apply(args.size)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"GNOME cursor size verified: {actual}. Confirm visual size in your applications.")


if __name__ == "__main__":
    main()
