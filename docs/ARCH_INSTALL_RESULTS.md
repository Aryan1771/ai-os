# Current runtime inspection — 2026-10-16

Scope: read-only inventory and source repairs, not a reinstall or ISO build.
Baseline branch `main`, commit `82de882`; existing interrupted edits and unrelated
untracked `:memory:.ses` were preserved. Cached `origin/main` is also `82de882`.
`git ls-remote --heads origin` failed with DNS resolution unavailable; the actual
remote head and any Windows-only changes cannot be confirmed from that cache.
No pull, reset, model download, package installation or host service change ran.

| Component | Observed evidence | Limit |
| --- | --- | --- |
| Python | Existing venv and system Python report 3.14.7; imports resolve to the editable checkout | No clean reinstall needed/performed |
| Native Qt | Existing venv PySide6 Essentials 6.11.2 | Offscreen source tests do not prove desktop behavior |
| Kernel | `7.2.8-arch1-2`; standard and Zen packages installed | Running Zen not established |
| NVIDIA | nvidia-open-dkms/nvidia-utils 615.71.09 installed | GPU device/driver access unavailable inside this sandbox; no new peak measurement |
| Ollama | ollama and ollama-cuda 0.35.1-1 installed | Loopback tags/ps requests raise ConnectionError here; no inventory/inference acceptance |
| Audio | pw-record, pw-play, whisper-cli and Piper found; selected Whisper/Piper files and Piper sidecar exist | No microphone capture, mute/device or audible verification |
| Desktop | Environment advertises GNOME Wayland/XWayland; Hyprland package exists | No compositor control/session-bus proof from this sandbox |
| Accessibility | Distro Python imports Atspi 2.0 with required text/timeout APIs | No private desktop text was read in validation |
| Containment | Bubblewrap 0.13.0 exists; harmless namespace diagnostic confirms private devices/bus paths, read-only root and no_new_privs | Not a complete adversarial sandbox audit |
| Storage | Sandbox-visible USB SSD root/EFI; about 182 GiB free; internal NVMe NTFS partitions have no visible mountpoints | Sandbox mount flags are not the host's mount policy; no mount/disk changes performed |

Commands used included `git status --short --branch`, `git branch -vv`,
`git remote -v`, `git log`, `uname`, `pacman -Q`, `df -h`, `findmnt`, `lsblk`,
venv version/import checks and the read-only `python -m ai_os.runtime_health`.
Private model stores, memory content and raw journals were not printed.

The saved switches reported listening enabled without either a wake word or an
alternative activation choice; screen context was disabled. The new readiness
report names this `needs_activation_choice`. New context/activity options remain
off. Existing values/assets were not rewritten. See [harness controls](INTERACTION_HARNESS.md).

Rollback: review the checkpoint diff/commit, then revert only that source checkpoint
if needed. No runtime data migration was performed. Do not reset unrelated changes,
delete private runtime data or blindly restore old backups. Service changes require
separate approval; the new supervisor takes effect after an approved restart.
