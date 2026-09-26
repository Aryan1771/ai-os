# Roadmap

See [Feature Status](FEATURE_STATUS.md) for the detailed checklist, [C++ Hub](CPP_HUB.md) for settings/conversation/memory, and [Native Desktop](NATIVE_DESKTOP.md) for the live pixel companion. [Implementation handoff](IMPLEMENTATION_HANDOFF.md) separates remaining software work from Arch validation. The browser frontend has been removed.

## Phase 0: Portable Arch Base

- Boot external NVMe Arch install.
- Install Zen kernel headers, NVIDIA DKMS, CUDA, PipeWire, Python, Git.
- Verify `nvidia-smi`, `nvcc`, audio, brightness controls, and networking.

## Phase 1: Core Daemon Without Hyprland

- Build safe system tools.
- Build consent broker.
- Build Ollama tool-calling harness.
- Run daemon from TTY or terminal.
- Confirm VRAM stays below the 8 GB ceiling.

## Phase 2: Voice and Memory

- Source: Whisper.cpp adapter, Piper PipeWire playback path, lazy openWakeWord adapter, and optional ChromaDB helpers are present.
- Arch validation: install local models, verify microphone capture, confirm Piper audio, then explicitly enable wake word.

## Phase 3: Security Sandbox

- Source: UFW/AppArmor baseline, ClamAV adapter, and HTTPS allowlisted external API broker are present.
- Arch validation: apply the baseline only from a local console, load the profile, and verify recovery access.

## Phase 4: Hardware Awareness and Async Jobs

- Source: polling and optional udev monitor, cooperative job registry, and sentence-aware speech queue are present.
- Arch validation: monitor real attach/remove events and ensure long-running workers observe cancellation and pause events.

## Phase 5: Hyprland/Wayland UI

- Source: phase-gated `hyprctl` window listing, consent-gated typing, Hyprpaper/Hyprlock templates, and branding paths are present.
- Arch validation: install and test Hyprland separately, then explicitly set `hyprland_enabled` to `true`.

## Phase 6: Packaging

- Source: staged installer, branding asset boundary, Archiso package additions, and build guide are present.
- Arch validation: copy Archiso's `releng` profile, build an ISO, test it in a VM, then test it on spare removable media.
