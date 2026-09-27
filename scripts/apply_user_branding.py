"""Apply REgenOS cursor and wallpaper to GNOME; no system or boot changes."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ai_os.cursor_theme import THEME, apply_preferences, build_theme


def run(*argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True,
                          timeout=30, shell=False).stdout.strip()


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Run as your desktop user, not root")
    repo = Path(__file__).resolve().parents[1]
    data = Path(os.environ.get("XDG_DATA_HOME", str(Path.home()/".local/share")))
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home()/".config")))
    root = data / "regenos"
    root.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="appearance-backup-", dir=root))
    keys = [("org.gnome.desktop.interface", "cursor-theme", THEME),
            ("org.gnome.desktop.interface", "cursor-size", "32"),
            ("org.gnome.desktop.background", "picture-uri", (root/"wallpaper.png").as_uri()),
            ("org.gnome.desktop.background", "picture-uri-dark", (root/"wallpaper.png").as_uri())]
    previous = [{"schema": s, "key": k, "value": run("gsettings", "get", s, k)} for s,k,_ in keys]
    (backup/"gsettings.json").write_text(json.dumps(previous, indent=2))
    with tempfile.TemporaryDirectory(prefix="regenos-artwork-") as temporary:
        stage = Path(temporary)
        build_theme(repo/"Cool_cursor", stage/THEME)
        run("magick", str(repo/"branding/wallpapers/default.svg"), str(stage/"wallpaper.png"))
        icons = data/"icons"
        icons.mkdir(parents=True, exist_ok=True)
        target = icons/THEME
        if target.is_symlink():
            raise RuntimeError("Refusing to replace a symlink cursor theme")
        if target.exists():
            target.rename(backup/THEME)
        shutil.copytree(stage/THEME, target)
        if (root/"wallpaper.png").exists():
            shutil.copy2(root/"wallpaper.png", backup/"wallpaper.png")
        shutil.copy2(stage/"wallpaper.png", root/"wallpaper.png")
    apply_preferences(config, data)
    for schema,key,value in keys:
        run("gsettings", "set", schema, key, value)
    print("Applied REgenOS-Cool cursor and REgenOS wallpaper.")
    print("Previous GNOME settings and artwork backup:", backup)


if __name__ == "__main__":
    main()
