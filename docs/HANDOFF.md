# REgenOS handoff — 2026-09-27

## Native interaction and voice identity — 2026-10-19

Latest evidence supersedes older executor restrictions below: **540 tests pass**,
correctness Ruff passes. The private PTY helper now establishes its terminal in a fresh process, avoiding
forkpty in the Qt-threaded test runner. See [research/chat/cleanup](RESEARCH_AND_CLEANUP.md)
and [voice identity/voice choices](VOICE_IDENTITY_AND_VOICES.md) for controls/limits.

- Added reviewed interactive terminal jobs (1–900s), ordinary command cancellation
  cleanup, public per-request activity, compact chat with Enter/Shift+Enter/Ctrl+Enter
  and stale callback guards. Disk/boot/shell/script/OS restrictions remain.
- Native speaker wizard records four explicitly requested styles plus a fresh fifth
  check, saves only a private embedding, and requires a separate filtering opt-in.
  Per-utterance matching has a ten-second worker bound. Backend/model/profile are
  absent; physical recognition is pending. No audio samples/models were captured/downloaded.
- Added current-utterance en/hi metadata routing. Saved match mode after private
  backup `~/.ai_os/backups/pre-migration-pxk4b770`, preserving English fallback,
  listening off, speaker filter off and the already-supervised command mode. No grant
  was created. User explicitly approved restarting **only ai-os.service** to load code.
  Restart returned active; listening stayed off. No other service was changed.
- Added cited Wikipedia/Crossref topic briefs, private Markdown, saved-report reader,
  paragraph narration and local tool-free explanation. Full papers are not read;
  tests use synthetic API/audio. Live online/audible walkthrough remains pending.
- Added recoverable regular-file Trash previews, explicitly remembered directory/
  pattern/inode rules (30 days/20 uses) and revoke UI. No user files were trashed.
- Added speaking mouth cadence, shared native styling, collapsible chat options,
  unsaved/save feedback and bounded mood-to-tone guidance. Real local model answered
  the display question in first person without the canned disclaimer; when explicitly
  asked about consciousness it described feelings as simulated. Not evidence of
  consciousness, consistently better reasoning, or phoneme lip sync.
- Readiness now reaches PipeWire (unmuted), active core and Ollama. Synthetic
  Piper→Whisper English passed/en; Hindi detected hi but emitted Urdu-script errors.
  Combined synthesis/STT samples took 3.14/3.17s. Two synthetic model turns followed
  en/hi, with uneven Hindi fluency. Personal voice, real latency and hotplug pending.
