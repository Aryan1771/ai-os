# REgenOS implementation and Arch verification audit

Latest 2026-10-20 incremental evidence: **1150 local tests passed in 11.92s**;
listener rejection recovery and privacy-safe guided stage timings are implemented.
Separately approved core restart passes with unchanged config/listening off.
The owner installed the compact 144×48 GDM logo; file/key readback passes, physical
appearance remains pending. Elevated inspection reports current UKI evidence and
the missing known fallback path, not a verified recovery boot. Hosted assertions
pass but Qt shutdown exits 139; controlled diagnostics remain unresolved. These
results close no untested hardware/security/ISO acceptance item. See
[CHECKPOINT_PROGRESS](CHECKPOINT_PROGRESS.md) for current gates; counts below are
historical.

2026-10-20 source checkpoint: **1080 passed in 12.63s**, correctness lint and
whitespace clean. Local fixed model checks **11/11**, zero tools executed. Earlier native
nine-page greeting and six-page temporary onboarding previews passed; final UI
greeting attempts were interrupted by window closure (not passed), while a
current tool-free local core reply passed in 4.521s; no physical
microphone, boot, installer or multi-monitor acceptance is inferred.

Implemented: optional 2D/3D avatar and responsive opt-in sensor menus; placement/
Stop/steering repairs; recipient-bound final privacy checks including revoked
app-usage/OCR/accessibility consent; article-first research, optional saved reports
and one-shot report navigation; website synonyms and bounded read-only argument
repair; native reviewed power scheduling; Aurora Ridge branding and six-page
post-install setup with completed/live gating. See [HANDOFF](HANDOFF.md),
[request status](REQUEST_STATUS.md), [setup](FIRST_RUN_SETUP.md) and
[branding proposal](REGENOS_BRANDING_PROPOSAL.md).

Approved CUDA executable-only switch is applied with backup; base/model/language/
profile/listening unchanged. Five-phrase comparison CPU 80.243s/CUDA 22.500s,
sampled CUDA peak 961 MiB with Ollama unloaded. English exact; Hindi still inaccurate
or rejected. No universal command, GPU support, sentience, training or finished-OS
claim. Owner-approved restart of only `ai-os.service` passed active/running readback,
with listening/wake/filter off and config unchanged. Owner-approved desktop/GDM artwork and defaults installed with private backups;
source hashes, compiled databases and logo-key readback pass. Visual login is
pending. No boot write, ISO build, VM test or publication.

2026-10-19 checkpoint: voice silence/utterance separation, language/current-turn
routing, shared speech ownership, queued device reactions and memory decay repairs
are source-tested; see [PERSONAL_INTERACTION](PERSONAL_INTERACTION.md). Full suite:
350 passed, 1 failed, 7 errors (restricted local sockets). No unchecked hardware,
desktop, model-quality or ISO acceptance item is closed by these source results.

Audit date: 2026-09-27. Scope: every checkbox in FEATURE_STATUS.md, against the
current source and this session's measurements. This is an inventory and gap
audit, not independent security certification. Old checkmarks mean source claims,
not installation or hardware acceptance. Evidence must be attached before closing
any remaining task. The older C++ UI is outside the supported Python/PySide6 path.

## Dependency order

1. **P0 — Installed-runtime provenance and backup:** confirmed editable source,
   older installed metadata/config, user unit path, private pre-migration backup.
   Direct Ollama CLI use bypasses the harness. Approved Whisper/Piper/speaker
   assets are now installed; preserve them and the existing private runtime.
2. **P1 — Core latency:** CPU and small GPU inference probes passed; the historical
   driver mismatch is superseded. Sampled VRAM is not worst-case or a hard cap.
   Continue context budgeting, request scheduling, concurrent-load measurement
   and bounded multi-tool result-grounded follow-ups.
