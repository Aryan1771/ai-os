"""Import the graphical session for RE, start the core and resident companion."""
import os
import subprocess
import sys


def main():
    keys = ("DISPLAY", "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE",
            "HYPRLAND_INSTANCE_SIGNATURE", "XAUTHORITY")
    present = [key for key in keys if os.environ.get(key)]
    missing = [key for key in keys if key not in present]
    for args in (["unset-environment", *missing], ["import-environment", *present]):
        if len(args) > 1:
            subprocess.run(["/usr/bin/systemctl", "--user", *args],
                           check=True, timeout=10, shell=False)
    subprocess.run(["/usr/bin/systemctl", "--user", "restart", "ai-os.service"],
                   check=True, timeout=20, shell=False)
    # Existing LocalInstance guard prevents duplicate companions.
    os.execv(sys.executable, [sys.executable, "-m", "ai_os.avatar_overlay"])


if __name__ == "__main__":
    main()
