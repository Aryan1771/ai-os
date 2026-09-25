# Project Structure

```text
ai-os/
├── ai_os/
│   ├── ai_os_core.py
│   ├── avatar_overlay.py
│   ├── config.py
│   ├── hardware_monitor.py
│   ├── logging_utils.py
│   ├── native_settings.py          # Qt Widgets settings window
│   ├── native_widgets.py           # Native canvas, emotion bars, local IPC
│   ├── settings_store.py           # Config validation and persistence
│   ├── settings_server.py          # Legacy import/launch shim; no HTTP server
│   ├── companion_state.py          # Bounded activity and emotion snapshots
│   ├── pixel_engine.py             # Persistent-particle morphing
│   ├── speech_queue.py
│   ├── security/                 # CLI consent broker
│   ├── services/                 # API broker, listener, STT, wake-word, jobs, scanner
│   └── tools/                    # System, memory, and UI tools
├── archiso/
│   ├── packages.x86_64.add
│   └── calamares/                 # Installer integration plan, not a shippable installer
├── branding/
│   ├── regenos-mark.svg           # Scalable REgenOS mark
│   ├── regenos-mark.png
│   ├── regenos-companion-atlas.png # Nine concept poses; not the live renderer
│   ├── plymouth/                  # Linux boot splash theme
│   └── wallpapers/                # Desktop and lock-screen art (SVG masters)
├── config/
│   ├── ai-os/config.example.json
│   ├── desktop/                   # Native application menu entries
│   └── hypr/                      # Hyprland wallpaper, lock, and Super bindings
├── docs/                          # Arch setup, security, desktop, voice, and ISO guides
├── install/                       # Staged Arch installer script
├── scripts/                       # Package, runtime, security, and smoke-check scripts
├── security/                      # AppArmor profile
├── systemd/                       # User services for daemon and avatar
├── tests/
├── pyproject.toml
└── README.md
```

Runtime files are created on the Arch system, not committed to Git:

```text
~/.ai_os/
├── venv/
├── config.json
├── habit_engine.json
├── slang_vocab.json
├── logs/
├── run/
├── models/                        # Local voice models; keep out of Git
└── data/
```