3. **P2 — Continuity:** persistent sessions, explicit preferences, lexical retrieval,
   native/CLI inspection/deletion tested; validate the user's actual entry point,
   then tighten tokenizer-aware budgeting, concurrent requests and privacy controls.
4. **P3 — Voice:** use the already provisioned assets and instrument capture/STT/model/
   synthesis/playback separately, validate current replies with the user, then VAD,
   recorder-stall handling, cancellation, echo suppression and hotplug.
5. **P4 — Native Qt:** conversation and memory pages now Python; validate real
   interaction, all saved controls and multi-monitor behavior; hardware policy
   controls now exist in Python. Layer-shell and avatar editor come after reliable basic UI.
6. **P5 — Permissions/security:** independently audit argument policies, trusted
   native consent and user-data boundaries, then approved AppArmor/firewall work.
   No weakening of fail-closed behavior to make tests pass.
7. **P6 — Desktop/branding:** optional compositor, shortcuts/cursors/appearance,
   approved login/lock/boot integration; suspend and portable hardware matrix.
8. **P7 — Packaging:** reproducible packages and VM-only Archiso/Calamares work,
   including failed-install recovery, before any real disk installation.

**M** = missing code; **I** = incomplete integration; **H** = hardware/user acceptance
missing. **S** = implementation found in source, not independently verified for
all cases. **T** = relevant local automated coverage exists, not full acceptance.

## Item-by-item checklist

Each A-number corresponds to one original checkbox in file order. Source evidence
is grouped immediately above each section; item-level exceptions follow in the
last column. All rows remain open until their stated acceptance gap is closed.

### Cursor

Source inspected: `ai_os/cursor_theme.py; scripts/install_cursor_theme.sh; tests/test_cursor_theme.py`.

| ID | Original claim | Status / remaining acceptance |
|---|---|---|
| A001 (P6) | Original Cool cursor artwork, Linux conversion/installation tooling, desktop defaults and appearance-panel integration; see [cursor guide](CURSOR_THEME.md). | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A002 (P6) | Validate converted cursor hotspots, animation and compositor behavior on Arch. | H — Conversion test still skipped; inspect cursor hotspots/animation in session. |
### Native Desktop And Companion

Source inspected: `ai_os/native_settings.py; native_widgets.py; avatar_overlay.py; pixel_engine.py; tests/test_native_ui.py; tests/test_companion.py`.