- Editable metadata refreshed offline without dependencies; Chat/Research desktop
  launchers installed. GNOME cursor **64** now passes readback. Human visual size
  confirmation remains pending. No privileged packages, drivers or disk changes.

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q --tb=short
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests
git diff --check
bash -n scripts/install_native_desktop.sh
desktop-file-validate config/desktop/regenos-chat.desktop config/desktop/regenos-research.desktop
~/.ai_os/venv/bin/python -m ai_os.runtime_health
~/.ai_os/venv/bin/python -m pip install --dry-run --no-cache-dir 'sherpa-onnx>=1.12,<2'
~/.ai_os/venv/bin/python -m pip install --no-index --no-deps --no-build-isolation -e .
~/.ai_os/venv/bin/python -m ai_os.cursor_size --size 64
systemctl --user restart ai-os.service
systemctl --user is-active ai-os.service
```

The sherpa dry run resolved compatible 1.13.8/core wheels; it did not install them.
`pip check` still reports the pre-existing openwakeword→tflite-runtime dependency
gap; the selected RE/Whisper path is separate. Do not claim the venv is dependency-clean.
New bridge requests import current source. Reopen Settings/corner companion for
new controls/animation; neither app was silently closed. Preserve `:memory:.ses`.
Merged GitHub's two newer commits, including the Calamares skeleton, preserving
their source without resetting or claiming installer validation. The README voice
status conflict was resolved by retaining both per-machine provisioning and the
host's limited measured results. No ISO, VM install, physical
disk operation, release publication or signing was performed.

## Voice, reinforcement and device speech checkpoint — 2026-10-19

Resumed interrupted work and reviewed the resulting source before integration.
See [PERSONAL_INTERACTION](PERSONAL_INTERACTION.md) for current behavior/limits.
User language was saved as Hindi; saved English, ending silence 5 seconds,
maximum utterance 120 seconds and desired cursor 64 after private backup
`~/.ai_os/backups/pre-migration-7ju7empq`. Listening remains off, command access
remains restricted, existing memory/device-speech opt-ins preserved. No model
download, package change, service restart, or physical disk operation.

Implemented distinct initial-wait/silence/utterance budgets, rejection of partial
requests at the hard maximum, trimming trailing silence before Whisper, post-reply
feedback suppression, and native voice-request timeout including the recording
budget. Saved language/current-turn guidance overrides old-history language;
synthetic resident and one-shot tests follow current transcript to its own reply.
Queued legacy speech now counts as busy before it plays and is discarded on stop.
Participating resident/native/device/proactive outputs share a nonblocking flock
lease. Five-second silence is intentional waiting; speculative inference while
speaking, real latency and acoustic echo cancellation remain unverified/pending.

Hardware monitoring now delegates to `hardware_reactions.py`: baseline before
hotplug, periodic DRM retries, up to 8 queued reactions with 60-second expiry,
fresh opt-in/language checks and no overwriting newer activity on cleanup.
Localized USB categories and new/familiar/4K monitor capability reactions are
fixed factual presentation, not model commands. Memory expiry is purged before
reinforcement; old hits cannot revive after a 180-day gap. Preferences/notes remain
explicit durable important facts; semantic paraphrase consolidation is pending.

Commands/results:

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q \
  tests/test_voice_endpointing.py tests/test_voice_reply_grounding.py tests/test_voice_settings.py \
  tests/test_memory_decay.py tests/test_hardware_reactions.py tests/test_speech_lease.py \
  tests/test_personal_interaction.py tests/test_listener.py tests/test_voice_languages.py \
  tests/test_settings_recovery.py tests/test_access_grants.py tests/test_desktop_context.py
# 134 passed; all audio, monitor and conversational evidence synthetic
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q --tb=line
# 350 passed, 1 failed, 7 errors: existing denied QLocalServer/screen sockets
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests
git diff --check
~/.ai_os/venv/bin/python -m ai_os.runtime_health
~/.ai_os/venv/bin/python -m ai_os.cursor_size --size 64
```

Readiness finds recorder/Whisper/Piper/assets, but PipeWire, Ollama and user-service
bus are inaccessible from this executor; nvidia-smi cannot access the driver.
This does not establish that host services/drivers are broken. No live microphone,
playback or model request was run. Cursor application failed verified readback:
live GNOME remains 48, desired preference 64. Native GNOME application and full
host suite must run outside this restricted executor. Current hardware watcher
source needs the resident core to reload; service restart requires approval per
user handoff. No new commit/push/publication; prior staged changes/private data
and unrelated `:memory:.ses` preserved. No ISO/VM work attempted.

## Visible full access and avatar recovery controls — 2026-10-17

Found a layout defect: adding buttons to the page after creating a form places
them after the *entire* form, even when the addWidget call appears near its first
field. The unhide/quit controls were below the long Companion preferences.
**Unhide avatar** now stays in the dashboard header; **Unhide / start avatar**
and Quit are at the top of Companion. Command mode, Enable/Revoke full access and
status are at the top of Permissions. Rendered and inspected both pages offscreen
at the minimum 780×570 size using temporary default settings.

Fixed PySide6 startDetached tuple handling (a `(False, pid)` tuple is truthy),
and propagate the selected `AI_OS_HOME` into companion startup. Existing-resident
activation now reveals/repositions the overlay if its persistent preference is
enabled; no-flag startup continues to honor hidden preferences. Full-access
duration/consent cancellation preserves settings and unsaved edits. Persisting
the mode precedes request creation because saving it revokes old pending grants.
Native confirmation remains mandatory; database/confirmation/revocation errors
are reported, and grant status refreshes every second. No live user grant enabled.

