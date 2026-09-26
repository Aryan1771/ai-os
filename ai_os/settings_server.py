"""Compatibility entry point; settings now run as a native Qt window."""

from ai_os.settings_store import save_settings  # noqa: F401


def main() -> int:
    from ai_os.hub_launcher import main as native_main

    return native_main()


if __name__ == "__main__":
    raise SystemExit(main())