| ID | Original claim | Status / remaining acceptance |
|---|---|---|
| A003 (P4) | Compiled C++17/Qt 6 Widgets hub with application-menu launcher and a private child-process Python backend. No browser, HTML, JavaScript frontend, HTTP settings endpoint, Electron or WebEngine. The animated overlay remains Python/Qt. | S/I — historical C++ implementation is not supported deployment evidence. Python conversation/memory now added; full page parity pending. |
| A004 (P4) | Eight pages: conversation, AI connection, voice/listening, companion, appearance, memory preferences, permissions and context notebook. All persisted settings are described by the backend and represented with native controls. | S/I — historical C++ implementation is not supported deployment evidence. Python conversation/memory now added; full page parity pending. |
| A005 (P4) | Native checkboxes, selectors, numeric controls, sliders, color dialog, file pickers, confirmation dialogs and status feedback. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A006 (P4) | Five REgenOS window themes: forest, graphite, ocean, light and sunrise. Graphite is the ordinary charcoal dark default for new configurations, not high-contrast mode. Existing choices are preserved. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A007 (P4) | Saved product/companion names update native window identity; an existing local logo path supplies the Settings window icon. This does not rewrite `/etc/os-release` or boot branding. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A008 (P4) | Save/revert preferences; validate values before an atomic config write; keep existing nested defaults when upgrading older configs. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A009 (P4) | Native transparent corner companion, shown/hidden from Settings; independent lifetime after closing Settings; click to reopen Settings; context-menu hide. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A010 (P4) | Single-instance protection for both applications. Reopening Settings raises the existing window using user-local IPC. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A011 (P4) | Pixel robot rendered in real time with a bounded 2D particle system. Persistent pixels travel between shapes; spring damping and waves create fluid-looking transitions. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A012 (P4) | Twelve built-in forms: core robot, heart, music, code, idea, cloud, gear, shield, folder, chip, search and clock. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A013 (P4) | Additional forms can come from model-generated 4-24-cell-wide/high pixel patterns. Only a small fixed character palette is accepted; malformed patterns are ignored. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A014 (P4) | Face changes from emotional state, including happy, concerned, focused, low-energy and curious variants. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A015 (P4) | Six emotion bars: joy, curiosity, focus, calm, concern and energy. Baseline sliders, reactivity control and smoothly changing live values are implemented. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A016 (P4) | Corner, scale, color, fluid-motion intensity, animation enable, resting form, topic morphing and visible-bar preferences update in the running overlay. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A017 (P4) | Activity states connected to wake-word readiness, capture, transcription, model requests, tool execution, response, speech and errors. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A018 (P4) | Stale or malformed activity snapshots recover to idle; state files contain presentation metadata rather than executable instructions or hidden reasoning. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A019 (P4) | Native `.desktop` launchers, optional login autostart instructions, optional companion user service, and Hyprland floating/pinned rules. | T/H — native Settings launch/recovery and read-only companion status have regressions; existing launchers inspected. Status does not establish resident visibility, app-grid discovery or login acceptance. |
| A020 (P4) | Unrestricted high-quality conversion of every possible topic into artwork. Custom grids are supported, but model artistry/reliability is not guaranteed. | M/H — Bounded pixel grids exist; unrestricted quality is not a realistic completion guarantee. |
| A021 (P4) | Physical liquid simulation. The current renderer is a controlled spring/wave animation. | M — Spring/wave renderer exists; physical simulation absent and optional. |
| A022 (P4) | Pure Wayland layer-shell overlay. Current corner placement uses X11 or XWayland; validate placement and pinning on the installed compositor. | M/H — No layer-shell adapter; XWayland rendering smoke passed, compositor placement pending. |
| A023 (P4) | Arbitrary multi-monitor selection, drag-to-place persistence, avatar packs, and a visual pixel editor. | T/M/H — display selection/drag, usable-area clamping and manual placement across unrelated preference refreshes have synthetic coverage. Physical multi-monitor/compositor acceptance remains; packs/editor absent. |
| A024 (P4) | Complete replacement of every Linux desktop environment's settings application. | M — No universal desktop settings adapters; constrain supported scope. |
### AI And Tool Execution

Source inspected: `ai_os/ai_os_core.py; tools/system_tools.py; security/consent_broker.py; tests/test_core_protocol.py; tests/test_command_risk.py`.

