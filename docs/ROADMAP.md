# Roadmap

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

- Add Whisper.cpp command integration.
- Add Piper speech output.
- Add openWakeWord.
- Add JSON habits, slang vocabulary, and ChromaDB memory.

## Phase 3: Security Sandbox

- Enable UFW baseline.
- Add AppArmor profile.
- Add ClamAV scanning.
- Add noexec temp/cache mounts only after confirming package workflows.

## Phase 4: Hardware Awareness and Async Jobs

- Add udev hardware monitor.
- Add GPU/RAM/display snapshot diffs.
- Add background job registry.
- Add sentence-aware speech queue event injection.

## Phase 5: Hyprland/Wayland UI

- Install Hyprland after the daemon is stable.
- Enable `hyprctl` IPC bridge.
- Enable `ydotool`/`wdotool` with explicit user consent.
- Build HUD, lock screen branding, wallpaper, and desktop shell polish.

## Phase 6: Packaging

- Move installation into scripts.
- Create Archiso profile.
- Add branding assets.
- Build and test ISO on multiple machines.