Validation (all test state temporary):

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_settings_recovery.py tests/test_access_grants.py
# 57 passed, including 10 new recovery checks
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_native_ui.py tests/test_avatar_displays.py -k 'not single_instance'
# 13 passed, 1 deselected; actual local-socket operation remains restricted here
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/native_settings.py ai_os/avatar_overlay.py tests/test_settings_recovery.py
git diff --check
```

The existing venv resolves both modules to this checkout. Actual saved avatar
visibility is true. A bounded installed `python -m ai_os.avatar_overlay --show`
attempt exited -6: Qt cannot connect to the graphical display in this executor.
Physical avatar visibility and GNOME window activation are therefore pending.
No service was changed/restarted. A running old dashboard retains old code:
fully close it (handle unsaved edits), then launch `~/.ai_os/venv/bin/regenos-settings`.
The app-menu Companion entry or `~/.ai_os/venv/bin/python -m ai_os.avatar_overlay --show`
is the recovery command from the real desktop terminal. Source/docs changes and
the new test file are uncommitted; prior staging and unrelated files preserved.

## Recovery controls and Permissions full access — 2026-10-17

Native Settings now has an explicit **Show / start companion now** action, which
sets saved avatar visibility and starts the companion with `--show`; saved
visibility can still be toggled separately. The application-menu Companion
launcher also passes `--show`. The user's REgenOS Dashboard and REgenOS Companion
desktop entries exist in `~/.local/share/applications`; `gio` previously
reported them registered and visible to the app registry, but actual GNOME
Show Apps search/display is not observable from this restricted session. Direct
recovery command: `~/.ai_os/venv/bin/python -m ai_os.avatar_overlay --show`.

Permissions now labels **Full access mode — time-limited ordinary user commands**
and exposes **Enable full access mode…**, a duration and scope confirmation, a
live status label and **Revoke full access**. Mode selection alone does not grant
access; an explicit native human confirmation is still required. The grant is
for the default/voice session and ordinary account-level commands under the
existing Bubblewrap boundary. It does not grant root, and privilege, physical
disk, mount, boot and security operations remain separately blocked/reviewed.
Enabling without Bubblewrap fails closed. Added a check that the saved mode is
actually enabled before granting; unsaved dropdown changes cannot silently arm
the mode. Updated `docs/NATIVE_DESKTOP.md` and `docs/COMMAND_ACCESS.md` to match.

Ruff correctness checks (`~/.ai_os/venv/bin/python -m ruff check --select
E4,E7,E9,F ai_os/native_settings.py`) and `git diff --check` pass after these
changes. Native graphical display is unavailable in this execution session
(`DISPLAY=:0` cannot connect and Wayland display access is denied), so the
actual dashboard, app-grid search and avatar visibility on the physical desktop
remain unverified. The resident process must reload the updated source to show
the new button; reopen the dashboard from Show Apps, or use the recovery command
above from a desktop terminal. Existing unrelated staged changes and untracked
`:memory:.ses` were preserved; no privileged operations, commit or push were
performed for this UI follow-up.

## Explicit website and app launch — 2026-10-17

Found the old path opened Brave deterministically but sent website requests such
as “Open YouTube” only to the model; the model had to select `open_website`
correctly. Added bounded direct intent parsing for common open/visit/go-to
phrases, known sites and explicit hostnames. “Open YouTube on Brave” routes to
the named installed browser. Browser discovery checks system, user-local and
Flatpak desktop entries from a fixed allowlist. General app discovery now scans
those standard app directories and launch still requires an exact discovered
desktop ID or a built-in alias. Native chat now renders tool result messages
instead of dumping JSON.

Focused `tests/test_desktop_access.py` and `tests/test_interaction_harness.py`
cover intent routing, URL safety, browser selection, app scanning and native tool
flow; 40 focused tests pass. Commands:

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_desktop_access.py tests/test_interaction_harness.py
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q --tb=line
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests/test_desktop_access.py tests/test_interaction_harness.py
git diff --check
```

