# Portable Hardware Adaptation

REgenOS now has read-only discovery and conservative inference admission for
x86-64 Linux. This is not a universal driver installer or a guarantee that every
computer boots. ARM machines require a separate image and validation. An NPU
being present does not mean Ollama or the voice pipeline can use it.

## Implemented

- Scan CPU, RAM, PCI display/accelerator devices, bound GPU drivers, audio-card
  descriptions and DRM connector state at daemon startup and before inference.
- Save capability profiles under `~/.ai_os/hardware/` without serial numbers,
  hostnames, MAC addresses or machine-id. Identical hardware may share a profile.
- On Linux with local Ollama, inspect installed/loaded models, cap context and
  CPU threads, and reject requests that exceed a conservative estimated RAM budget.
- Defer GPU scheduling to Ollama when a relevant driver is bound; request CPU
  inference when it is absent or when explicitly selected. GPU detection is not
  proof of acceleration. The report distinguishes policy from prior observed use.
- Optional fallback to explicitly listed, already installed models. This is OFF
  by default and does not change the saved preferred model. No automatic downloads.
- One in-flight REgenOS model request per runtime home, across hub/CLI/voice.
- Native C++ Hardware page with protected adaptation settings, refresh/report,
  and confirmed per-computer CPU/automatic/default overrides.

Memory admission uses model file size plus estimated overhead, not exact tensor
allocation. It deliberately requires enough system RAM even when a GPU is
present. It is not a hard VRAM limiter, does not reserve memory, and cannot limit
other Ollama clients or concurrent transcription. A failed GPU request is reported,
not silently replayed. CPU-only mode may be much slower.

## Update Your Existing Arch Installation

Run as your normal user, adjusting only the checkout path if necessary. Do not
delete `~/.ai_os`, Ollama storage, or existing models. Review local edits before
pulling; `--ff-only` stops rather than overwriting divergent work.

```bash
cd ~/src/ai-os
git status --short
git pull --ff-only
source ~/.ai_os/venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ai_os.hardware_profile --refresh
```

The refresh command writes a report and exits successfully even when its
`policy.ready` is false: inspect the reason. Model requests fail closed when
adaptation is enabled but inventory/planning cannot succeed. On Windows the
report explicitly states that automatic adaptation targets Linux; Windows tests
use simulated hardware and do not certify Linux behavior.

Rebuild the existing native hub (this explicitly installs build dependencies):

```bash
bash scripts/install_cpp_hub.sh
~/.ai_os/venv/bin/regenos-settings
```

Open Hardware, refresh, and inspect the report. Save settings before testing.
Fallback names are one per line. Enable fallback only if you accept using those
models. CPU/automatic overrides affect this capability profile; Follow defaults
clears its entire override. Advanced `context_tokens` and `threads` overrides
can be stored with the validated Python API; the panel does not expose those
per-machine numeric overrides yet. The AI tool registry cannot invoke this API.
Same-user file access is not an independent security boundary.

```bash
systemctl --user restart ai-os.service
journalctl --user -u ai-os.service -n 80 --no-pager
ollama list
ollama ps
cat ~/.ai_os/hardware/current.json
```

If the user service is not installed, run `python -m ai_os.ai_os_core` instead.
Keep the existing preferred model; a smaller model download is optional and
requires network access and your explicit choice, for example:

```bash
ollama pull qwen2.5:3b-instruct-q4_K_M
```

## Prepare The SSD For Different PCs

Runtime adaptation starts AFTER Linux boots. First back up the external SSD and
confirm disk identities. These commands only inspect:

```bash
uname -m
findmnt /
findmnt /boot
lsblk -o NAME,PATH,MODEL,SIZE,FSTYPE,UUID,MOUNTPOINTS
lspci -nnk
pacman -Q linux linux-zen linux-lts linux-firmware mesa ollama
cat /etc/fstab
cat /etc/mkinitcpio.conf
ls /etc/mkinitcpio.d
```

