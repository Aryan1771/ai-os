#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${AI_OS_HOME:-${HOME}/.ai_os}/venv/bin/python"
if [[ ${EUID} -eq 0 || ! -x "${PYTHON}" ]]; then
  echo "Run as your desktop user after installing the REgenOS runtime." >&2
  exit 1
fi
case "${1:-}" in
  ""|--apply) ;;
  *) echo "Usage: bash scripts/install_cursor_theme.sh [--apply]" >&2; exit 2 ;;
esac
sudo pacman -S --needed imagemagick adwaita-cursors
"${PYTHON}" -m pip install 'win2xcur==0.1.2'
cd "${REPO_ROOT}"
"${PYTHON}" - "${REPO_ROOT}" "${1:-}" <<'PY'
import os
import sys
import tempfile
from pathlib import Path
from ai_os.cursor_theme import THEME, apply_preferences, build_theme

repo = Path(sys.argv[1])
data = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
icons = data / "icons"
icons.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix=".regenos-cursors-", dir=icons) as temporary:
    stage = Path(temporary) / THEME
    build_theme(repo / "Cool_cursor", stage)
    target = icons / THEME
    if target.is_symlink():
        raise RuntimeError(f"Refusing to replace a symlink: {target}")
    backup = None
    if target.exists():
        backup = Path(tempfile.mkdtemp(prefix=f"{THEME}-backup-", dir=icons)) / THEME
        target.rename(backup)
    try:
        stage.rename(target)
    except OSError:
        if backup is not None:
            backup.rename(target)
        raise
    if backup is not None:
        print(f"Previous theme preserved at {backup}")
if sys.argv[2] == "--apply":
    apply_preferences(config, data)
print(f"Installed {target}")
PY
if [[ "${1:-}" == --apply ]]; then
  if command -v gsettings >/dev/null && gsettings list-schemas | grep -qx org.gnome.desktop.interface; then
    echo "Previous GNOME cursor: $(gsettings get org.gnome.desktop.interface cursor-theme)"
    gsettings set org.gnome.desktop.interface cursor-theme REgenOS-Cool
    gsettings set org.gnome.desktop.interface cursor-size 32
  fi
  echo "Log out and back in. See docs/CURSOR_THEME.md for X11/Hyprland session setup."
fi
