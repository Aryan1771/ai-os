"""Compatibility entry point for the native Python/PySide6 settings window."""

from __future__ import annotations


def main() -> int:
    from ai_os.native_settings import main as native_main

    return native_main()


if __name__ == "__main__":
    raise SystemExit(main())
