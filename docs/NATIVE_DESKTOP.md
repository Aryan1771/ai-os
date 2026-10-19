# Native REgenOS Desktop

New native launchers: **REgenOS Chat** (`regenos-chat`) has a compact live-avatar
composer (Enter send, Shift+Enter newline, Ctrl+Enter stop/steer) and expandable
operational activity. **REgenOS Research** (`regenos-research`) stores cited briefs
with a source reader and paused paragraph narration. Open either from Conversation.
See [controls and limits](RESEARCH_AND_CLEANUP.md). Shared styling and explicit
unsaved/save feedback are source-tested; this is not a claim that every OS control
or physical desktop interaction is verified. Reopen old application instances to
load new Python UI code.

The native installer also installs and applies the original `REgenOS-Cool`
cursor theme. See [cursor setup](CURSOR_THEME.md) for session-specific activation,
backups, and rollback. Appearance applies cursor preferences to GTK 3/4 and
writes Xcursor environment and Hyprland session fragments; existing session
configuration must load those fragments as documented.

The supported Settings and Companion applications use Python/PySide6 Qt Widgets.
The earlier C++ hub is retained as historical source, but is no longer launched or
built by the native installation stage. Python Conversation and Memory pages now provide named sessions, explicit
preferences/context notes, inspect and forget controls. Hardware policy and
Hindi/English voice controls are also present. See [runtime validation](RUNTIME_VALIDATION.md).
Both applications use local files and user-local IPC, without a browser or HTTP
settings endpoint. The core also runs on a bare TTY.

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

The native stage adds PySide6 to the existing venv for both applications. It does not install Hyprland. Launch **REgenOS Settings** from the application menu, or use the command above. The installer disables the old `ai-os-settings.service` HTTP service. The old `python -m ai_os.settings_server` entry point launches Python Settings for compatibility.

## Companion Controls

The dashboard header's **Unhide avatar** button is available on every page. It
restores saved visibility and starts the companion with `--show`. **Companion**
also has **Unhide / start avatar** and **Quit companion** at the top, above the
preview and long preferences form. **Show corner companion** controls the saved
visibility preference. The overlay reloads preferences about three times a
second; activating an existing enabled resident also reveals and repositions
its window. Closing Settings leaves the companion running. Clicking the avatar
reopens Settings; its context menu can hide it. The **REgenOS Companion** app-menu
entry passes `--show` as an independent recovery path.

After updating source, close the dashboard fully with its window close button,
handling any unsaved-changes prompt, then run `~/.ai_os/venv/bin/regenos-settings`.
Launching again while an old dashboard is running raises that existing window;
it cannot load new controls into already-imported Python code. No core service
restart is required just to load updated dashboard controls.

Emotion baseline sliders control joy, curiosity, focus, calm, concern, and energy. **Emotional response** controls how strongly AI activity changes those values. These are simulated character values, not evidence of conscious feelings. The activity label exposes states such as armed, listening, transcribing, thinking, working, speaking, reply, and error. It does not display hidden model reasoning.

The renderer moves persistent colored pixels through damped springs and a wave field. It is a fluid-looking animation, not a physical fluid simulator. The core is a small robot with face changes. Twelve supplied forms cover a heart, music, code, idea, cloud, gear, shield, folder, chip, search, clock, and the core character. The model may additionally return a validated pixel pattern up to 24 by 24 cells. That permits new subject forms, but their visual quality depends on the model; malformed patterns fall back to the built-in behavior. No model-generated program is executed.

## Start At Login

