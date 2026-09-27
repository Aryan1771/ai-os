"""Install backed-up user login startup, app icons and Hyprland Lua integration."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def install(home, repo):
    # The desktop/Lua templates use fixed trusted paths, never model-provided text.
    if any(c not in "/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for c in str(home)):
        raise ValueError("Home path needs explicit desktop/Lua quoting support")
    data, config = home/".local/share", home/".config"
    backups = data/"regenos"
    backups.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="session-backup-", dir=backups))

    def write(relative, content):
        target = home/relative
        if target.is_symlink():
            raise ValueError(f"Refusing to replace symlink: {target}")
        if target.exists():
            saved = backup/relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    write(".local/share/icons/hicolor/scalable/apps/regenos.svg", (repo/"branding/regenos-mark.svg").read_text())
    for app in ("settings", "companion"):
        text = (repo/f"config/desktop/regenos-{app}.desktop").read_text()
        text = text.replace(f"Exec=regenos-{app}", f"Exec={home}/.ai_os/venv/bin/regenos-{app}")
        write(f".local/share/applications/regenos-{app}.desktop", text)
    write(".config/autostart/regenos-session.desktop", "[Desktop Entry]\nType=Application\nName=RE — REgenOS assistant\n"
          f"Exec={home}/.ai_os/venv/bin/python -m ai_os.session_start\nIcon=regenos\n"
          "Terminal=false\nX-GNOME-Autostart-enabled=true\nNotShowIn=Hyprland;\n")
    write(".config/hypr/regenos.lua", (repo/"config/hypr/regenos.lua").read_text())
    main = config/"hypr/hyprland.lua"
    if main.exists():
        content = main.read_text()
    elif (config/"hypr/hyprland.conf").exists():
        raise ValueError("Existing legacy Hyprland config requires manual migration; not replacing it")
    else:
        content = Path("/usr/share/hypr/hyprland.lua").read_text().replace('local fileManager = "dolphin"', 'local fileManager = "thunar"')
    if 'require("regenos")' not in content:
        write(".config/hypr/hyprland.lua", content+'\n-- REgenOS native assistant integration\nrequire("regenos")\n')
    return backup


if __name__ == "__main__":
    if os.geteuid() == 0:
        raise SystemExit("Run as your desktop user")
    backup = install(Path.home(), Path(__file__).resolve().parents[1])
    subprocess.run(["systemctl", "--user", "enable", "ai-os.service"], check=True, timeout=10, shell=False)
    print("User session integration installed; backup:", backup)
