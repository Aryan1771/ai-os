# REGENOS Feature Checklist

Updated 2026-09-25. Checked items mean implemented in this repository, not certified on the Arch laptop. The Python/Qt tests run on Windows with offscreen Qt rendering. PipeWire, NVIDIA, systemd, AppArmor, Hyprland and ISO installation need target-system validation. This is an application/distribution prototype, not a completed independently installable operating system.

## Native Desktop And Companion

- [x] Native Python/Qt Settings application with application-menu launcher. No browser, HTML, JavaScript frontend, HTTP settings endpoint, Electron or WebEngine.
- [x] Six settings pages: companion, AI connection, voice/listening, appearance, desktop and permissions.
- [x] Native checkboxes, selectors, numeric controls, sliders, color dialog, file pickers, confirmation dialogs and status feedback.
- [x] Five REGENOS window themes: forest, graphite, ocean, light and sunrise.
- [x] Saved product/companion names update native window identity; an existing local logo path supplies the Settings window icon. This does not rewrite `/etc/os-release` or boot branding.
- [x] Save/revert preferences; validate values before an atomic config write; keep existing nested defaults when upgrading older configs.
- [x] Native transparent corner companion, shown/hidden from Settings; independent lifetime after closing Settings; click to reopen Settings; context-menu hide.
- [x] Single-instance protection for both applications. Reopening Settings raises the existing window using user-local IPC.
- [x] Pixel robot rendered in real time with a bounded 2D particle system. Persistent pixels travel between shapes; spring damping and waves create fluid-looking transitions.
- [x] Twelve built-in forms: core robot, heart, music, code, idea, cloud, gear, shield, folder, chip, search and clock.
- [x] Additional forms can come from model-generated 4-24-cell-wide/high pixel patterns. Only a small fixed character palette is accepted; malformed patterns are ignored.
- [x] Face changes from emotional state, including happy, concerned, focused, low-energy and curious variants.
- [x] Six emotion bars: joy, curiosity, focus, calm, concern and energy. Baseline sliders, reactivity control and smoothly changing live values are implemented.
- [x] Corner, scale, color, fluid-motion intensity, animation enable, resting form, topic morphing and visible-bar preferences update in the running overlay.
- [x] Activity states connected to wake-word readiness, capture, transcription, model requests, tool execution, response, speech and errors.
- [x] Stale or malformed activity snapshots recover to idle; state files contain presentation metadata rather than executable instructions or hidden reasoning.
- [x] Native `.desktop` launchers, optional login autostart instructions, optional companion user service, and Hyprland floating/pinned rules.
- [ ] Unrestricted high-quality conversion of every possible topic into artwork. Custom grids are supported, but model artistry/reliability is not guaranteed.
- [ ] Physical liquid simulation. The current renderer is a controlled spring/wave animation.
- [ ] Pure Wayland layer-shell overlay. Current corner placement uses X11 or XWayland; validate placement and pinning on the installed compositor.
- [ ] Arbitrary multi-monitor selection, drag-to-place persistence, avatar packs, and a visual pixel editor.
- [ ] Complete replacement of every Linux desktop environment's settings application.

## AI And Tool Execution

- [x] Local Ollama connection, configured for `qwen2.5:7b-instruct-q4_K_M` by default.
- [x] OpenAI-compatible model endpoint support, including another offline loopback server.
- [x] Optional HTTPS remote provider mode with hostname approval and API key supplied via an environment variable.
- [x] Text and JSON tool-call parsing, registered-tool routing and rejection of unknown tool names.
- [x] Optional structured reply with avatar shape, emotion values and custom pixel grid; avatar metadata is excluded from spoken reply text.
- [x] Terminal interaction and a daemon mode that remains alive under systemd.
- [x] Hardware/CPU/RAM/disk/battery statistics, NVIDIA query adapter and process listing.
- [x] PipeWire `wpctl` volume/mute and `brightnessctl` brightness adapters.
- [x] Command assessment, subprocess timeouts, captured results and `shell=False` execution.
- [x] Risky command consent and process-termination consent. Model-supplied `approve=true` cannot approve its own request through the router.
- [x] Background/noninteractive consent requests are denied instead of waiting on nonexistent terminal input.
- [ ] Complete autonomous planning loop with multiple tool steps, result-grounded follow-up answers, retry policies and durable task recovery.
- [ ] Native conversation window and native system-action approval broker. Current conversational entry points are voice and the terminal.
- [ ] Native adapters for every provider's proprietary protocol. Present remote support assumes an OpenAI-compatible chat-completions schema.
- [ ] Hard enforcement of an 8 GB VRAM ceiling, GPU admission control, adaptive model unloading and model performance benchmarks.

## Voice And Listening

