# REgenOS Cool Cursors

The default theme is `REgenOS-Cool`, converted from Aryan's original
RealWorld Cursor Editor artwork in `Cool_cursor/`. The Windows files cannot
be used directly as Linux cursor themes. The build uses
[win2xcur 0.1.2](https://github.com/quantum5/win2xcur) and ImageMagick,
preserving source sizes, click hotspots and animated busy-frame delays.
Installed cursors work offline without the converter running.

## Install On Arch

After installing the REgenOS runtime, run as your desktop user:

```bash
cd ~/src/ai-os
git pull --ff-only
sudo pacman -Syu
bash scripts/install_cursor_theme.sh --apply
```

The native desktop installation stage also runs this step. It installs
ImageMagick and Adwaita fallback cursors via pacman, and the converter only
inside `~/.ai_os/venv`. Omit `--apply` to install without changing preferences.
Existing theme installations are renamed to unique backup directories;
configuration files retain their first `.regenos-backup` copy.

The theme lives in `${XDG_DATA_HOME:-$HOME/.local/share}/icons/REgenOS-Cool`.
GTK 3/4, Xcursor default inheritance and systemd user environment preferences
are set to this theme at size 32. GNOME preferences are updated when its schema
is available. A desktop settings daemon can override file preferences; select
`REgenOS-Cool` in that desktop's mouse settings if necessary. Existing REgenOS
configuration is not reset: choose `REgenOS-Cool` under Appearance if it still
contains the earlier Bibata value, then apply desktop appearance.

For Hyprland's hyprlang configuration, add this once to `hyprland.conf`:

```ini
source = ~/.config/hypr/regenos-cursor.conf
```

This selects Xcursor and disables native hyprcursor rendering for consistency.
Use the equivalent settings if your compositor version uses a different config
format. Log out and back in. Other native Wayland compositors have their own
cursor preference controls; this is not a universal Wayland setting.

For a minimal X11 session, add these before launching the window manager in
your existing `.xinitrc` (do not overwrite the file):

```bash
export XCURSOR_THEME=REgenOS-Cool
export XCURSOR_SIZE=32
xrdb -merge "${XDG_CONFIG_HOME:-$HOME/.config}/regenos/cursor.Xresources"
```

Install `xorg-xrdb` if needed. The theme does not change a TTY caret, firmware,
bootloader, or applications that draw their own pointer. Display-manager login
screens require separate configuration under their own service user.

## Validate And Revert

```bash
~/.ai_os/venv/bin/python -m pytest tests/test_cursor_theme.py -q
file ~/.local/share/icons/REgenOS-Cool/cursors/left_ptr
file ~/.local/share/icons/REgenOS-Cool/cursors/watch
```

On the actual desktop check pointer clicks, links, text selection, both resize
diagonals and animated wait. Windows-specific Location and Person are
retained under `regenos-*` custom names; unsupported roles such as forbidden
or grab inherit Adwaita. Select supplies the help pointer. Not every application uses
all twelve source images. Original resolutions are preserved, not upscaled.

To revert, select another installed theme in REgenOS Appearance and apply it,
and in your desktop's cursor settings where applicable. Alternatively restore
the affected `.regenos-backup` files. Update GNOME's cursor setting if it was
changed. Keep or remove the Hyprland include as appropriate, then log out/in.

## Ship In A Future ISO

Build into an unused output directory; the builder refuses to overwrite one:

```bash
cd ~/src/ai-os
~/.ai_os/venv/bin/python -m ai_os.cursor_theme Cool_cursor build/REgenOS-Cool
```

Copy `build/REgenOS-Cool` to the reviewed Archiso profile's
`airootfs/usr/share/icons/REgenOS-Cool`, retaining its attribution. Include
`adwaita-cursors` in the target package list (already in this repo's additions).
Use the following to write defaults inside the copied profile, not the host:

```bash
~/.ai_os/venv/bin/python - <<'PY'
from pathlib import Path
import shutil
from ai_os.cursor_theme import apply_preferences
root = Path.home() / 'iso-work/regenos/airootfs'
if not root.is_dir():
    raise SystemExit('Create and review the Archiso profile first')
target = root / 'usr/share/icons/REgenOS-Cool'
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree('build/REgenOS-Cool', target)
apply_preferences(root / 'etc/skel/.config', root / 'usr/share')
PY
```

Ensure the shipped X11/Hyprland session loads the cursor preferences as above.
If the chosen desktop uses GSettings, supply its distribution schema overrides
for cursor-theme and cursor-size as part of that desktop's packaging. Ensure
the future installer transfers both the theme and defaults to the target OS.
Defaults apply to new users; existing users keep their own preferences. Test
the live session and a newly installed account in a VM before distribution.
The repository still does not ship a finished ISO/graphical installer.