| ID | Original claim | Status / remaining acceptance |
|---|---|---|
| A025 (P1) | Local Ollama connection, configured for `qwen2.5:7b-instruct-q4_K_M` by default. | T/H — installed model completed CPU/GPU probes and synthetic continuity checks. Historical driver mismatch is resolved; sustained/concurrent GPU and owner quality acceptance remain. |
| A026 (P1) | OpenAI-compatible model endpoint support, including another offline loopback server. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A027 (P1) | Optional HTTPS remote provider mode with hostname approval and API key supplied via an environment variable. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A028 (P1) | Text and JSON tool-call parsing, registered-tool routing and rejection of unknown tool names. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A029 (P1) | Optional structured reply with avatar shape, emotion values and custom pixel grid; avatar metadata is excluded from spoken reply text. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A030 (P1) | Terminal interaction and a daemon mode that remains alive under systemd. | T — direct daemon SIGTERM and installed user-service lifecycle passed; interactive daily-use acceptance pending. |
| A031 (P1) | Hardware/CPU/RAM/disk/battery statistics, NVIDIA query adapter and process listing. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A032 (P1) | PipeWire `wpctl` volume/mute and `brightnessctl` brightness adapters. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A033 (P1) | Command assessment, subprocess timeouts, captured results and `shell=False` execution. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A034 (P1) | Risky command consent and process-termination consent. Model-supplied `approve=true` cannot approve its own request through the router. | T/H — argument/consent regression coverage; independent audit and hostile-input review pending. |
| A035 (P1) | Background/noninteractive consent requests are denied instead of waiting on nonexistent terminal input. | T/H — argument/consent regression coverage; independent audit and hostile-input review pending. |
| A036 (P1) | Complete autonomous planning loop with multiple tool steps, result-grounded follow-up answers, retry policies and durable task recovery. | T/I/H — three-step schemas/result follow-up, duplicate/approval stops, owned cancellation and bounded same-session steering references are implemented. The fixed local benchmark passes 11/11 without executing tools; one real read-only diagnostic grounds its reply. Durable recovery, retry policy and broad owner task acceptance remain absent. |
| A037 (P1) | Native C++ conversation window, with recent-history loading and optional spoken replies using the saved Piper voice. | S/I — historical C++ implementation is not supported deployment evidence. Python conversation/memory now added; full page parity pending. |
| A038 (P1) | Native system-action approval broker. Background risky actions still fail closed; the hub is not a privileged approval channel. | T/I/H — Exact native review and an expiring background proposal inbox exist. Sudo requires separate visible-terminal authentication; same-account dialogs are not independent privileged authorization. No model self-approval. |
| A039 (P1) | Native adapters for every provider's proprietary protocol. Present remote support assumes an OpenAI-compatible chat-completions schema. | M — Only Ollama/OpenAI-compatible protocols implemented. |
| A040 (P1) | Hard enforcement of an 8 GB VRAM ceiling, GPU admission control, adaptive model unloading and model performance benchmarks. | M/H — CPU/GPU latency probes and sampled device-wide peaks exist; no strict VRAM reservation/admission or sustained simultaneous worst-case bound. |
### Voice And Listening

Source inspected: `ai_os/services/listener.py; stt.py; wakeword.py; ai_os/speech_queue.py; tests/test_listener.py; tests/test_hub_backend.py`.

| ID | Original claim | Status / remaining acceptance |
|---|---|---|
| A041 (P3) | Local PipeWire microphone capture with openWakeWord gating. | T/I/H — capture transport and existing openWakeWord ONNX backend/model loading passed separately. Real wake accuracy, acoustic rejection and end-to-end owner acceptance remain pending. |
| A042 (P3) | Explicit listening and wake-word switches; microphone stays off until both are enabled. | T/H — continuous capture requires listening plus an explicit wake or conversation mode; one-shot capture requires its own Record consent. Listening remains opt-in; owner disable/indicator checks remain. |
| A043 (P3) | Fixed-duration command recording and local Whisper.cpp transcription adapter. | T/H — distinct wait/silence/maximum and transcript rejection are tested. Approved small-model CPU comparison passes Hindi script only, with poor single-phrase WER/CER and slower output; no setting switched. GPU Whisper build/runtime and personal Hindi/accent/latency acceptance remain pending. |
| A044 (P3) | Temporary command WAV deletion after transcription. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A045 (P3) | Piper speech queue with sentence splitting and priority bridge messages; PipeWire playback adapter. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A046 (P3) | Speech activity drives the companion and carries model-generated form metadata into playback. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A047 (P3) | Wake detection is suppressed while the speech queue is speaking; recorder frames continue to be consumed in that period. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A048 (P3) | Native controls for voice/model paths, wake threshold and recording duration; service start/restart/stop buttons. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A049 (P3) | Verified microphone selection, hotplug recovery, user-calibrated voice activity detection and noise suppression on the laptop. | M/H — Capture transport verified; explicit device selection, VAD calibration, hotplug/noise handling incomplete. |
| A050 (P3) | Full acoustic echo cancellation, reliable interruption/barge-in, streaming transcription and streaming speech. | M/I/H — Feedback suppression is a speaking flag; no AEC/barge-in or streaming STT/TTS. |
| A051 (P3) | Voice/model download manager and all wake/embedding model assets pre-provisioned for first-run offline use. | M/I — CLI adapters exist; no verified asset manifest/provisioner. Do not redownload installed models. |
| A052 (P3) | Piper WAV playback uses each voice's sample rate rather than fixed 22050 Hz; bounded synthesis/playback subprocesses are reaped on timeouts, temporary audio is removed, and failures are surfaced without killing the speech worker. Real audio remains unverified here. | T/H — installed English/Hindi Piper assets, synthetic synthesis/STT and playback transport have evidence; subprocess/WAV cleanup tests pass. Current spoken relevance, quality, echo and owner audibility acceptance remain. |
| A053 (P3) | Custom ONNX/TFLite wake-word file selection, voice duration multiplier and native voice-test command. A custom phrase requires a trained wake-word model, not simply typing a new name. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A054 (P3) | End-to-end Arch audio validation with the installed Ollama, Whisper and Piper models. | T/I/H — configured Whisper/Piper assets are installed; synthetic English closed-loop/timing checks pass. Guided owner microphone/reply/audibility checks and reliable Hindi recognition remain; missing models are not the current blocker. |
### Memory And Personalization

