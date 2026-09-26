# Remaining Work: Windows vs Arch

An unchecked feature is not necessarily blocked by Windows. Source-level work
can often be implemented here, while correctness on the real OS needs Arch.
The C++ hub, persistent conversation history, context notebook, Piper WAV
playback and argument-level command restrictions were implemented in the
2026-09-26 update. Not every unchecked feature is finished by this update.

## Software Work Still Possible Here

| Remaining area | Next implementation and required proof |
| --- | --- |
| Agent planning | Bounded tool-result loop, structured tool schemas, retries, durable task recovery and failure tests; risky execution still requires a trusted consent design. |
| Approvals | Native request display can be written here; separate service identities, authenticated IPC and privilege enforcement must be validated on Linux. |
| Memory | Semantic retrieval, summaries, sensitive-data handling and conflict resolution; explicit offline embedding provisioning before semantic tests. |
| Companion | Screen selection, persistent dragging, avatar packs and pixel editor; real compositor positioning needs Arch. |
| Provider protocols | Additional vendor adapters with protocol-specific tests; current support is Ollama and OpenAI-compatible chat. |
| Voice assets | Hash-verified download/provisioning manager, resume/retry and license metadata; actual models/audio must be tested locally. |
| Scheduling | Durable job scheduling and hardware-event routing, with rate limiting and consent. |
| Packaging sources | Package recipes, Calamares configuration, branding and release scripts; building files is not validation of an installer. |

## Work To Validate On Arch With Codex CLI

| Area | Why the target matters |
| --- | --- |
| Speed and VRAM | Measure cold/warm Ollama, CPU/GPU offload, context pressure, transcription and playback latency on the RTX 4060; add admission control using real measurements. |
| Audio | Device selection/hotplug, noise suppression, VAD, acoustic echo cancellation, interruption and streaming need real PipeWire routes, microphone and speakers. |
| Cursor and display | Run real conversion tests; test hotspots/animation in GTK/Qt; verify X11/XWayland positioning. Pure Wayland layer-shell needs protocol integration and compositor tests. |
| Isolation | Dedicated service identity, AppArmor enforcement, seccomp, secrets, domain egress, noexec mounts and adversarial testing require Linux facilities. |
| Media scanning | Connect ClamAV to actual removable-media/udev flows with safe mount and failure handling. |
| UI automation | Window manipulation, accessibility, screenshots and vision need the actual display/input stack and visible permission controls. |
| OS themes | Desktop, GTK, Qt, display-manager and bootloader settings vary by chosen desktop/session; keep explicit scope and backups. |
| Portability | NVIDIA/audio/display drivers, suspend/resume, external-SSD boot and other-machine behavior require spare hardware testing. |
| ISO/installer | Build and boot Archiso; install with Calamares in disposable VMs; test partitioning, encryption, UEFI failure recovery, updates and rollback. Never use the Windows disk as a test target. |

## Not Universal Completion Promises

Perfect artwork for every possible topic, replacement of every desktop's
settings application, and guaranteed production readiness are not bounded
features. The current fluid-looking pixel motion is not a physical liquid
simulation. Firmware-logo replacement is vendor-specific firmware work, not
Plymouth branding, and should not be attempted as a routine distribution step.
Fine-tuning is a separate dataset/license/training project, not a prerequisite
for local memory or something that fits automatically in an 8 GB VRAM budget.

## Prompt For The Arch CLI

```text
Continue REgenOS from docs/FEATURE_STATUS.md, docs/CPP_HUB.md and
docs/IMPLEMENTATION_HANDOFF.md. Audit the installed state before modifying it.
Do not reinstall Ollama/models or delete ~/.ai_os. The settings hub is C++17/
Qt6 Widgets; Python remains the validated backend and companion renderer.
Use the existing venv. Default new UI configurations to ordinary Graphite dark.
First run tests and verify the hub, two-turn/restart conversation recall,
context-note retrieval and Piper/wake-word paths. Measure each source of slow
response with real GPU/audio metrics. Then work through remaining software
features in dependency order, checking items only when implementation and
appropriate tests exist. Distinguish code-complete from hardware-verified.
Keep confirmations fail-closed; request approval before privilege, firewall,
mount, boot or disk changes. Never touch the internal Windows disk. Build and
test installer work only in disposable VMs or explicitly selected spare disks.
Update docs, commit and push reviewed source changes without private data.
```
