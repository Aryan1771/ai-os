# Remaining REgenOS work

2026-10-20 inventory, reconciled against [the 100-item audit](IMPLEMENTATION_CHECKLIST.md),
[owner requests](REQUEST_STATUS.md), [feature status](FEATURE_STATUS.md) and
[Arch stages A–G](ARCH_HANDOFF.md). Every original audit ID remains represented
below. An open acceptance item does not mean its implementation is missing.
Historical C++ requirements are superseded by the supported Python/PySide6 apps.

The latest incremental source checkpoint passed **1150 tests**; the earlier 11/11
fixed local model probes executed no probe actions. This does not accept real microphone
quality, login appearance, recovery, an installer or a distribution. There is
**no built/accepted preview ISO, final ISO path/hash or VM installation result**.

## First priorities

1. **Restore a usable login layout.** The owner reports the installed square GDM
   logo was oversized and hid the password field. The approved 144×48 landscape
   repair is installed with four-file/compiled-key readback; the owner must confirm login controls remain visible at the
   actual resolutions/scales. Installed hashes/dconf readback did not pass this
   visual check. See [branding and rollback](REGENOS_BRANDING_PROPOSAL.md).
2. **Accept the real voice loop and improve Hindi.** CUDA Whisper is selected with
   backup, but the saved base model rejects Hindi and small remains inaccurate
   on four synthetic Hindi sentences. Use explicit guided Record checks, measure
   each stage, and evaluate recognition/reply/audibility before enabling listening.
3. **Verify everyday interactions.** Check avatar unhide/monitor transfer, app-grid
   entries, three GNOME shortcuts, cursor, browser/tab launches, Stop/steering,
   memory controls and opted-in spoken device reactions with the owner.
4. **Close runtime/privacy/security gaps.** Measure concurrent LLM/STT/TTS VRAM;
   exercise denial/revocation/lock behavior; finish bounded memory/planning work
   and the chosen confinement design. Passing unit tests is not an independent audit.
5. **Establish boot recovery before splash work.** The newer elevated owner report
   provides current-UKI evidence and confirms the known fallback UKI path is not
   found. Reported GRUB product/custom menu alone does not identify the active
   entry. Existing Zen files are not a boot-tested recovery path. Plymouth is
   absent; no host boot writes occurred. Unknown custom recovery remains unknown.
6. **Agree the preview architecture, then implement packaging/installer and VM
   acceptance.** Complete the release gates below in order; do not jump to a build.

## Classification

- **Source**: nonprivileged implementation, documentation or automated validation
  still possible. It is not permission to download assets or change the host.
- **Owner**: physical interaction, subjective quality, available hardware or a
  real installed workflow needs the owner's acceptance.
- **Approval**: an exact privileged/system/service/driver/firewall/boot/mount or
  disk change needs approval first; an earlier approval applies only to its scope.
- **Deferred**: optional research, a separate project, or an unbounded promise
  outside a truthful preview. Reducing preview scope needs an explicit decision.

Combined labels mean both steps remain. New models/voices, remote providers and
continuous recording require their own opt-in even when work is labeled Source.

## Original audit: what remains

### Cursor and native desktop