The actual environment's
`gio mime x-scheme-handler/https` selects Brave, and the installed desktop entry
and `/usr/bin/brave` exist. A requested Gio YouTube launch returned success, but
no Brave process was visible afterward. Direct `/usr/bin/brave URL` exited with
code -5 and the sanitized diagnostic `crashpad setsockopt: Operation not
permitted`, consistent with this executor's GUI/process restrictions. Therefore
the physical browser window/page remains **not hardware-verified**; Gio's success
is only acceptance of the launch request. The full suite reports 284 passed, 1
failed and 7 errors: the existing local-socket limitation (`QLocalServer` and
screen-context socket unavailable). No service or system settings changed.

## Hidden avatar and Show Apps — 2026-10-17

Confirmed saved `avatar_enabled=false`; backed up private runtime/launchers to
`~/.ai_os/backups/pre-migration-nkb1_0m1` and changed only avatar visibility to true.
A running companion should refresh that flag without restarting. No desktop
visibility is claimed from the sandbox. The existing settings launcher was valid;
its app-grid absence was not reproduced. Updated its searchable name to
**REgenOS Dashboard**, added AI/assistant/dashboard keywords and refreshed the
user desktop database. Gio registration reports both REgenOS launchers present
and `should_show=true`; real GNOME search/grid remains physically unverified.

The companion application-menu entry now passes `--show`; that flag restores
visibility before the single-instance check, including an older hidden resident.
Ordinary no-flag session startup preserves the saved hidden preference. Native
installer retains `--show` when writing the absolute Exec path. Only the two user
application launchers were updated; no session installer, packages, services,
autostart configuration or boot settings were changed. Launcher originals were
preserved in the private backup. Full suite: 275 passed, 1 failed, 7 errors (same
socket restrictions); lint, desktop-file validation and shell syntax pass.

## Companion close control — 2026-10-17

Added Quit companion to the dashboard and avatar menu; application exit now also
cleans up overlay speech. Standalone human CLI:
`~/.ai_os/venv/bin/python -m ai_os.companion_control` gracefully terminates only
same-user companion module/script entry points and waits up to three seconds.
No forced kill or core/microphone termination. This is not registered as a model
tool. The actual stop attempt found no companion visible in the sandbox's isolated
process namespace, so **the host companion was not closed**. Run the command from
the desktop terminal to close the old process without needing a GUI connection.
22 focused control/overlay/backend tests pass; lint/diff checks pass. New dashboard
controls require the settings process to reload; the CLI works independently of Qt.

## Avatar transfer repair — 2026-10-17

Dragging was clamped to `self.screen().availableGeometry()`, trapping the avatar
on its original monitor. Dragging now uses Qt's screen under the global pointer,
clamps to that destination's available rectangle and saves `avatar_display` by
Qt screen name on release. Negative monitor origins work in synthetic tests.
Right-click **Move to display** enumerates current displays; native Companion
settings also have a Display selector. Geometry/hotplug callbacks include newly
added displays; an unavailable saved target falls back to an available display
and can be restored when reconnected. No screen content is captured for placement.

New tests cover cross-boundary drag, release persistence, menu selection,
disconnection and reconnection with synthetic displays. Full suite: 274 passed,
1 failed, 7 errors (same denied local sockets); correctness lint and diff checks
pass. The actual two-monitor desktop is **not hardware-verified** and no running
companion/service was restarted. Resident Python code must be reloaded before
these controls are available. Existing GNOME XWayland placement path is retained;
this is not a native Wayland compositor-control implementation. Git author/network
blockers remain; changes are staged, not committed or pushed.

## Publication and cursor follow-up — 2026-10-17

User requested commit/push and comparison with a newly added startup skeleton.
`gh auth status`, `gh repo view Aryan1771/ai-os --json defaultBranchRef,nameWithOwner`
and `gh api repos/Aryan1771/ai-os/commits` could not reach GitHub. Auth status also
reported invalid authentication, but token validity cannot be established while
API connectivity fails. Do not log out, replace credentials or infer remote state.
Local Git author name/email remain unset; the intended repository-local identity
has been requested. No commit/push or remote merge occurred. Cached main remains
82de882; the only tracked startup artwork found locally is the existing Plymouth
theme plus Archiso/Calamares documentation. New remote skeleton is **not verified**.
No boot, initramfs or installer activation was performed.