For the current installed Hyprland 0.56 / GNOME host, use the tested
[RE session installer](RE_SESSION_AND_IDENTITY.md). It installs GNOME autostart
and Hyprland **Lua** integration while retaining the active GNOME desktop.
The `.conf` instructions below describe older Hyprland versions; do not use them
unchanged on 0.55+.

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
- **Voice & listening:** select local Whisper/Piper files, conversation language, wake threshold, initial speech wait, ending silence and maximum utterance. The updated daemon reloads saved voice preferences. Loading source changes into an older resident process requires a reviewed restart; Start/Restart/Stop buttons control `ai-os.service`. Enable microphone listening and choose either wake-word gating or explicit conversation listening. See [voice setup](VOICE_AND_COMPANION.md).
- **Appearance:** choose a native window theme and branding paths. Saving records preferences. **Apply desktop appearance** explicitly writes user GTK icon/cursor/font settings and Hyprpaper/Hyprlock files, preserving a first `.regenos-backup` beside each existing file. Existing GTK keys are retained. Reload affected applications to see changes.
- **Permissions:** **Command access mode**, **Enable full access mode…**, **Revoke full access**, and status are at the top. The enable button selects the mode after you choose a duration and confirm the native scope dialog (default No); cancellation preserves saved settings and unsaved edits. Status refreshes once a second. It applies to the default session, including voice, until expiry or revocation. It runs ordinary commands as the logged-in user without repeated prompts; that exposes the user's files and credentials to those programs. Privilege helpers, physical disks, mounts, boot and security operations remain separately blocked/reviewed; this is neither root access nor a guarantee of account isolation. Bubblewrap is required and there is no unsandboxed fallback. Protected preference changes also open a native confirmation dialog. Disabling that confirmation is itself protected.

The window themes style the REgenOS programs. System-wide Qt/GTK themes, bootloader settings, firmware, partitions and the complete desktop settings stack are not controlled by this panel. Boot branding remains documented in [branding and ISO setup](BRANDING_AND_ARCHISO.md).

## Verify On Arch

```bash
cd ~/src/ai-os
source ~/.ai_os/venv/bin/activate
python -m pytest -q
regenos-settings
```

Manually verify: toggle visibility; move through all corners; resize the companion; change a baseline bar; disable animation; save/reopen Settings; then use voice and a harmless hardware query while observing the activity and forms. Observe `nvidia-smi` while Ollama, Whisper and Piper run together. Windows offscreen checks do not establish PipeWire behavior, compositor positioning, startup ordering or the 8 GB VRAM budget on the laptop.

References: [Qt Widgets](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html), [QPainter](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPainter.html), [Hyprland window rules](https://wiki.hypr.land/0.53.0/Configuring/Window-Rules/).


## Move the companion between displays

Drag the avatar onto another display, or right-click it and select **Move to
display → display name**. Native Companion settings also provide a Display
selector. The selected Qt display name is saved in `avatar_display`; corner
settings apply on that display. Dragging uses global logical coordinates and
clamps to the destination display's usable area. Removing the display falls back
to an available display, while retaining the preference for reconnection.
Identical/changed Qt screen names are not guaranteed stable hardware identity.

Qt APIs: [screenAt](https://doc.qt.io/qt-6/qguiapplication.html#screenAt) and
[availableGeometry](https://doc.qt.io/qt-6/qscreen.html#availableGeometry-prop).
The existing companion launcher prefers XWayland on GNOME when X11 is available;
pure native Wayland placement remains compositor-dependent and unverified.

2026-10-17: synthetic transfer/reconnect tests pass. No physical monitor transfer
was performed in this restricted execution environment. The existing companion
must reload updated Python code before these new controls appear; restarting
only the core service does not necessarily restart the separate companion.

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_avatar_displays.py
```

To close the companion independently of the core, use dashboard Companion → **Quit companion** or the avatar menu → **Quit companion**. For an already-running older version without that menu, run `~/.ai_os/venv/bin/python -m ai_os.companion_control` from the desktop terminal. This sends graceful termination only to the current user’s exact companion entry points. No forced kill is sent.

The application-menu settings entry is searchable as **REgenOS Dashboard** (AI, assistant, settings and companion keywords). **REgenOS Companion** passes `--show` to reveal an avatar saved as hidden, including when a resident already exists. Startup without that flag preserves the saved visibility preference. The 2026-10-17 user-launcher repair passed desktop-file validation and Gio `should_show=true`; GNOME visual search remains unverified from the restricted session.