| Audit IDs | State now and remaining work | Class |
| --- | --- | --- |
| A001, A002 | Cursor artwork/tooling and GNOME size 64 exist; accept conversion, hotspots, animation, GTK/Qt and mixed scaling in the real session. | Owner; Source for conversion defects |
| A003, A004 | Native Python Settings has nine pages; verify current page/control parity and remove obsolete C++ deployment requirements from older docs. A C++ rebuild is not a current runtime prerequisite. | Source, Owner |
| A005, A006 | Native controls and five themes exist; exercise responsiveness, disabled/busy feedback, contrast, compact layouts and actual saved changes. | Owner |
| A007, A008 | Naming/icon and atomic validated save/revert exist; accept installed identity and round trips while preserving older nested settings. | Owner |
| A009, A010 | Unhide/quit/reopen and single-instance IPC exist; accept resident visibility, independence from Settings and repeated launches. | Owner |
| A011, A012, A013 | Persistent blue particles, built-in forms and bounded custom grids exist; accept rendering, topic transitions and malformed-pattern recovery. | Owner |
| A014, A015 | Simulated mood bars/tone guidance exist; evaluate natural reactions and live controls without changing facts or consent. | Owner |
| A016, A017, A018 | Placement/style/activity/error states exist, including optional depth; accept live updates, speaking waveform, rest/idle recovery and sensor indicators. | Owner |
| A019 | Native launchers, optional startup/services and recovery controls exist; verify app-grid discovery and chosen login behavior without duplicate companions/listeners. | Owner; Approval for service changes |
| A020 | Bounded custom artwork is implemented; perfect artwork for every possible topic is not a completion promise. | Deferred |
| A021 | Motion is spring/wave animation; a physical liquid simulation is absent and optional. | Deferred |
| A022 | Pure Wayland layer-shell is absent; current X11/XWayland placement needs compositor acceptance. Add a native adapter only within chosen scope. | Source, Owner; optional |
| A023 | Screen selection, drag/persistence and usable-area clamping exist; test physical monitor transfer/reconnect/scaling. Avatar packs and a visual editor are missing. | Owner; Source for packs/editor |
| A024 | Universal replacement of every desktop's settings is absent; define supported adapters rather than promise all Arch settings. | Deferred |

### AI, commands and planning

| Audit IDs | State now and remaining work | Class |
| --- | --- | --- |
| A025 | Local Qwen text/tool probes pass; evaluate longer human conversations, ambiguity, task selection, cold/warm and sustained/concurrent load. A stronger model is not yet a demonstrated fix for every failure. | Owner, Source |
| A026, A027 | Ollama/OpenAI-compatible adapters and opt-in HTTPS exist; test explicitly selected additional servers/providers, secret handling and endpoint/consent changes without uploading private context implicitly. | Source, Owner |
| A028, A029 | Tool schemas/parsing and bounded avatar metadata exist; keep malformed-call, unknown-tool and speech-metadata regressions, and accept real model behavior. | Source, Owner |
| A030 | User daemon lifecycle and approved restart pass; daily-use restart/recovery/offline behavior still need acceptance. | Owner; Approval for new service changes |
| A031, A032 | Read-only hardware/process reports and volume/brightness adapters exist; validate actual supported devices and intended effects through native controls. | Owner |
| A033, A034, A035 | Bounded shell-free commands and fail-closed consent exist; continue hostile argument/race testing and independent review, including background denial and process termination. | Source, Owner |
| A036 | Three-step result-grounded loop, limited argument repair, cancellation and steering exist. Original-deadline checks now prevent stale new dispatch and preserve completed results. Durable recovery, general retry policy, better context/token budgeting and broad task acceptance remain incomplete. | Source, Owner |
| A037 | Python chat/history/speech replaces the historical C++ conversation claim; accept keyboard, current-turn steering, long replies and actual spoken interaction. | Owner; Source for stale docs |
| A038 | Exact native review and expiring background inbox exist. A separate trusted privileged broker/identity is not implemented; same-account dialogs are not OS-level authorization. | Source, Approval |
| A039 | Proprietary noncompatible provider adapters are absent and require separate scope. | Deferred |
| A040 | Sampled VRAM/latency exists, including CUDA STT; strict reservation/admission and worst-case concurrent 8 GiB guarantees do not. Implement chosen admission/unloading policy and measure overload/recovery. | Source, Owner |

### Voice and listening

