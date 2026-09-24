# REGENOS

Offline-first AI interface layer and Arch-based desktop product for a portable external NVMe install.

![REGENOS pixel-cycle mark](branding/regenos-mark.svg)

The companion concept is a retro pixel character with expressive poses; its live overlay uses spring-driven pixel particles and currently morphs among a core, heart, music, code, idea, and cloud. The settings panel and desktop bindings are included. A branded Archiso live image is documented; a graphical disk installer is not yet packaged or safe to ship.

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

ai_os/settings_server.py and ai_os/web/
  loopback-only settings application for AI, voice, companion, appearance, desktop, and sandbox controls

ai_os/avatar_overlay.py
  pixel-particle companion with spring morphs and topic/emotion forms
```

## Start Here

Read and execute in this order:

```bash
docs/INSTALL_ON_ARCH.md
docs/PHASE_5_DESKTOP.md
docs/BRANDING_AND_ARCHISO.md
docs/VOICE_AND_COMPANION.md
```

`docs/ARCH_RUNBOOK.md` remains the detailed Phase 1 checklist. REGENOS is the product identity; the source repository and Python package retain their `ai-os` names for compatibility. REGENOS is an independent Arch-based project and does not replace or claim ownership of Arch Linux, the kernel, or third-party projects.
