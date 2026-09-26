# REgenOS: Arch Installation To Release ISO

Use this guide after booting the existing Arch installation on the external SSD.
It is a staged handoff, not a claim that every planned feature or installer exists.
Baseline: source commit `daed4a0`, 84 Windows Python tests passed, one cursor test
skipped, C++ build and repeated bridge tests passed. Inspect newer commits too.
Those results do not certify Arch hardware, security enforcement or installation.

## 1. Choose The Assistant

Use **Codex CLI in the Arch terminal** for repository edits and local commands.
Ordinary ChatGPT in a browser can discuss logs and provide instructions, but do
not assume that it can execute commands on your Arch installation. Treat a new
CLI session as needing the context below; do not rely on this Windows conversation
being automatically available merely because you sign in with the same account.

Codex setup/sign-in normally needs internet. REgenOS's local Ollama assistant is
a separate program and should work offline after its dependencies are provisioned.
Do not apply restrictive firewall changes before preserving an approved development
connection and a local recovery path. Never disable the firewall wholesale to fix
connectivity. Never run Codex as root or bypass its approval controls.

If Codex already works, skip installation. Otherwise, follow the
[official CLI instructions](https://learn.chatgpt.com/docs/codex/cli).
The documented Linux installer can be downloaded for inspection before execution:

```bash
command -v codex
mkdir -p ~/.local/share/regenos-setup
curl -fL https://chatgpt.com/codex/install.sh -o ~/.local/share/regenos-setup/codex-install.sh
less ~/.local/share/regenos-setup/codex-install.sh
```

After reviewing the downloaded script, run it without sudo and follow its PATH
instructions. Reopen the terminal if necessary:

```bash
sh ~/.local/share/regenos-setup/codex-install.sh
codex --version
```

If `curl` or Git is missing, install only the missing prerequisite through pacman
with a full system upgrade after reviewing the transaction. Do not reinstall Arch.

## 2. Bring The Source Across

Keep the existing Ollama models, `~/.ai_os`, conversations, voice models, venv and
working configuration. A fresh source checkout does not require a model download.

If the repository is already at `~/src/ai-os`:

```bash
cd ~/src/ai-os
git status --short
git remote -v
git pull --ff-only
git log -3 --oneline
```

Stop on local-change or divergence errors; ask the assistant to preserve and
reconcile them. Do not reset or delete the old checkout. If no checkout exists:

```bash
mkdir -p ~/src
git clone https://github.com/Aryan1771/ai-os.git ~/src/ai-os
cd ~/src/ai-os
```

Start the CLI in the repository, sign in when prompted, and paste Prompt A:

```bash
codex
```

Run the prompts in order, not all at once. Blank extra-feature lines mean no extra
request; fill only the ones you want. After each stage, keep its report and Git
checkpoint. For a new conversation, paste Prompt A again followed by the current
stage and ask it to read the reports. Preserve local reports, not just chat history.

## Prompt A: Context And Read-Only Audit

```text
You are continuing my existing REgenOS project on the actual Arch Linux host.
Repository: https://github.com/Aryan1771/ai-os.git, normally ~/src/ai-os.
Read AGENTS.md if present, README.md, docs/FEATURE_STATUS.md,
docs/IMPLEMENTATION_HANDOFF.md, docs/CPP_HUB.md, docs/HARDWARE_PORTABILITY.md,
docs/INSTALL_ON_ARCH.md, docs/VOICE_AND_COMPANION.md,
docs/BRANDING_AND_ARCHISO.md and this ARCH_HANDOFF.md. Inspect code and current
Git history; documentation and checkmarks are not proof of installed behavior.

Identity: REgenOS, with lowercase gen deliberately. Offline-first Arch-based
desktop on a portable external SSD. Initial machine: i7-14650HX, 16 GB RAM,
RTX 4060 Laptop with 8 GB VRAM, Zen kernel, PipeWire. Ollama and the preferred
qwen2.5:7b-instruct-q4_K_M model may already be installed. Detect actual hardware.
The native hub is C++17/Qt6 Widgets with ordinary Graphite dark styling, not a
browser. The native pixel companion is Python/Qt with rearranging particles,
topic forms and simulated emotion bars. Voice uses Whisper.cpp, Piper and
openWakeWord. Memory includes local SQLite conversations/curated context notes;
Chroma helpers exist but full semantic recall and fine-tuning are not complete.
The author-created Cool_cursor pack is the intended distribution default.

Hardware profiles/admission/CPU overrides exist; generic NPU inference does not.
The installer/ISO integration and many checklist items remain incomplete.
First prove the core in TTY/existing minimal desktop. Integrate Hyprland only
after that checkpoint, with my approval. Preserve existing working desktop files.

Never format, repartition, mount writable, or install a bootloader to the internal
Windows disk. Do not delete ~/.ai_os, ~/.ollama, /var/lib/ollama, other discovered
model stores, local edits or existing models. Do not print secrets or private
conversation contents. Use the existing Python venv; no global pip or sudo pip.
Ask before system package/service, driver, firewall, mount, initramfs or boot changes.
Approval for this audit is not approval for later disk/privileged actions.

Start with read-only inventory: Git state, root/EFI mount identities, disks,
architecture/kernel, RAM/GPU drivers, Ollama installation/model store/service,
Python/venv health, audio routes, display/session, existing AI services and models.
Inspect setup scripts before suggesting execution. Older instructions that pull
models or recreate the venv should not be repeated if the installed assets work.
Report missing pieces and risks, then propose a minimal upgrade plan. Stop for
my approval before installation. Create a sanitized local audit report if useful;
do not commit machine identifiers or private paths/data without review.

Extra requirements (blank means none):
- ______________________________
- ______________________________
- ______________________________
```

## Prompt B: Install Or Upgrade The Runtime

Send after reviewing Prompt A's proposed changes. Approve concrete privileged
transactions individually; do not treat the text below as blanket sudo consent.

```text
Proceed with the reviewed REgenOS runtime upgrade, preserving working components.
Back up configuration and private memory consistently outside Git before edits;
stop relevant writers for SQLite backup or use its backup API. Record rollback
steps. Reuse Ollama and its existing models. Verify the venv interpreter and ABI;
if Arch's Python changed, repair only the venv with a recoverable replacement.

Install only necessary dependencies in the appropriate layer. Review the base,
runtime, voice, native and security scripts rather than running the all stage.
Build the C++ hub on Arch, not a copied Windows binary. Install the companion and
original cursor theme. Preserve current configuration values and desktop files.
Provision missing Whisper, Piper (including required sidecar configuration),
wake-word and optional embedding assets only after checking licenses, checksums,
versions and my download approval. Record all runtime assets required offline.

Validate service paths, user/environment, PipeWire session access, Ollama endpoint,
AppArmor profile availability and secrets handling before enabling the user daemon.
Avoid duplicate hub/CLI/daemon microphone listeners. Keep always-listening off until
the explicit microphone/wake test stage. Do not install Hyprland yet.

Run Python tests, native C++ tests and manual hub/backend smoke checks. Separate
new regressions from pre-existing lint failures; do not hide failures or uncheck
tests to obtain a pass. Produce docs/ARCH_INSTALL_RESULTS.md with sanitized results,
exact versions/commands, remaining blockers and rollback instructions. Commit and
push reviewed source/documentation changes only; exclude backups/models/private data.
Stop at a working core-runtime checkpoint or a clearly explained blocker.

Extra install requirements:
- ______________________________
- ______________________________
```

## Prompt C: Test And Measure On Real Hardware

```text
Validate the installed REgenOS, not just unit tests. Read the previous audit and
installation report. Build a reproducible acceptance matrix with expected result,
actual result, evidence and pass/fail/not-tested. Ask me to perform physical tests.

Cover: text and registered tool replies; denied risky commands; native settings
round-trip and protected-change confirmation; two-turn conversation recall across
process restart; context note retrieval/deletion; memory opt-out and retention;
Piper audible output; Whisper recognition; wake-word gating; false activations;
microphone privacy and explicit disable; no self-trigger while speaking; listener
restart and recovery; companion placement/morphing/emotion bars; cursor hotspots.
Enable always-listening only after my explicit consent. It must listen locally
for the wake word, show its state, and provide an accessible stop/mute control.

Measure cold/warm response latency, model load, STT, inference and TTS separately.
Use nvidia-smi and ollama ps where applicable. Keep space within this machine's
8 GB VRAM; profile combined workloads, not only the LLM. Do not assume admission
estimates enforce exact VRAM limits. Diagnose slow CPU fallback before changing
models; ask before reducing quality or downloading anything.

Test automatic hardware policy, installed-only fallback opt-in, CPU override,
unavailable/oversized model failures and concurrent request denial. Verify audio,
display, suspend/resume and another machine when available. Mark absent hardware
untested; do not claim NPU inference or universal compatibility.

Validate AppArmor/systemd enforcement, consent denial, secret permissions and
offline behavior. Existing firewall rules are not domain-only egress; document
and address that gap with an approved design. Do not cut off this development
session. Use explicit, reversible offline tests and reconnect afterward.

Fix verified defects with regression tests. Record sanitized metrics and evidence
in docs/ARCH_ACCEPTANCE.md; keep raw private logs outside Git. Update FEATURE_STATUS
truthfully, commit and push reviewed changes. Stop before branding/ISO work if
critical runtime or security checks fail.

Additional tests or performance targets:
- ______________________________
- ______________________________
- ______________________________
```

Useful manual checks, once the venv/runtime have been verified:

```bash
cd ~/src/ai-os
source ~/.ai_os/venv/bin/activate
python -m pytest -q
python -m ai_os.hardware_profile --refresh
ollama list
ollama ps
systemctl --user status ai-os.service --no-pager
journalctl --user -u ai-os.service -n 80 --no-pager
wpctl status
~/.ai_os/venv/bin/regenos-settings
```

Run the hub in an existing graphical session. Service checks can fail normally
before the service is installed. Do not post raw private logs publicly.

## Prompt D: Finish The Agreed Feature Scope

```text
Read FEATURE_STATUS and the Arch acceptance report. Classify every unchecked item:
implementable now, requires my physical verification, research/prototype, or deferred.
Create a release-scope checklist with dependencies and acceptance tests. Ask me to
approve the scope, including any extras below, before implementation. Blank extras
are not tasks. Do not mark all features complete just because files exist.

Then implement approved work in tested modules, preserving the C++ native settings
hub and native companion. Connect new settings end-to-end with validation, clear
states, ordinary dark default and user consent. Prioritize safe approvals, reliable
voice/memory, recovery and settings integration before optional visual polish.
Do not present stored memory as model training or simulated avatar bars as sentience.
Do not promise physically perfect liquid motion or unlimited arbitrary forms.

Separate independent security enforcement from same-user dialogs. Keep privileged
operations out of unchecked model output. Record source changes, repeat acceptance
tests, update feature status and commit/push reviewed work at stable checkpoints.
Do not begin an installable ISO until agreed release-blocking features pass or I
explicitly reduce scope to a labeled preview release.

Extra features I want (fill in before sending):
- ______________________________
- ______________________________
- ______________________________
- ______________________________
- ______________________________
```

## Prompt E: Desktop And REgenOS Product Identity

```text
The core has passed its agreed acceptance checks. Plan and apply REgenOS desktop
integration and branding, asking before system/boot changes. Confirm my chosen
desktop/session first; Hyprland was deferred during core development, not mandatory
for the daemon. Back up and merge existing config rather than overwriting it.

Use the supplied REgenOS logo, default/lock wallpapers, original Cool cursor pack,
native pixel companion, C++ hub and Super-key bindings. Keep exact REgenOS casing.
Make companion visibility, voice, wake-word, model, memory, appearance and safety
settings discoverable. Use normal dark styling, not high contrast. Verify Qt/GTK,
display scaling, multiple monitors, login/lock screens, icons/fonts and key conflicts.
Pure Wayland overlay positioning may require additional compositor integration;
test it and do not call an XWayland workaround native layer-shell support.

Implement Linux Plymouth branding and the selected bootloader/login appearance
only after inspecting the actual boot stack. Preserve recovery entries. Do not
modify vendor firmware logos. Use a package-managed distribution identity with
ID_LIKE=arch and upstream licensing/attribution; avoid fragile ad hoc overwrites of
Arch-owned files. Do not claim this creates a new kernel or an independent codebase.

Capture approved generic defaults as repository packages/config/templates so a
clean install reproduces them. Do not copy my private home directory into defaults.
Document every applied customization and rollback in docs/REGENOS_CUSTOMIZATION.md.
Run desktop and boot acceptance checks, update docs, commit and push reviewed files.

Extra branding/desktop preferences:
- ______________________________
- ______________________________
- ______________________________
- ______________________________
```

## Prompt F: Build A Clean Live ISO And Graphical Installer

This is new engineering work. The current repository only provides Archiso starting
materials and a Calamares plan. An ISO is not a conversion of your SSD into a file,
and a bootable live image is not automatically an installable distribution.

```text
Read the approved release scope, ARCH_ACCEPTANCE, customization report, Archiso
sources and archiso/calamares/README.md. Verify current upstream Archiso and
Calamares documentation before implementation. Build a clean distributable REgenOS
image from tracked source/package inputs, NOT a clone of my running installation.

First propose the release architecture and wait for approval: supported x86-64
hardware/UEFI scope, kernel and recovery strategy, desktop/live user, signed package
source, installer target strategy, offline asset bundle, update/rollback policy,
disk space/RAM needed and preview-versus-release blockers. Do not promise every
GPU, NPU, BIOS/Secure Boot configuration or bit-identical builds without testing.

After approval implement Arch package recipes for the Python runtime, C++ hub,
companion/assets, branding/defaults, services and dependencies. Production paths
must not depend on ~/src/ai-os or my username/venv. Preserve isolation from system
Python; provide a supported package/private-runtime strategy and upgrade tests.
Build custom packages in a clean environment with signature verification. Capture
package versions/source revisions/checksums and the complete build manifest.

Create a complete maintained Archiso profile and repeatable build script under the
repository. Include working AI/desktop integration, generic per-user defaults,
first-boot hardware adaptation and recovery tools. Never automatically download
models or replace GPU drivers at startup. Offer an approved broad firmware/backend
bundle while documenting unsupported hardware.

For an offline-full image, include only explicitly approved redistributable model
and voice/wake/embedding assets, with license notices, required sidecars, checksums
and an inventory. Provision from clean verified sources, never blindly copy my
Ollama store. Establish appropriate ownership and installed-target asset paths.
If licensing prevents bundling, explain the exception and provide an explicit
first-run provisioning path; do not label that configuration fully offline-ready.

Implement a branded Calamares graphical installer: language, timezone, keyboard,
target disk selection, partitioning, users, summary, installation progress and
completion. Validate its source package, module sequence, live-versus-target
packages, bootloader, users/permissions, locale, network, assets and service setup.
Ask me to approve supported encryption/manual/erase-disk scope. Clearly label any
unimplemented paths instead of displaying controls that pretend to work.

No personal accounts, credentials, chat/memory databases, Wi-Fi secrets, browser
profiles, SSH keys, machine IDs, per-machine overrides or private recordings may
enter the image. Installed machines must generate unique identities and host keys;
do not ship a reusable account password. Disable telemetry unless explicitly approved.

Build to a separate output directory on the external development storage after
checking space and mounts. Do not overwrite a working image/profile or delete
mounted build trees. Produce a preview ISO, SHA256SUMS, manifest, license inventory,
build instructions and known limitations. Do not commit large images/models to Git.
Do not flash a drive or publish a release yet. Commit and push reviewed sources.

Extra ISO/installer requirements:
- ______________________________
- ______________________________
- ______________________________
- ______________________________
```

After the assistant creates and validates a complete profile, the basic Archiso
build shape is below. This is NOT a command to run against today's incomplete
profile. Substitute only the verified profile/output paths; use fresh work paths:

```bash
sudo pacman -Syu --needed archiso qemu-desktop edk2-ovmf
mkarchiso --help
run_archiso --help
```

The assistant should then supply the exact `mkarchiso -v -w WORK -o OUT PROFILE`
command for its implemented profile. Archiso's `run_archiso` can boot the result in
QEMU; check its current help for UEFI options. Initial testing must expose only
disposable virtual disks, never raw host disks or writable personal shares.

## Prompt G: Installer And Release Acceptance

```text
Test the generated REgenOS ISO before any release. First inspect the build manifest
and image for private data and missing runtime assets. Record exact image hash.
Use disposable VMs with fresh virtual disks only; never pass through physical
disks, my external development SSD or internal Windows disk.

Test live boot and the graphical installer, selected disk isolation, cancellation,
low-space errors, approved manual/erase/encryption paths, bootloader creation,
reboot into the installed OS WITHOUT the ISO attached, and unique machine identity.
Ensure live-only accounts/autologin and insecure installer defaults do not survive
in the installed system. Verify an install on disk A never writes disk B or its EFI.
Test interrupted/failed installs and give a truthful recovery procedure.

On the freshly installed system test offline text inference, conversation persistence,
voice/wake assets, native hub/companion, original cursor, Super bindings, branding,
hardware adaptation, security rules, update/reboot and recovery. Disable the VM's
network for offline proof without severing the host's assistant connection. GPU,
microphone and suspend tests that VM hardware cannot prove remain explicitly untested.
Ask me separately to test a spare physical machine/disk after reviewing its identity.
Never propose writing an ISO over the SSD currently holding the development OS.

Create docs/ISO_ACCEPTANCE.md with pass/fail/not-tested results and release blockers.
Fix failures and rebuild with a new manifest/hash; retest the actual final artifact.
Provide ISO location, SHA256, supported configurations, limitations and recovery
instructions. Prepare a release checklist, but ask before public publication or
signing. Keep private signing keys off Git and out of the ISO. Commit/push reviewed
source and sanitized reports. Call it a preview if production blockers remain.

Extra acceptance/release requirements:
- ______________________________
- ______________________________
- ______________________________
```

## Resume Prompt For Later Sessions

```text
Resume REgenOS from docs/ARCH_HANDOFF.md and the latest sanitized installation,
acceptance, customization and ISO reports. Inspect Git status and actual installed
state before edits. Preserve all existing data/models and the internal Windows disk.
Current stage: ______________________________
Last successful checkpoint: ______________________________
Current blocker or new requirement: ______________________________
Read the corresponding stage prompt; summarize the next concrete action and
continue within its approval boundaries. Do not assume prior chat history exists.
```

## References

- [Official Codex CLI setup and sign-in](https://learn.chatgpt.com/docs/codex/cli)
- [Archiso profiles and VM testing](https://wiki.archlinux.org/title/Archiso)
- [Calamares distribution integration](https://calamares.io/about/)
- [Project hardware setup](HARDWARE_PORTABILITY.md)
- [Current feature checklist](FEATURE_STATUS.md)

Upstream package names, release tools and hardware support change. The Arch-side
assistant must verify them at the time of installation, not blindly repeat an old
command list. Development approval does not authorize erasing any disk.