| Audit IDs | State now and remaining work | Class |
| --- | --- | --- |
| A041, A042 | Capture and ONNX wake loading exist; test real wake accuracy/false activations, privacy indicators, explicit enable/disable and duplicate-listener avoidance. Continuous listening stays off until separately enabled. | Owner |
| A043 | Separate wait/silence/maximum and CUDA Whisper are implemented and selected; correct stale CPU-only audit wording. Hindi accuracy, accents, complete utterances and real latency remain open; small is not selected. | Source, Owner |
| A044 | Temporary audio cleanup exists; verify cancellation/error paths leave no recordings during real use without publishing private samples. | Owner, Source |
| A045, A046, A047 | Piper queue, speaking animation and feedback suppression exist; accept audible current-turn replies, mouth/waveform timing, no self-trigger and coordinated hardware speech. | Owner |
| A048 | Native asset/listening/service controls exist; accept path errors, responsiveness and useful failures. Service changes remain explicitly approved actions. | Owner, Approval |
| A049 | Protected explicit input selection, cancellable metadata checks and shared no-fallback capture routing pass 223 focused tests. Calibration, physical hotplug/noise recovery and laptop-specific VAD remain incomplete. | Source, Owner |
| A050 | Full acoustic echo cancellation, reliable barge-in and streaming STT/TTS are absent; speaking-flag suppression is not AEC. | Source, Owner; scope decision |
| A051 | Existing approved assets are preserved; a verified offline asset manifest/provisioning/download manager with licenses, retries and missing-asset handling is absent. | Source; separate download approval |
| A052, A053 | Sample-rate-aware bounded playback, custom wake-file controls and local tests exist; real voice quality, custom wake thresholds, timeout/stall handling and audibility need acceptance. Custom phrases need actual trained models. | Owner, Source |
| A054 | Synthetic transport/English checks passed; guided owner microphone→STT→model→speech, Hindi, echo, stop and recovery acceptance remain. Missing assets alone are not the current explanation. | Owner, Source |

### Memory and personalization

| Audit IDs | State now and remaining work | Class |
| --- | --- | --- |
| A055, A056, A057 | Legacy preferences/overrides/vocabulary/events exist behind consent and runtime boundaries; test intended expiry, protected terms and explicit real-user workflows. | Owner |
| A058 | Semantic APIs deliberately fail closed and preserve legacy vectors. Trusted offline embeddings and functional semantic integration are missing. | Source; asset/license approval |
| A059 | Recent sessions, lexical retrieval, notes and bounded reinforced statements exist; accept real fresh-process/restart recall, retention, inspect/edit/pin/forget and opt-out. | Owner |
| A060 | Native Python memory controls exist; verify import/export/edit/delete parity and reconcile the historical C++ wording. | Source, Owner |
| A061 | Semantic paraphrase consolidation, automatic summaries and conflict resolution are missing; basic secret heuristics are not complete sensitive-data protection. | Source, Owner |
| A062 | Fine-tuning/training pipeline is absent and intentionally separate from saved memory. | Deferred |
| A063 | Offline embedding/license/checksum/telemetry setup and successful semantic retrieval acceptance are missing; installing Chroma does not complete them. | Source, Owner; asset approval |

### Security and integration

| Audit IDs | State now and remaining work | Class |
| --- | --- | --- |
| A064 | Existing venv works and is preserved; validate future clean installation/ABI upgrades through packaging without global pip. No reinstall is needed just to close a checkbox. | Source |
| A065 | Protected-setting review exists; physically accept deny/revert/confirmation behavior, including attempts to weaken the guard. | Owner |
| A066, A067 | Hardening/AppArmor/firewall/scanner templates exist; reviewed installed enforcement, denied-write tests and rollback remain, not blanket script execution. | Source, Approval |
| A068 | Bounded data-only avatar rendering/native UI exists; retain hostile-input/privacy review and ensure no future model code/URL renderer is introduced. | Source |
| A069 | Independent daemon/settings/approval/user-data trust separation is absent; design authenticated IPC, identities and a threat model. | Source, Approval |
| A070, A071 | Exact diagnostics and Bubblewrap-backed broad grants are implemented. Cwd/interpreter-environment bootstrap shadowing is repaired and passes 79 focused regressions; resident reload is pending. Broader independent argument-policy/confinement/adversarial audit remains. Same-user access is not isolation from private files. | Source, Owner |
| A072 | System-wide domain-only egress is absent. Choose and review a real enforcement design; UFW's generic HTTPS allowance is not it. Preserve the development connection/recovery. | Source, Approval |
| A073 | Audited active AppArmor, seccomp, dedicated identity and secure secrets integration are incomplete; templates are not installed proof. | Source, Approval |
| A074 | Verified noexec temporary/cache policy is absent; propose exact compatible changes and rollback before any mount policy change. | Approval, Owner |
| A075 | Automatic incoming/removable-file scanning is not integrated; add bounded consent-aware watchers without automatic physical-disk mounting. | Source, Approval, Owner |

