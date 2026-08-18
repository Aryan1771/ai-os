# AI-OS Interface Layer

Offline-first AI control layer for an Arch Linux portable external NVMe install.

This repository stores the source code, systemd templates, security templates, and Arch setup instructions. It does not store the Python virtual environment, Ollama models, ChromaDB state, downloaded voice models, or private API keys.

## Target Runtime

- OS: Arch Linux, Zen kernel, systemd, PipeWire
- GPU: NVIDIA RTX 4060 Laptop 8 GB VRAM
- Local LLM: Ollama with `qwen2.5:7b-instruct-q4_K_M`
- Python: 3.12+ in `~/.ai_os/venv`
- Runtime directory: `~/.ai_os`
- Source checkout: any folder, commonly `~/src/ai-os-interface-layer`

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
```

## Start Here

Read and execute:

```bash
docs/ARCH_RUNBOOK.md
```

The repo is intentionally usable before Hyprland. Phase 1 runs in TTY or minimal X11 and focuses on the daemon, tool safety, Ollama, memory, and voice pipeline.