DRM capabilities show two 1920x1080 displays (not proof of active mode or DPI).
The saved 48-pixel preference is a reasonable initial target, adjustable natively.
New `python -m ai_os.cursor_size --size 48` changes only GNOME pointer size,
backs up its original value, verifies readback and saves the preference only on
success. Native Appearance has the corresponding cursor-only button. The actual
attempt was rejected by session restrictions: verified readback remains **32**.
Use that command in the real desktop terminal; original-size rollback is 32.

33 focused cursor/backend/memory tests pass. Full suite: 272 passed, 1 failed,
7 errors, all unsuccessful checks requiring denied local sockets. Correctness
lint and whitespace checks pass. Changes remain staged, unrelated :memory:.ses
is untouched, and no private runtime files were staged.

## Command traversal and voice diagnostics — 2026-10-17

See [COMMAND_ACCESS](COMMAND_ACCESS.md#2026-10-17-command-and-voice-error-repair).
New bounded directory metadata, home/cwd normalization, read-only system-directory
cwd for broad grants, bounded-output/group-cleanup runner, and sanitized stage-specific
voice errors are source-tested. 108 focused tests pass; full suite 270 passed,
1 failed, 7 errors (local socket restrictions). Harmless Bubblewrap `pwd` from
`/usr` succeeded. No command mode/grant was enabled and no service restarted.
User's exact post-transcription error is still requested; status was armed with
no recorded error when inspected. Do not call that reported failure fixed.

## Personal interaction follow-up — 2026-10-16

See [PERSONAL_INTERACTION](PERSONAL_INTERACTION.md) for the latest source changes,
exact tests, saved preferences, rollback and unresolved live acceptance. Language
selection now controls STT and reply prompt; one-shot capture ends on silence and
shows recognized text; voice synthesis works sentence by sentence. Optional bounded
reinforcement memory and spoken monitor/USB reactions are implemented. Cursor
preferences default to 48 with a native size control. **Live GNOME remains 32**:
dconf rejected the set attempt; do not claim the cursor is visibly changed.

The user-requested English/48-pixel/reinforcement/hardware-speech preferences were
saved after private backup; listening, provider and access policy were preserved.
No service was restarted, so source changes may not be loaded in resident workers.
104 focused regressions and correctness lint pass. Full host/native/audio/hotplug
acceptance remains pending. Commit identity and remote access blockers remain.

## Latest interaction checkpoint

The interrupted October runtime work has been continued without resetting local
edits. See [INTERACTION_HARNESS](INTERACTION_HARNESS.md) and the current
[ARCH_ACCEPTANCE](ARCH_ACCEPTANCE.md) before relying on the historical results below.
New source provides native tool schemas/discovery, at most three tool steps with
result-grounded follow-up and duplicate prevention, personality controls, optional
GNOME AT-SPI text context, and separate opt-in app-name/time memory. Voice workers
reload settings, bound stalled reads, report invalid activation choices, and own
their temporary audio. Website opening, installed-app discovery and hardware
notifications are connected. No model was replaced/downloaded and no runtime
settings, packages, services, boot or physical disks were changed in this checkpoint.
New privacy features and broad command grants remain off until explicitly enabled.

Source/docs/tests are staged on `main` above baseline `82de882`. Commit failed
because Git author name/email are unset; the user has been asked for the intended
repository-local identity. Remote access failed DNS resolution, so nothing was
pushed or published. Leave unrelated untracked `:memory:.ses` untouched.

This execution environment cannot reach host Ollama, bind local sockets or control
the desktop service bus. Full-suite IPC failures therefore remain unresolved host
acceptance checks, not passes. Git network access is also unavailable. Finish the
host-side full suite and approved native/voice checks before ISO work.

Preserve exact **REgenOS** capitalization. This is an offline-first native desktop
and Arch runtime prototype, not a finished distribution. Start with
[RUNTIME_VALIDATION](RUNTIME_VALIDATION.md) for commands, measurements, rollback
and limitations, and [IMPLEMENTATION_CHECKLIST](IMPLEMENTATION_CHECKLIST.md) for
the dependency-ordered audit of all 100 feature checkboxes (33 unchecked).

## Documentation review — 2026-10-08

The root README now links directly to setup and feature guides, identifies the
Python Settings path as supported, and aligns its voice-status summary with this
handoff. Documentation checks do not constitute new hardware, audio, or runtime
validation. Historical commands and measurements below are preserved.

## Actual installation versus source

- 2026-09-28 continuous screen follow-up: native Qt Multimedia portal capture,
  local English OCR, expiring in-memory context, read-only screen questions and
  optional screen comments implemented. GNOME lock checks fail closed; screen
  data never enters tools, conversation memory or remote providers. New settings
  enabled for this user after explicit request and backup `pre-migration-7cf28wkw`;
  speech/microphone settings preserved. Approved Tesseract/English packages and
  matching venv Qt Addons installed. See [SCREEN_AWARENESS](SCREEN_AWARENESS.md)
  for controls, limits and current validation. No general image/video understanding.
  **225 tests passed**, correctness lint/native smoke and synthetic OCR → Ollama
  passed. Live GNOME capture produced 2574 fresh text characters without logging
  content; sharing subsequently switched off and was left paused. Live commentary,
  spoken comments and manual lock/login continuity remain pending. Restart preserves
  permission; manually closing the reader disables it. Current screen reading is off.
- 2026-09-28 companion automation: independent debug emotion/mood toggles (hidden
  in current runtime); microphone/grant/speaking indicators stay visible. Dragging,
  pointer avoidance and optional local screen-texture corner selection implemented.
  Screen capture remains off and unverified live. Optional local proactive check-ins
  and emotion-dependent speech pace added; proactive speech remains off.
- Reviewed Bash draft/syntax tools and separate-profile browser research/ChatGPT
  actions added. Browser tools remain off until enabled in native Permissions;
  exact prompts/URLs require individual native review. Playwright 1.63.0 installed
  in existing venv; existing sandboxed Brave used. GNU manual returned HTTP 429;
  Arch Bash manual read succeeded (20000 chars). No authenticated ChatGPT send or
  personal-profile access. **209 tests passed**, correctness lint/native smoke pass.
  Core and companion restarted; private runtime backup `pre-migration-5cx07bl6`.
  See [COMPANION_AUTOMATION](COMPANION_AUTOMATION.md) for controls and limits.
- 2026-09-28 RE/session checkpoint: assistant named RE (spoken R E); user login
  startup installed for core and companion with graphical environment import.
  Core active/enabled, one companion process. GNOME kept as requested; original
  Cool cursor remains selected. Installed Hyprland 0.56.2 requires Lua; new
  integration and combined user config pass its parser. AI window tools enabled,
  actual Hyprland-session control pending. **193 tests passed**, lint clean under
  correctness rules; native XWayland/local Ollama smoke passed.
- Local experimental Whisper RE detector is selected; both listening switches
  remain off. Synthetic Piper → Whisper returned `RE.` and matched; real wake
  accuracy/false activations are pending. `find_commands` falls back to installed
  manual names because the host apropos index is empty (network finds 33 topics).
- User wants face/voice to replace normal password prompts after enrollment.
  Neither unlock feature is implemented; hub reports unavailable. No camera
  capture, enrollment, PAM edits or password changes. See
  [RE_SESSION_AND_IDENTITY](RE_SESSION_AND_IDENTITY.md) for exact commands,
  backups, limitations and remaining authentication/boot work.
- User approved the exact system-identity installer (os-release, two logos, TTY
  banner). `sudo -n` required a password; native pkexec authentication timed out
  after 60s. Verified OS identity remains Arch. Run the already approved
  `sudo /usr/bin/python scripts/apply_system_identity.py --apply` locally, then
  verify and record its backup. No repeat permission request for this operation.
- 2026-09-28 access-grant follow-up: exact pending-command and timed session
  grants are implemented with trusted terminal/native confirmation, expiry,
  countdown and revocation. Seconds/minutes/hours, up to 24 hours; timed scope
  is limited to diagnostics and new-file mkdir/touch/cp in approved directories.
  Voice requests remain pending until native review; models cannot confirm.
  See [COMMAND_ACCESS](COMMAND_ACCESS.md) for usage and security limits.
  **173 tests passed**, correctness lint passed. No real user grant was activated
  and no microphone listening was enabled. Native smoke result is recorded in
  [RUNTIME_VALIDATION](RUNTIME_VALIDATION.md).
- 2026-09-28: see [COMMAND_ACCESS](COMMAND_ACCESS.md) for new direct app launching,
  supervised native command approval, installed man-page help, explicit official
  manual caching and warmer emotion-aware replies. Full command access defaults
  to restricted; no sudo/root policy was changed. Background voice still fails
  closed on command approval. Pacman manual cached; greeting tested on real Ollama.
  **135 tests passed**, correctness lint passed, real native smoke passed. Brave
  launch accepted after fixing inherited-output-pipe timeout; window placement
  is not automatically verified. See runtime notes for exact commands.
- Custom cursor and original wallpaper applied to GNOME with appearance backups.
  System identity, boot splash and login branding remain pending privileged review.
  User confirmed the previous live English voice reply was audible/relevant.
- Latest user-requested live English check completed microphone → Whisper →
  local Ollama → Piper/PipeWire reply with temporary memory disabled and no tools.
  Eight-second capture; STT 0.88s, model 4.47s, synthesis/playback 6.58s. Recording
  was deleted; continuous listening stayed off. User confirmed earlier synthetic
  English/Hindi playback was audible; this latest reply awaits user confirmation.
  `pw-record --sample-count 128000` returned 1 with empty stderr despite a complete
  128000-frame WAV. First attempt stopped on that code; retry validated audio and
  completed. Signal reached full scale; input gain/clipping requires follow-up.
- Latest voice audit: all packages listed in PREINSTALL's immediate/optional
  commands and win2xcur are installed. **122 tests passed, none skipped**.
  Multilingual Whisper base, English Lessac and Hindi Pratham model SHA256 values
  match publisher metadata. Both voice JSON files and Jarvis ONNX exist.
- Corrected saved `whisper_model` from absent `models/ggml-base.en.bin` to
  `models/ggml-base.bin`, after private runtime backup. Listening/wake/speech
  remain false; daemon inactive, clean exit. No microphone capture was performed.
- Synthetic English round-trip passed. Hindi synthesis works, but base Whisper
  returned Urdu-script text with `-l hi`; Hindi recognition quality is pending.
  Both voices passed the real speech adapter/PipeWire playback command (4.50/4.56s);
  human audibility/quality confirmation is still needed. Jarvis ONNX loads and
  rejects one silence frame; this does not validate real wake-word detection.
- `pip check` still reports missing tflite-runtime, while the selected ONNX path
  passes. Existing five-second microphone WAV was inspected only for metadata.
  Untracked `:memory:.ses` was preserved and excluded from commits.

### Earlier dependency and GPU checkpoint

- Resume validation supersedes the earlier machine snapshot below: running kernel
  `7.2.7-arch1-1`, NVIDIA module/userspace `615.71.09`, RTX 4060 Laptop with
  8188 MiB VRAM. Driver access works outside the tool sandbox. The user daemon,
  PipeWire and WirePlumber are active; this resume did not start/restart them.
- GPU inference verified after user installed `ollama-cuda 0.34.4-1` and restarted
  Ollama: model `size_vram=size=4748056984` bytes at 4096 context. Two synthetic
  requests took 5.487/0.405 seconds; 34 device samples peaked at 4662 MiB, no
  sampling errors. This is a small-workload sampled peak, not a hard VRAM cap.
- Missing package/asset inventory and scoped installation commands are in
  [PREINSTALL](PREINSTALL.md). No packages were installed by the audit.
  Venv `pip check` reports missing `tflite-runtime` for openWakeWord; ONNX Runtime
  is present, but wake models/readiness remain unverified. Listening stays off.
- Resume checks: **121 passed, 1 skipped**, correctness lint passed. The sandbox
  denied one Qt local-socket test; the outside-sandbox suite passed. Real native
  smoke passed with nine pages, visible companion and completed synthetic chat.
- Fixed implicit memory retention: inspection, context retrieval and append now
  use saved retention when callers omit it, rather than silently pruning at 30 days.
  Six regressions cover 7/90-day policies across those access paths.

### Earlier checkpoint snapshot (historical)

- Started at `640183c`; earlier uncommitted repair work was preserved.
- User confirmed Phase 1 used **Ollama CLI directly**. That bypasses REgenOS tools,
  memory and UI. Voice files are intentionally deferred until the structure is ready.
- Existing `~/.ai_os/venv` imports editable source from `~/src/ai-os`, including when
  invoked outside the checkout. Python 3.14.7. No clean reinstall.
- Old package metadata lacked launchers; refreshed only editable project metadata
  with `pip install --no-deps --no-build-isolation -e .`. Both desktop launchers
  now exist. PySide6 was added to this same venv in the first repair checkpoint.
- Old runtime config/working preferences preserved. Private backup:
  `~/.ai_os/backups/pre-migration-7n_o9uf6`. No preexisting conversation database.
  Synthetic acceptance-test conversations stayed in temporary runtimes.
- Installed user daemon points at the correct source/venv, remains inactive, and
  was not enabled. Earlier lifecycle check passed. It lacks the tracked template's
  AppArmorProfile/EnvironmentFile; no security policy or unit was replaced.
- GNOME Wayland/XWayland; PipeWire/WirePlumber active. Raw capture and synthetic
  playback transport passed. Whisper CLI/models and Piper voices absent at configured
  paths. Listening remains disabled. Recognition/synthesis/audible latency untested.
- Running standard Arch kernel 7.1.11; installed standard/Zen kernels 7.2.7.
  NVIDIA module 610.57.04 versus NVML 615.71; `nvidia-smi` fails. Matching new DKMS
  modules exist for installed kernels. Reboot/boot/package changes need approval.
- Existing Qwen 7B Q4 model preserved. CPU requests verified; no GPU peak or enforced
  8 GB guarantee. Internal Windows disk untouched. No model downloads.

## Implemented and tested this checkpoint

- Python/PySide6 Settings and Companion launchers; historical C++ hub retained but
  no longer required. Nine Python pages include conversation, memory and hardware.
- Bounded native chat child, selected session forwarding, cancellation/cleanup.
- Persistent recent sessions, relevant lexical notes/older turns, explicit preferences,
  CLI/native inspect/forget/clear, private schema backups, remote-memory opt-in,
  obvious-secret heuristic and revision protection against late writes after forgetting.
- Removed automatic model write tools for habits/events/semantic memory. Legacy
  stores are preserved separately; new forgetting controls do not erase those or backups.
- Shorter protocol prompt: uncached processing 6.912 → 4.510 seconds in small CPU
  samples. Cold load variable (5.8–9.4 seconds); warm final probe 1.901 seconds total.
  No saved context/model setting changed. Exact tokenizer budgeting remains pending.
- Hindi/English recognition selection, explicit Hindi Piper voice route, danda
  sentence splitting. Unit-tested only; no claim of bilingual speech quality.
- Recorder stop reaps its subprocess. Voice transcripts no longer printed to logs.
- **108 Python tests passed, 1 cursor-conversion test skipped.** Correctness lint
  passes; 17 older default-Ruff findings remain. Real native chat completed in XWayland.
  Real Ollama recalled a fictional codename across fresh processes, then did not
  repeat it after forgetting. User-data acceptance still requires actual use.

## Next actions

1. Use `~/.ai_os/venv/bin/regenos-settings` or
   `~/.ai_os/venv/bin/python -m ai_os.ai_os_core --session personal`, not bare Ollama
   CLI, to exercise connected memory/tools. Report any real conversation failures.
2. GPU smoke now passes. Next validate connected REgenOS requests and longer
   contexts under realistic load; sampled usage does not enforce a VRAM ceiling.
3. Voice assets are installed. Improve/validate Hindi recognition, confirm audible
   output, then explicitly opt into real microphone/wake-word end-to-end testing.
4. Finish tokenizer-aware limits, robust request ordering, streaming/tool-result loop,
   speech cancellation/stall recovery and actual bilingual acceptance.
5. Follow the audit dependency order for trusted native approvals/security, desktop,
   branding and VM-only ISO/Calamares work. Do not mark unchecked items complete
   from source existence alone. Emotions are simulated; memory is not model training.