### Hardware, desktop and branding

| Audit IDs | State now and remaining work | Class |
| --- | --- | --- |
| A076, A077 | Capability/RAM policies, native Python Hardware page and cross-process lock exist; accept CPU overrides, absent/oversized-model failures, installed-only fallback and concurrency on supported machines; correct old C++ wording. | Source, Owner |
| A078 | Strict memory admission is covered by A040. Generic NPU inference/backend provisioning/universal compatibility are not implemented or verified. | Source for chosen backends; Deferred for universal claims |
| A079 | Device snapshots/polling/optional udev exist; accept actual attach/remove/reconnect and bounded identity handling. | Owner |
| A080 | Cooperative job state exists; a durable daemon scheduler/recovery system does not. | Source |
| A081 | Optional Hyprland listing/typing exists; GNOME is the real session. Validate only explicitly selected compositor adapters; do not imply general UI control. | Owner; Source for supported adapters |
| A082 | Three owner-approved GNOME Super+Alt shortcuts passed readback; physically test Settings/Chat/Companion and conflicts. Other desktop bindings need per-session acceptance/explicit scope. | Owner; Approval for additional changes |
| A083 | Source art/photo exists; resolve oversized login logo first, verify small/large readability and document redistribution permission/licenses for every bundled asset. | Source, Owner |
| A084 | Approved desktop/GDM stages installed nine files with matching hashes and compiled defaults. Visual login failed owner acceptance; wallpaper/lock/scaling/new-user checks remain. Do not restart GDM to preview. | Owner; Approval for changes outside approved repair |
| A085 | Boot theme/helper and source-only landscape UKI BMP/manifest exist; 20 artifact tests and decoded preview pass. Owner metadata/preset evidence supports Arch's embedded splash as the startup image. Active boot route/recovery, disposable-VM build/render and exact host generation/copy/activation approval remain. Static UKI artwork does not require Plymouth. | Source, Owner, Approval |
| A086 | Opt-in localized device speech is implemented; physically test first/repeated/improved monitor reactions. Autonomous AI job scheduling is still missing. | Owner; Source for scheduling |
| A087 | Opt-in OCR/AT-SPI/application metadata exist; arbitrary visual/UI navigation, hidden-program understanding and a full vision/action pipeline do not. Any future adapter needs explicit sensors, lock/revoke checks and bounded actions. | Source, Owner; broad promise Deferred |
| A088 | App themes and selected desktop/GDM stages exist; an integrated Qt/GTK/boot/login/icon theme manager is incomplete. Independent GNOME lock artwork is not established as supported. | Source, Owner, Approval |
| A089 | Firmware-logo replacement is not implemented and is not Plymouth's function. | Deferred |
| A090 | This NVIDIA host has limited GPU evidence; suspend/resume, audio/display regressions, portable external-SSD boot and another-machine matrix remain untested. No automatic driver changes. | Owner; Approval for any driver/system change |

### Packaging and validation

