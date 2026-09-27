# Installed dependency audit — 2026-09-27

**Update after user installation:** all immediate and optional desktop packages
listed below are now installed, as is win2xcur 0.1.2. Whisper base, both Piper
voices/configs and Jarvis ONNX are present. The remaining TFLite dependency warning
does not prevent the explicitly selected ONNX wake model from loading. These
sections retain the earlier installation commands for reference. Current voice
test results and limitations are in [HANDOFF](HANDOFF.md).

Verified against this host's pacman inventory, venv module discovery, `pip check`,
configured model-file existence and repository installers. These are scoped
preinstallation commands, not a requirement to run every installation stage.
No package or service changes were made by this audit.

## Missing packages useful next

```bash
sudo pacman -S --needed whisper-cpp noto-fonts
```

- `whisper-cpp` supplies `whisper-cli` for transcription. Installing it does not
  download the configured speech model or enable listening. Confirmed by the
  [official Arch file list](https://archlinux.org/packages/extra/x86_64/whisper-cpp/files/).
- `noto-fonts` supplies the font family used by the native/desktop defaults;
  other fonts currently allow the native UI to work.

Use these against an up-to-date Arch installation; do not refresh package
databases with `pacman -Sy` alone. If an upgrade is needed, review a full
`sudo pacman -Syu` separately, including any kernel/driver changes.

## Optional desktop packages missing from repository defaults

```bash
sudo pacman -S --needed hyprlock hyprpaper hypridle wofi thunar \
  papirus-icon-theme ttf-jetbrains-mono
```

These support lock, wallpaper, idle, launcher, file-manager and appearance
templates. They are not prerequisites for the working GNOME/XWayland native
Settings/Companion. Hyprland, Waybar, Kitty, XWayland, its desktop portal and
ydotool are already installed. Session configuration and acceptance remain
separate; package installation alone does not activate the templates.

Plymouth and Archiso are also absent but deferred with boot/ISO work. CMake and
Ninja are absent and only needed if deliberately building native dependencies;
they are not required for the supported Python UI. Do not install Calamares yet:
the repository still lacks a complete tested installer configuration.

## Missing items that sudo packages do not solve

- Configured Whisper model and English/Hindi Piper voices are absent. Voice
  assets remain deferred; later choose multilingual Whisper for Hindi and verify
  model provenance/checksums. Piper needs its voice metadata as well as ONNX.
- `openwakeword`, Piper, ONNX Runtime, PySide6, ChromaDB, OpenCV, pyudev, pytest
  and Ruff modules are present in the project venv; module presence is not full
  functional validation. `~/.ai_os/venv/bin/piper` exists.
- `~/.ai_os/venv/bin/python -m pip check` fails because openWakeWord 0.6.0 declares
  missing `tflite-runtime`. ONNX Runtime exists; explicit ONNX model support is
  implemented, but assets and readiness require validation. Do not use sudo pip
  or assume a compatible TFLite wheel exists for the current Python 3.14 venv.
- `win2xcur` is absent, explaining the skipped real cursor-conversion test.
  The repository pins `win2xcur==0.1.2` for installation in the venv, without sudo.
  ImageMagick and Adwaita cursors are already installed.

## Already installed

Ollama/CUDA backend, CUDA, NVIDIA open DKMS/userspace, standard and Zen kernels
with headers, Intel microcode, firmware, PipeWire/WirePlumber, ALSA utilities,
FFmpeg, brightnessctl, lm_sensors, PCI/USB tools, Qt XCB dependencies, fontconfig,
desktop-file-utils, Git and Python tooling. UFW, firewalld, AppArmor, audit and
ClamAV packages also exist; this is not evidence that policies/signatures are
configured or validated. Do not rerun the base/security installers as a package
shortcut: they also enable services or change policy.

Remaining engineering includes tokenizer-aware context limits, request ordering,
result-grounded tool loops, voice cancellation/stall recovery and end-to-end
bilingual acceptance, trusted native approvals, confinement audit, compositor
acceptance, and reproducible VM-tested installer work. These cannot be fixed by
preinstalling packages. See [the detailed audit](IMPLEMENTATION_CHECKLIST.md).