Source inspected: `ai_os/conversation_memory.py; memory_cli.py; memory_widget.py; tools/memory_tools.py; tests/test_conversation_continuity.py`.

| ID | Original claim | Status / remaining acceptance |
|---|---|---|
| A055 (P2) | Local habits JSON with permanent defaults and temporary overrides that expire. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A056 (P2) | Slang/jargon replacement dictionary and protected-term handling. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A057 (P2) | Local event log and recent-event text search. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A058 (P2) | Optional ChromaDB store/search helper functions and persistent local collection path. | T/M/I — compatibility APIs fail closed without importing Chroma, opening legacy stores, downloading embeddings or emitting telemetry. Existing vectors are preserved; functional semantic access requires unimplemented trusted offline setup. |
| A059 (P2) | Bounded persistent recent conversation history and automatic keyword retrieval of explicitly curated context notes into model requests, shared by default across terminal, voice and hub. Local SQLite; no embedding download required. Can be disabled. | T/I — fresh-process follow-up and forget tested with real Ollama using temporary synthetic data; real Phase 1 runtime had no database. |
| A060 (P2) | Context note create/edit/delete, text/Markdown import, validated JSON import/export, conversation retention and clear-history controls in the C++ hub. | S/I — historical C++ implementation is not supported deployment evidence. Python conversation/memory now added; full page parity pending. |
| A061 (P2) | Semantic retrieval of older conversation facts, sensitive-data filtering, automatic summarization and memory conflict resolution. Keyword notes plus recent history are not unlimited memory. | M/I — New bounded lexical older-turn retrieval and basic secret heuristic tested; semantic retrieval/summarization/conflict resolution absent. |
| A062 (P2) | Self-training or local model fine-tuning. Saving facts and preferences does not modify model weights. | M — No training pipeline, intentionally deferred; memory is not model training. |
| A063 (P2) | Offline provisioning/verification of Chroma's embedding model and full semantic-memory integration tests. | T/M/I/H — no trusted verified offline embedding setup exists. APIs return setup-required even with ordinary memory enabled or Chroma installed; regression tests prevent import, download, telemetry and legacy-store access. Successful retrieval acceptance remains pending. |
### Security And System Integration

Source inspected: `ai_os/settings_store.py; security/consent_broker.py; tools/system_tools.py; security/apparmor.ai-os; scripts/security_baseline.sh`.