- [x] Local PipeWire microphone capture with openWakeWord gating.
- [x] Explicit listening and wake-word switches; microphone stays off until both are enabled.
- [x] Fixed-duration command recording and local Whisper.cpp transcription adapter.
- [x] Temporary command WAV deletion after transcription.
- [x] Piper speech queue with sentence splitting and priority bridge messages; PipeWire playback adapter.
- [x] Speech activity drives the companion and carries model-generated form metadata into playback.
- [x] Wake detection is suppressed while the speech queue is speaking; recorder frames continue to be consumed in that period.
- [x] Native controls for voice/model paths, wake threshold and recording duration; service start/restart/stop buttons.
- [ ] Verified microphone selection, hotplug recovery, user-calibrated voice activity detection and noise suppression on the laptop.
- [ ] Full acoustic echo cancellation, reliable interruption/barge-in, streaming transcription and streaming speech.
- [ ] Voice/model download manager and all wake/embedding model assets pre-provisioned for first-run offline use.
- [ ] Speech backend supervision and support for all Piper voice sample rates; the current playback path assumes 22050 Hz.
- [ ] End-to-end Arch audio validation with the installed Ollama, Whisper and Piper models.

## Memory And Personalization

- [x] Local habits JSON with permanent defaults and temporary overrides that expire.
- [x] Slang/jargon replacement dictionary and protected-term handling.
- [x] Local event log and recent-event text search.
- [x] Optional ChromaDB store/search helper functions and persistent local collection path.
- [ ] Automatic retrieval of relevant memories into every model request. The helper tools exist; full conversational memory is not connected.
- [ ] Curated import/export, retention/deletion UI, sensitive-data filtering and memory conflict resolution.
- [ ] Self-training or local model fine-tuning. Saving facts and preferences does not modify model weights.
- [ ] Offline provisioning/verification of Chroma's embedding model and full semantic-memory integration tests.

## Security And System Integration

- [x] Python venv installation; no global pip package modifications.
- [x] Native confirmation for protected settings, including disabling the confirmation guard itself.
- [x] AppArmor and systemd hardening templates, firewall baseline script and ClamAV scanner adapter.
- [x] Protected `/etc`, `/boot`, `/usr` writes in the supplied AppArmor policy.
- [x] No model-executed avatar code, no rendering URLs or scripts, and no browser-based settings server.
- [ ] Independent OS-level trust separation between daemon, settings, consent and user files. A settings dialog under the same Linux account is not a full security boundary.
- [ ] Exhaustive safe-command policy. The current read-command allowlist is broad and needs argument-level restrictions before unattended unrestricted tools are trusted.
- [ ] Network-wide domain-only egress enforcement. The current UFW baseline permits outbound DNS, HTTP and HTTPS generally; the Python provider broker enforces its own hostname policy.
- [ ] Audited AppArmor enforcement on the actual Arch install, seccomp policy, dedicated service identity and secure secrets storage.
- [ ] Verified `noexec` mount policy for temporary/cache directories; a script/template alone does not establish this.
- [ ] Automatic ClamAV scanning of every incoming/removable-media file.

## Hardware, Desktop And Branding

- [x] Hardware snapshot comparison, polling monitor and optional block-device udev event monitor.
- [x] Cooperative background job registry with pause/cancel state; it is a library rather than a full daemon scheduler.
- [x] Phase-gated Hyprland window listing and a separate typing adapter; typing is not exposed as a registered daemon tool.
- [x] Super-key bindings for native Settings/companion, launcher, terminal, file manager, AI service control, volume, brightness and locking.
- [x] Original REGENOS logo, wallpapers, lock-screen art, companion concept atlas and Plymouth theme sources.
- [x] Explicit user appearance application: GTK icon/cursor/font preferences plus Hyprpaper/Hyprlock config, with backups of pre-existing files.
- [x] Written boot-splash, desktop, logo installation and branding commands.
- [ ] Hardware events automatically routed into conversations/speech and jobs automatically scheduled by the AI.
- [ ] Compositor-wide autonomous window manipulation, arbitrary UI navigation and completed vision pipeline. OpenCV is only an optional dependency.
- [ ] Full OS theme engine across Qt, GTK, bootloader, display manager, application icons and all desktop components.
- [ ] Firmware-logo replacement. Plymouth only covers the later Linux boot stage.
- [ ] Portable multi-machine driver handling, suspend/resume verification and NVIDIA/audio/display regression testing.

## Packaging And Validation

- [x] Repository installer/config/branding/docs layout and staged Arch setup scripts.
- [x] Separate native-UI installation stage that does not require Hyprland.
- [x] Archiso package additions and branded-live-image instructions.
- [x] Calamares integration plan and references.
- [x] Automated Python/Qt checks for config changes, native UI persistence/visibility, state parsing, pixel validation/motion, tool consent and speech activity; offscreen window screenshots at desktop and compact sizes.
- [ ] Finished graphical disk installer, complete Calamares modules/branding/launcher and reproducible signed package source.
- [ ] Reproducible release ISO, verified installed target system, Secure Boot policy, upgrades, rollback and recovery media.
- [ ] Partitioning/encryption/bootloader failure-path testing in disposable VMs and spare drives.
- [ ] End-to-end production readiness. Do not interpret implemented components as a fully validated autonomous OS.
