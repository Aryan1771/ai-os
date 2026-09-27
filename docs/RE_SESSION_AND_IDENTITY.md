# RE, startup and desktop identity

2026-09-28. The assistant is **RE**, pronounced as the letters **R E**. The product
is **REgenOS**, an Arch desktop/runtime prototype. The prompt uses this name and
Piper input expands standalone `RE` to `R E`; displayed text stays unchanged.

## Installed user session

```bash
~/.ai_os/venv/bin/python scripts/install_user_session.py
Hyprland --verify-config -c ~/.config/hypr/hyprland.lua
systemctl --user is-enabled ai-os.service
```

The core is enabled for user-session startup. The installer adds a GNOME/XDG
autostart entry for the companion/session helper, installs application launchers
with absolute venv paths and the original logo, and adds Hyprland Lua integration.
The helper imports only named graphical environment variables, clears stale ones,
restarts the user core with that environment, and starts the singleton companion.
It does not enable microphone listening, install lingering, or run before login.
No default desktop switch occurs. User requested keeping GNOME.

Installation backup: `~/.local/share/regenos/session-backup-bbla6mfj`.
Runtime backup before preferences changed: `~/.ai_os/backups/pre-migration-gv3k4ce8`.
Rollback: disable/remove `~/.config/autostart/regenos-session.desktop`, restore
affected files from that backup, and remove the added `require("regenos")` line
if reverting Hyprland integration. Disabling core autostart is
`systemctl --user disable ai-os.service`; stopping it also stops its listener.

Your original `Cool_cursor` artwork is already installed as **REgenOS-Cool** and
selected in GNOME. The new Hyprland integration sets Xcursor theme/size and calls
`hyprctl setcursor REgenOS-Cool 32` at session start. Existing appearance backup:
`~/.local/share/regenos/appearance-backup-h7dv8w3x`. Some apps need reopening.

## Hyprland integration

Installed Hyprland is **0.56.2**. Since 0.55, configuration moved to Lua; use
`config/hypr/regenos.lua` with this installation, not the older `.conf` templates.
The installed default Lua configuration was extended without switching GNOME.
Both the standalone integration and installed combined configuration pass
`Hyprland --verify-config`. See [upstream configuration](https://wiki.hypr.land/Configuring/Start/).

Super+A opens the hub; Super+Shift+A starts the companion; Super+Return opens Kitty;
Super+Space opens Wofi; Super+L locks; Super+Ctrl+R stops the core/listener.
The template adds companion floating/pinning rules and disables the default
Hyprland logo. It does not constitute a complete themed Hyprland desktop.

AI tools now include `list_windows`, `focus_window(address)` and
`switch_workspace(workspace)` (integer 1–20). Window focus requires a currently
listed hexadecimal address. Fixed dispatch templates support legacy and Lua-era
Hyprland; arbitrary Lua, exec dispatches and model regexes are not accepted.
Window tools honor the protected `hyprland_enabled` preference and require an
actual Hyprland session. This preference was enabled as requested. GNOME window
control is not provided by these tools. Live Hyprland session behavior remains
pending; parser validation is not compositor/hardware validation.

## RE wake activation

New default detector: `re_whisper`, selectable in **Voice & listening → Wake
detector**. It uses the installed local Whisper model on overlapping two-second
audio windows, skips quiet windows, and accepts an isolated `RE`/`R E`/`ar ee`/`ary`,
optionally preceded by Hey/Hello/Hi. Say the name, pause until the companion shows
Listening, then speak the task. Recognition is English for the name; the command
continues to use the configured recognition language. Temporary wake audio is
deleted. No wake transcript is logged or sent online.

This is experimental speech-based wake detection, not a trained RE keyword model.
It consumes more CPU and may miss calls or falsely activate. Detection subprocesses
have a five-second timeout; this is not a latency guarantee. The alternative
openWakeWord backend still supports custom models. Its installed Jarvis model
does not detect RE. A dedicated RE model needs training and held-out evaluation:
[official openWakeWord project](https://github.com/dscripka/openWakeWord).

Both listening switches remain **off** on this machine. To opt in, save **Listen
for wake word** and **Require wake word**, optionally **Speak replies**, then restart
the listener from the hub. The companion exposes armed/listening activity.
Stop immediately using the hub's Stop button or `systemctl --user stop ai-os.service`.
Synthetic Piper “R E” → Whisper returned `RE.` and matched the detector. This is
not real-microphone, noise, false-activation, or long-running performance validation.

## Arch knowledge and authority

`find_commands(query)` searches the installed apropos index, falling back to
installed manual filenames if it has no match/index; `command_help(command)`
reads installed manuals. Both are bounded, shell-free operations. RE is instructed
to inspect those references and actual state before choosing arguments. Existing
official manual caching remains available. No claim of “all commands learned,”
model-weight training, or autonomous privilege escalation is made. Tool execution
still obeys command review and [access grants](COMMAND_ACCESS.md).

## System branding and authentication boundaries

The user approved these exact identity changes. Applying with `sudo -n` failed
because a password is required; `timeout 60s pkexec /usr/bin/python
/home/aryan/src/ai-os/scripts/apply_system_identity.py --apply` expired without
authentication (exit 124). Verified `/etc/os-release` still reports Arch. No
additional approval is needed for this same reviewed operation; authenticate
locally and never collect a password in chat.

`python scripts/apply_system_identity.py` previews a concrete installer. After
explicit approval, `sudo python scripts/apply_system_identity.py --apply` changes:

- `/etc/os-release`: REgenOS display name, `ID=arch` retained for compatibility.
- `/usr/share/icons/hicolor/scalable/apps/regenos.svg` and
  `/usr/share/pixmaps/regenos.svg`: original logo.
- `/etc/issue`: branded TTY banner.

It backs up files/symlink metadata in `/var/lib/regenos/branding-backups/identity-*`,
then atomically replaces each target. Arch's `/usr/lib/os-release` stays untouched.
For rollback, restore saved regular files, recreate recorded symlinks, and remove
only newly introduced targets identified by `manifest.json`. Review with root
access before restoring. The operation is not a multi-file atomic transaction.
See [os-release specification](https://www.freedesktop.org/software/systemd/man/latest/os-release.html).

Boot splash, GRUB/UKI branding and login-screen styling are separate pending work.
Read-only boot inspection identifies GRUB plus a systemd UKI; access to parts of
`/boot` was denied. No boot configuration or disk contents were changed.

User preference: face/voice should replace the normal password prompt after
enrollment. **Neither biometric unlock feature is implemented or enabled.** The
hub reports this accurately. The camera identifies as HP True Vision FHD; IR and
liveness capability have not been verified. Howdy is absent. Its upstream explicitly
warns against use as sole authentication: [Howdy security notes](https://github.com/boltgolt/howdy#A-note-on-security).
No camera capture, voice enrollment, PAM edit or password removal was performed.

Required next stage: review/install a maintained authentication backend; validate
camera/speaker verification and replay resistance; implement privileged enrollment,
disable/delete controls and protected hub toggles; retain a tested password recovery
route; verify rejection and lockout recovery in a disposable session before changing
GDM/hyprlock PAM. Voice wake detection is not speaker verification. The model and
same-user settings JSON must never be an authority that unlocks the computer.