| ID | Original claim | Status / remaining acceptance |
|---|---|---|
| A064 (P5) | Python venv installation; no global pip package modifications. | T — existing venv preserved; refreshed project metadata only, no model/dependency reinstall this phase. |
| A065 (P5) | Native confirmation for protected settings, including disabling the confirmation guard itself. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A066 (P5) | AppArmor and systemd hardening templates, firewall baseline script and ClamAV scanner adapter. | S/I/H — templates exist; installed confinement not established and no policy changed. |
| A067 (P5) | Protected `/etc`, `/boot`, `/usr` writes in the supplied AppArmor policy. | S/I/H — templates exist; installed confinement not established and no policy changed. |
| A068 (P5) | No model-executed avatar code, no rendering URLs or scripts, and no browser-based settings server. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A069 (P5) | Independent OS-level trust separation between daemon, settings, consent and user files. A settings dialog under the same Linux account is not a full security boundary. | M/I — Same-account files and confirmation dialogs do not establish privilege separation. |
| A070 (P5) | Silent command execution limited to exact diagnostic argument forms, restricted package/service queries and trusted `/usr/bin` resolution on Linux. General-purpose interpreters/editors/search tools now require approval. | T/H — argument/consent regression coverage; independent audit and hostile-input review pending. |
| A071 (P5) | Independent command-policy audit and OS-level confinement. Restricted diagnostics alone are not a complete sandbox. | I/H — Argument-level regression tests exist; independent security audit/confinement pending. |
| A072 (P5) | Network-wide domain-only egress enforcement. The current UFW baseline permits outbound DNS, HTTP and HTTPS generally; the Python provider broker enforces its own hostname policy. | M/I — UFW permits generic HTTPS; app hostname checks are not system-wide domain enforcement. |
| A073 (P5) | Audited AppArmor enforcement on the actual Arch install, seccomp policy, dedicated service identity and secure secrets storage. | M/I/H — Template only; installed unit lacks AppArmorProfile. No applied-policy audit, seccomp or secret service. |
| A074 (P5) | Verified `noexec` mount policy for temporary/cache directories; a script/template alone does not establish this. | I/H — No mount policy was applied or verified; requires approved system changes. |
| A075 (P5) | Automatic ClamAV scanning of every incoming/removable-media file. | M/I — Scanner adapter exists; no incoming-file/removable-media watcher integration. |
### Hardware, Desktop And Branding

Source inspected: `ai_os/hardware_profile.py; hardware_monitor.py; services/jobs.py; tools/ui_tools.py; config/hypr; branding; tests/test_hardware_profile.py`.

