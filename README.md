# REgenOS

The default desktop pointer is the author's original **REgenOS Cool** cursor
pack. See [cursor installation and ISO defaults](docs/CURSOR_THEME.md).

Offline-first AI interface layer and Arch-based desktop product for a portable external NVMe install.

![REgenOS pixel-cycle mark](branding/regenos-mark.svg)

REgenOS Settings and the corner companion are native Python/Qt applications. The companion rearranges colored pixels in real time, with six simulated emotion bars, twelve built-in forms and validated model-generated pixel patterns. No browser or HTTP settings server is needed. A branded Archiso live image is documented; the graphical disk installer remains unfinished.

![Native REgenOS Settings](docs/images/native-settings.png)

This repository stores the source code, systemd templates, security templates, and Arch setup instructions. It does not store the Python virtual environment, Ollama models, ChromaDB state, downloaded voice models, or private API keys.

## Target Runtime

- OS: Arch Linux, Zen kernel, systemd, PipeWire
- GPU: NVIDIA RTX 4060 Laptop 8 GB VRAM
- Local LLM: Ollama with `qwen2.5:7b-instruct-q4_K_M`
- Python: 3.12+ in `~/.ai_os/venv`
- Runtime directory: `~/.ai_os`
- Source checkout: any folder, commonly `~/src/ai-os`

## Architecture

```text
ai_os_core.py
  loads config, builds tool registry, talks to Ollama, routes JSON tool calls

ai_os/tools/system_tools.py
  process management, hardware stats, wpctl volume, brightnessctl, safe command runner

ai_os/tools/memory_tools.py
  JSON-backed habits/slang plus optional ChromaDB memory

ai_os/tools/ui_tools.py
  phase-gated UI bridge; disabled until Hyprland/Wayland phase

ai_os/hardware_monitor.py
  udev and system snapshot diff monitor

ai_os/speech_queue.py
  sentence-aware speech/event queue for Piper or terminal fallback

ai_os/security/consent_broker.py
  human approval flow for risky commands

ai_os/services/
  local Whisper.cpp adapter, optional wake-word adapter, allowlisted external API broker,
  ClamAV scanner, and cooperative background job registry

ai_os/native_settings.py and ai_os/settings_store.py
  native Qt settings application and validated local preferences

ai_os/avatar_overlay.py, ai_os/pixel_engine.py, ai_os/companion_state.py
  native pixel companion, particle morphing and activity/emotion state
```

## Start Here

Start with the Arch installation and native desktop guides:

```bash
docs/INSTALL_ON_ARCH.md
docs/NATIVE_DESKTOP.md
docs/VOICE_AND_COMPANION.md
docs/PHASE_5_DESKTOP.md
docs/BRANDING_AND_ARCHISO.md
```

See [the detailed feature checklist](docs/FEATURE_STATUS.md) for implemented features, integration gaps and target-hardware verification still required.

`docs/ARCH_RUNBOOK.md` remains the detailed Phase 1 checklist. REgenOS is the product identity; the source repository and Python package retain their `ai-os` names for compatibility. REgenOS is an independent Arch-based project and does not replace or claim ownership of Arch Linux, the kernel, or third-party projects.