| Audit IDs | State now and remaining work | Class |
| --- | --- | --- |
| A091, A092 | Staged scripts and native installation exist; validate fresh supported target installation/upgrades with production paths and no Hyprland dependency. | Source; VM acceptance |
| A093, A094 | Archiso additions/Calamares skeleton are not a maintained image pipeline or installer. Complete the architecture and implementation gates below first. | Source, Approval |
| A095 | Current Python tests supersede historical Windows/C++ counts; run final applicable native/cursor/installation checks. Upstream Plymouth fixture tests require reviewed pinned source and are not real graphics/boot tests. | Source, Owner |
| A096 | Supported Python 3.12/PySide6 6.11.2 hosted CI passes through `945f3fc`, including normal teardown. Later changes need their own result; excluded 6.12 interaction remains unresolved. Historical C++ CI is not hardware acceptance. | Source |
| A097 | Pinned reviewed Calamares package/modules, clean target root, runtime packages, live-only launcher and complete version-sensitive integration are missing/unvalidated. | Source, Approval; VM acceptance |
| A098 | Reproducible preview/build manifest, installed target, boot/Secure Boot scope, update/rollback and recovery plan are incomplete. A release is not yet produced. | Source, Approval; VM acceptance |
| A099 | Complete the final-hash disposable-VM failure/partition/encryption/boot matrix below. Historical spare-drive wording authorizes no physical-disk writes; current scope is disposable virtual disks only. | Source; approved VM resources; Owner for nondestructive hardware checks |
| A100 | Production readiness is not established; all applicable runtime/security/release gates must pass or be explicitly scoped out in a labeled preview. | Deferred as a production claim |

## Newer owner requests not fully represented by A001–A100

| Request | Remaining work | Class |
| --- | --- | --- |
| Cohesive English/Hindi voice or own voice pack | Existing Piper voices are separate. Choose a compatible bilingual engine/weights, verify consent/licenses, approve any download and measure memory/latency; private voice enrollment is not cloning. | Source, Owner; asset approval |
| Owner voice recognition | Enrollment is saved after retries. Measure genuine/impostor false acceptance/rejection, different speaking styles/noise and Hindi before optional filtering; never use it as command/login authorization. | Owner |
| Full access / arbitrary commands | Timed ordinary-user grants, exact native review and revocation exist; accept the actual Permissions UI, expiry, denial and background inbox. Unconditional root/account access or bypassing disk/boot safeguards is not a missing feature to enable. | Owner; unrestricted promise Deferred |
| Computer context and learning | Physically test screen lock/revocation, AT-SPI coverage and app-name/time memory. No silent recordings of all program content, keystrokes or clipboard are part of scope. | Owner; Source for bounded supported adapters |
| Humanlike social quality | Evaluate natural moods/personality, continuity and useful device reactions in real conversation. Simulated first-person presentation must not claim sentience, training or fabricated memories. | Owner, Source |
| Research and spoken walkthrough | Article-first search/cited optional reports and one-shot paragraph navigation exist; accept topic ambiguity, links and English/Hindi explanation/narration with an actual microphone. Full-paper/web-wide research is not implemented. | Owner; Source for an explicitly scoped extension |
| Learned deletion | Test exact previews, recoverable Trash/restore and explicitly saved narrow rules with disposable files. Arbitrary deletion/system harmlessness cannot be guaranteed from past actions. | Owner; broad promise Deferred |
| Compact chat/transparency | Physically accept Enter/Ctrl+Enter, Stop, session binding and responsive controls. Public tool/status progress exists; hidden chain-of-thought disclosure is not a feature to add. | Owner |
| GitHub | Read-only exact-repository MCP reading exists. Verify revocation/disabled states; account writes are outside this adapter's scope, while reviewed developer commit/push is separate. | Owner; writes Deferred pending separate scope |
| Shutdown/restart | Exact native scheduling/cancellation is implemented with mocked tests. Actual OS authorization/inhibitor and timed cancellation behavior is untested; do not power off the host merely for a smoke test. | Owner, Approval for an actual power action |
| First-run setup | Six-page native source and temporary preview exist. Verify Hindi fonts, clean new-user defaults, permission choices, completion/live gating and installed-only autostart in the final VM target. Host autostart was not installed. | Source; VM acceptance; Owner for appearance |
| Documentation/Git handoff | Reconcile stale C++/CPU-only/historical checkmarks; record final fixes, exact tests, failures/rollback and acceptance evidence. Review, commit and push intentional source/sanitized docs; never private data/artifacts. | Source |

## Preview ISO and installer gates, in dependency order

These are outstanding tasks, not authorization to run packaging, privileged
commands, mounts or disk operations. Follow [Prompt F/G](ARCH_HANDOFF.md) and
[the installer contract](../archiso/calamares/README.md).