Missing optional packages in `pacman -Q` are not a reason to reinstall everything.
Never target the internal Windows disk. Use filesystem UUIDs for the external
root/EFI mounts. Confirm the bootloader and EFI partition actually reside on
that SSD; a boot entry on one laptop alone does not establish portability.

For a broad x86-64 firmware/Mesa base, review and then explicitly run on Arch:

```bash
sudo pacman -Syu --needed linux-firmware sof-firmware mesa vulkan-intel vulkan-radeon intel-ucode amd-ucode pciutils usbutils
```

The base installer and Archiso additions no longer assume NVIDIA on every
machine. This does not remove your existing NVIDIA driver. Keep the working
driver for your RTX 4060; driver selection depends on GPU generation and kernel.
Do not blindly swap proprietary/open/legacy NVIDIA modules or install conflicting
driver variants. No GPU module is unloaded or blacklisted by adaptation.

Ollama needs the appropriate runtime backend as well as a working kernel driver.
Review current package metadata and conflicts before selecting additional backends:

```bash
pacman -Si ollama ollama-cuda ollama-rocm ollama-vulkan
systemctl cat ollama
journalctl -u ollama -n 80 --no-pager
```

For example, after confirming your GPU supports Vulkan and the package transaction
is appropriate, `sudo pacman -Syu --needed ollama-vulkan` adds that backend.
Restart Ollama explicitly after backend changes: `sudo systemctl restart ollama`.
REgenOS does not change the already-running server's GPU environment or grant it
extra capabilities. NVIDIA CUDA and supported AMD ROCm are other backend choices;
an NPU-specific inference adapter remains future work. Consult
[Ollama hardware support](https://docs.ollama.com/gpu) and
[Arch's Vulkan backend package](https://archlinux.org/packages/extra/x86_64/ollama-vulkan/).

## Boot And Recovery Review

Ask the Arch CLI to review these items against the inspected installation before
making privileged changes:

1. A fallback initramfs that does not filter drivers to the build machine via
   `autodetect`, including the storage/filesystem/encryption hooks your SSD needs.
2. A tested fallback entry for the actual bootloader and kernel, optionally an LTS
   kernel. Do not overwrite your sole working entry.
3. Removable-media UEFI boot support on the SSD's own EFI partition. Secure Boot,
   legacy BIOS and different CPU architectures require separate support decisions.
4. No machine-specific mandatory GPU/Xorg/compositor configuration that prevents
   a different GPU from starting a session; retain a reachable TTY recovery path.
5. Review the updated AppArmor template against local rules, then validate reads
   and denial logs. Do not disable enforcement merely to make a test pass.

The [mkinitcpio manual](https://man.archlinux.org/man/mkinitcpio.8) documents hook
selection and fallback generation. There is deliberately no blind bootloader,
partitioning, initramfs overwrite or driver-replacement command here: it depends
on the inspected disk layout. Hardware adaptation does not make an ISO installer
complete; follow the existing ISO guide and disposable-VM validation separately.

## Acceptance Checklist On Each Machine

- [ ] Cold boot using the external SSD, with internal disks left untouched.
- [ ] Refresh reports correct CPU/RAM/GPU driver and an honest accelerator status.
- [ ] Ask a question; compare report with `ollama ps` while the model is resident.
- [ ] Select CPU for this machine, request again, verify actual CPU execution.
- [ ] Test an unavailable/oversized preferred model: clear refusal, no download.
- [ ] Opt into an installed smaller fallback; verify saved preference is unchanged.
- [ ] Verify microphone, speakers, brightness, display scaling and input devices.
- [ ] Suspend/resume and repeat inference/audio tests; inspect service error logs.
- [ ] Move to another supported PC; confirm new profile and retained conversations.
- [ ] Confirm AppArmor enforcement and no unintended system writes.

Only after these tests should a hardware configuration be called verified.