| ID | Original claim | Status / remaining acceptance |
|---|---|---|
| A076 (P6) | Read-only x86-64 Linux capability profiles, installed-model RAM admission, bounded context/threads, opt-in installed-model fallback and per-machine CPU overrides. Rechecked at daemon startup and before requests; no automatic downloads or driver changes. See [portability setup and acceptance tests](HARDWARE_PORTABILITY.md). | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A077 (P6) | Native C++ Hardware settings/report page and cross-process inference lock for REgenOS clients. NPU detection is informational, not NPU inference support. | S/I — historical C++ implementation is not supported deployment evidence. Python conversation/memory now added; full page parity pending. |
| A078 (P6) | Exact memory reservation/VRAM enforcement, NPU inference adapters, runtime backend provisioning and universal hardware compatibility. | M/H — Estimated RAM policy and locks only; NPU informational, universal compatibility unproven. |
| A079 (P6) | Hardware snapshot comparison, polling monitor and optional block-device udev event monitor. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A080 (P6) | Cooperative background job registry with pause/cancel state; it is a library rather than a full daemon scheduler. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A081 (P6) | Phase-gated Hyprland window listing and a separate typing adapter; typing is not exposed as a registered daemon tool. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A082 (P6) | Super-key bindings for native Settings/companion, launcher, terminal, file manager, AI service control, volume, brightness and locking. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A083 (P6) | Original REgenOS logo, wallpapers, lock-screen art, companion concept atlas and Plymouth theme sources. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A084 (P6) | Explicit user appearance application: GTK icon/cursor/font preferences plus Hyprpaper/Hyprlock config, with backups of pre-existing files. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A085 (P6) | Written boot-splash, desktop, logo installation and branding commands. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A086 (P6) | Hardware events automatically routed into conversations/speech and jobs automatically scheduled by the AI. | T/I/H — bounded localized device/display speech reactions are connected behind explicit opt-in; owner attach/remove acceptance remains. Autonomous AI job scheduling is not implemented. |
| A087 (P6) | Compositor-wide autonomous window manipulation, arbitrary UI navigation and completed vision pipeline. OpenCV is only an optional dependency. | M/I/H — Phase-gated window listing/typing only; no general navigation/vision pipeline. |
| A088 (P6) | Full OS theme engine across Qt, GTK, bootloader, display manager, application icons and all desktop components. | M/I/H — App themes and user appearance files exist; no complete Qt/GTK/boot/login theme manager. |
| A089 (P6) | Firmware-logo replacement. Plymouth only covers the later Linux boot stage. | M — Not implemented; Plymouth cannot replace firmware branding. |
| A090 (P6) | Portable multi-machine driver handling, suspend/resume verification and NVIDIA/audio/display regression testing. | I/H — current RTX 4060/NVIDIA access and small GPU inference probes pass; the historical mismatch is resolved. Portable driver behavior, suspend and multi-machine audio/display acceptance remain unverified. |
### Packaging And Validation

Source inspected: `install; scripts; systemd; archiso; .github/workflows; tests`.

| ID | Original claim | Status / remaining acceptance |
|---|---|---|
| A091 (P7) | Repository installer/config/branding/docs layout and staged Arch setup scripts. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A092 (P7) | Separate native-UI installation stage that does not require Hyprland. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A093 (P7) | Archiso package additions and branded-live-image instructions. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A094 (P7) | Calamares integration plan and references. | S; H — implementation found in the cited source; item-specific installed acceptance remains unverified. |
| A095 (P7) | Automated Python/Qt checks plus C++ widget and real-backend load/save checks; offscreen hub screenshots at desktop and compact sizes. Local result: 84 Python tests passed, one cursor conversion test skipped without ImageMagick; C++ test suite passed. Hardware policy tests use synthetic device inventories, not Arch hardware. | T — current Python tests supersede old count; no new C++ build or cursor conversion acceptance. |
| A096 (P7) | Linux CI workflow for Python, real cursor conversion, C++ compilation and offscreen bridge tests. CI is not Arch hardware certification. | S/H — workflow source inspected; no remote CI result asserted in this session. |
| A097 (P7) | Finished graphical disk installer, complete Calamares modules/branding/launcher and reproducible signed package source. | S — Initial module sequence, REgenOS branding, launcher and install-image contract added; not in the ISO. M/I/H — pinned signed Calamares package source, clean target root image/build, package-version validation, Archiso integration and disposable-VM acceptance remain. |
| A098 (P7) | Reproducible release ISO, verified installed target system, Secure Boot policy, upgrades, rollback and recovery media. | M/I/H — No tested reproducible release, signing/rollback/update/recovery design. |
| A099 (P7) | Partitioning/encryption/bootloader failure-path testing in disposable VMs and spare drives. | H — Requires disposable VM acceptance matrix before any spare drive; never internal Windows disk. |
| A100 (P7) | End-to-end production readiness. Do not interpret implemented components as a fully validated autonomous OS. | I/H — Blocked by preceding runtime, security and installer work; do not mark complete. |

2026-10-16 follow-up: see [PERSONAL_INTERACTION](PERSONAL_INTERACTION.md). Language/reinforcement/device-speech/cursor source work has focused regression coverage; no hardware or ISO checkboxes promoted.