1. **Approve the architecture/scope.** Specify supported x86-64 hardware and boot
   modes, live desktop/user, kernel/recovery strategy, Secure Boot/BIOS exclusions,
   Python runtime isolation/production paths, package source/signing, clean target
   root, offline assets/licenses, update/rollback and disk/RAM/build-space budget.
   Label preview versus release and approve supported manual/erase/encryption paths.
2. **Finish reproducible packages.** Pin source revisions/dependencies; clean-build
   runtime/native Python Settings/companion/assets/defaults/services and Calamares
   from reviewed sources. Verify signatures and record package versions/checksums.
   Never embed the development checkout, username or personal venv/config.
3. **Build a clean installed target root.** Exclude the live root's accounts,
   autologin, installer/developer packages, mounts and credentials. Supply the real
   `/usr/share/regenos/installer/install-rootfs.squashfs` build pipeline, ownership,
   service/locale/network setup, generic hardware defaults and identity generation.
4. **Validate exact Calamares versions/modules.** Confirm every configured module
   exists; finish settings, branding, unpackfs, authorization agent, target users,
   partition/encryption/bootloader/initramfs behavior. Install launcher/autostart
   only in the live session; keep the final unmistakable selected-disk confirmation.
   Remove or label unsupported choices instead of presenting them as working.
5. **Audit all distributable assets.** Verify licenses/provenance/redistribution,
   hashes and sidecars for art/fonts/voices/wake/Whisper/LLM/embeddings. Never copy
   personal Ollama stores. Bundle only approved redistributable assets; otherwise
   provide an explicit first-run provisioning path and do not claim fully offline-ready.
6. **Complete the maintained Archiso profile/build script.** Use tracked generic
   inputs, clean package sources and a fresh separate work/output directory after
   mount/free-space checks. Preserve host disks and recovery. Record exact build
   commands, package/source revisions, manifest, licenses and ISO SHA256.
7. **Inspect the final image for private/live state.** Exclude credentials, browser/
   Wi-Fi profiles, memory/chat databases, recordings, keys, signing keys, machine
   IDs, personal overrides and reusable passwords. Verify installed/live separation
   and unique machine/host-key generation; telemetry stays opt-in.
8. **Run disposable-VM live acceptance.** Only disposable virtual disks, no host
   disk passthrough/writable personal shares. Test live UEFI boot, graphical desktop,
   installer launch, selected-disk isolation and network-disabled behavior for the
   assets actually bundled; do not sever the host development connection.
9. **Run every supported installer path and failure.** Test cancellation before
   writes, manual/erase/encryption paths actually implemented, final disk warning,
   two-virtual-disk isolation, low space, interruptions/failed installs, bootloader
   failure and honest recovery. Unsupported paths stay not tested/unsupported.
10. **Boot the installed VM without the ISO.** Verify UEFI bootloader, fresh
    identities/users/permissions, no live autologin or repeated installer launch,
    installed-only onboarding, services/runtime, offline inference/available voice
    assets, memory, native apps/companion, shortcuts/cursor/branding, hardware policy,
    security defaults, update/reboot/rollback and recovery.
11. **Fix, rebuild and retest the final artifact.** Every accepted result must name
    the final ISO hash. Update sanitized [install results](ARCH_INSTALL_RESULTS.md),
    [Arch acceptance](ARCH_ACCEPTANCE.md) and [ISO acceptance](ISO_ACCEPTANCE.md)
    with exact commands and pass/fail/not-tested. VM results do not prove physical
    NVIDIA/microphone/suspend/multi-machine support.
12. **Review the preview deliverables.** Report branch/commit, changed files,
    tests/VM cases, final ISO path/hash if one exists, limitations and recovery.
    Commit/push reviewed source/docs only. No flashing, signing, release upload or
    publication without a separate exact approval; keep ISO/models/keys out of Git.

Host Windows/development disks and private runtime/model stores remain protected
through every stage. A critical runtime/security failure blocks ISO release work.
