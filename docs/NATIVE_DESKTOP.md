# Native REgenOS Desktop

The native installer also installs and applies the original `REgenOS-Cool`
cursor theme. See [cursor setup](CURSOR_THEME.md) for session-specific activation,
backups, and rollback. Appearance applies cursor preferences to GTK 3/4 and
writes Xcursor environment and Hyprland session fragments; existing session
configuration must load those fragments as documented.

REgenOS Settings and Companion are Python programs using Qt Widgets through PySide6. They use local files and a user-local single-instance socket. They do not start an HTTP server, require a browser, use WebEngine/Electron, or download UI assets at runtime. Qt uses its Linux display backend; the daemon can still run on a bare TTY, while the two graphical programs need an X11 or Wayland desktop session.

## Install Or Upgrade On Arch

The first dependency/model download needs network access. Once dependencies and local models are installed, the UI and local AI pipeline can run disconnected.

```bash
cd ~/src/ai-os
git pull --ff-only
# Run runtime only if ~/.ai_os/venv does not exist yet:
# bash install/ai-os-install.sh runtime
bash install/ai-os-install.sh native
~/.ai_os/venv/bin/regenos-settings
```

The native stage adds Qt to the existing venv and installs desktop launchers. It does not install Hyprland. Launch **REgenOS Settings** from the desktop application menu, or use the command above. The installer disables the old `ai-os-settings.service` HTTP service. That unit has been removed from the repository. The old `python -m ai_os.settings_server` entry point now opens the native window for compatibility.

## Companion Controls

In **Companion**, save **Show corner companion** to enable or hide the resident overlay. Opening Settings starts the companion process when it is enabled. The overlay reloads its preferences about three times a second, including corner, size, accent, animation, fluid-motion strength, resting form, topic morphing, and emotion-bar visibility. Closing Settings leaves the companion running. Clicking the companion reopens Settings; its context menu can hide it.

Emotion baseline sliders control joy, curiosity, focus, calm, concern, and energy. **Emotional response** controls how strongly AI activity changes those values. These are simulated character values, not evidence of conscious feelings. The activity label exposes states such as armed, listening, transcribing, thinking, working, speaking, reply, and error. It does not display hidden model reasoning.

The renderer moves persistent colored pixels through damped springs and a wave field. It is a fluid-looking animation, not a physical fluid simulator. The core is a small robot with face changes. Twelve supplied forms cover a heart, music, code, idea, cloud, gear, shield, folder, chip, search, clock, and the core character. The model may additionally return a validated pixel pattern up to 24 by 24 cells. That permits new subject forms, but their visual quality depends on the model; malformed patterns fall back to the built-in behavior. No model-generated program is executed.

## Start At Login

For a desktop with XDG autostart support:

```bash
mkdir -p ~/.config/autostart
cp ~/.local/share/applications/regenos-companion.desktop ~/.config/autostart/
```

For Hyprland, install the desktop templates and add these lines to your existing `~/.config/hypr/hyprland.conf`:

```ini
source = ~/.config/hypr/regenos-bindings.conf
source = ~/.config/hypr/regenos-companion.conf
exec-once = ~/.ai_os/venv/bin/regenos-companion
```

The companion rules use Hyprland 0.53+ syntax. Verify with `hyprctl version` and `hyprctl clients -j`. The expected companion class is `regenos-companion`. Super+A launches the native Settings window; Super+Shift+A starts the resident companion, which honors the enable checkbox.

The overlay selects Qt's X11 backend through XWayland on Hyprland so that corner positioning is possible. Install `xorg-xwayland` and use the supplied floating/pinned rules. A pure Wayland session without XWayland cannot guarantee this window's position. On X11, transparency requires a compositor; a non-composited window manager may show an opaque background. Native layer-shell integration remains future work.

Alternatively, start the supplied user service from your graphical session. Choose the service or desktop autostart as your primary startup method:

```bash
mkdir -p ~/.config/systemd/user
cp ~/src/ai-os/systemd/ai-os-avatar.service ~/.config/systemd/user/
systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE
systemctl --user daemon-reload
systemctl --user enable --now ai-os-avatar.service
```

The service template assumes `~/src/ai-os` and `~/.ai_os`. For a custom installation directory, adjust the installed unit. A local lock prevents duplicate resident instances.

## Model, Voice And Appearance

- **AI connection:** select Ollama or an OpenAI-compatible server, endpoint and model. A loopback OpenAI-compatible server works offline. Remote endpoints require HTTPS, an approved hostname and online opt-in. API secrets remain in an environment variable, not the settings JSON.
- **Voice & listening:** select local Whisper/Piper files, wake threshold and capture duration. Start, restart and stop buttons control `ai-os.service`. Save and restart for microphone/model-path changes. Both wake-word and listening switches are required to start capture. See [voice setup](VOICE_AND_COMPANION.md).
- **Appearance:** choose a native window theme and branding paths. Saving records preferences. **Apply desktop appearance** explicitly writes user GTK icon/cursor/font settings and Hyprpaper/Hyprlock files, preserving a first `.regenos-backup` beside each existing file. Existing GTK keys are retained. Reload affected applications to see changes.
- **Permissions:** protected preference changes open a native confirmation dialog. Disabling that confirmation is itself protected. This is a local UI guard; it does not isolate the daemon from every process running under the same Linux user. Privileged action approvals remain terminal-based and are denied by background workers without an interactive terminal.

The window themes style the REgenOS programs. System-wide Qt/GTK themes, bootloader settings, firmware, partitions and the complete desktop settings stack are not controlled by this panel. Boot branding remains documented in [branding and ISO setup](BRANDING_AND_ARCHISO.md).

## Verify On Arch

```bash
cd ~/src/ai-os
source ~/.ai_os/venv/bin/activate
python -m pytest -q
regenos-settings
```

Manually verify: toggle visibility; move through all corners; resize the companion; change a baseline bar; disable animation; save/reopen Settings; then use voice and a harmless hardware query while observing the activity and forms. Observe `nvidia-smi` while Ollama, Whisper and Piper run together. Windows offscreen checks do not establish PipeWire behavior, compositor positioning, startup ordering or the 8 GB VRAM budget on the laptop.

For a local visual preview without starting services:

```bash
python scripts/render_native_preview.py --output /tmp/regenos-preview
```

References: [Qt Widgets](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html), [QPainter](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPainter.html), [Hyprland window rules](https://wiki.hypr.land/0.53.0/Configuring/Window-Rules/).
