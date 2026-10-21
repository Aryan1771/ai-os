# REgenOS handoff — 2026-10-21

Baseline `fd0f67f` on `main`; intentional runtime/source work follows.

## 2026-10-21 current runtime acceptance

After final frozen automated checks (**1290 passed in 16.64s**, normal exit;
correctness lint/whitespace clean), `scripts/verify_native_runtime.py` passed:
nine Settings pages, xcb, visible temporary companion and completed local Ollama
reply. It used temporary settings/history with speech/listening off. No personal
microphone, screen capture, saved preference or private conversation was used.

The owner then explicitly approved restarting only `ai-os.service` for the new
input-routing, deadline and command-bootstrap fixes. Approved restart/fresh
readback passed: active/running, ExecMainStatus 0, NRestarts 0, configuration bytes
unchanged. Listening, wake activation and speaker filtering remain false; voice
readiness has no blockers. This supersedes earlier pending-reload wording below.
No other service changed. Readiness is not personal microphone/language acceptance.

Hosted CI for the Qt fixture repair `3132e4a` and artwork `7d5b138` completes
successfully, including normal Python exit. Boot artwork is prepared, not installed.
The owner confirms the compact login layout is usable and the password field is
unobstructed; other scale/display cases are untested. Owner English guided voice
remains **not accepted**: controls are now visible in the separately launched
diagnostic, but no correct-transcript/audible-reply result has been confirmed.
An accurately staged diagnostic UI/early recorder-close repair is in progress.
Hindi, concurrent VRAM, real grant/revoke,
context lock/revoke and monitor/hardware acceptance remain open. Recovery is not
boot-tested. No ISO build, VM installation, artifact signing or release occurred.

## 2026-10-21 checkpoint: staged UKI artwork

The boot renderer now has an opt-in `--boot-splash` mode producing only a
566×167, 24-bit uncompressed BMP and relative hash/version manifest from the
tracked outlined wordmark. It preserves the stock splash footprint, refuses
overwrite/symlink staging and excludes external references/fonts. The default
four PNG outputs remain. Twenty isolated-process tests pass; root's frozen full
suite is **1290 passed in 16.64s**, normal exit, with lint/whitespace clean.

Root generated a separate temporary review artifact, decoded it with Qt and
visually inspected a PNG preview. BMP bytes: 283954; SHA256
`a2cf1dde1ee1625fe8a12fe3dfee3b99ab80432a23e8138f982bd3ed4473b772`
under Qt/PySide6 6.11.2. This is an artwork hash, **not an ISO or UKI hash**.
No raster output was added to Git. See [UKI_SPLASH_PROPOSAL](UKI_SPLASH_PROPOSAL.md)
for the read-only preset/stock-BMP evidence and separately gated future recipe.
No host UKI build, boot copy, activation, reboot or recovery acceptance occurred.

## 2026-10-21 checkpoint: Qt enrollment-test ownership

The newly pushed audio tests exposed a native crash during later Settings event
processing, locally and in hosted CI. Two reduced two-test sequences reproduced
exit 135. Independent probing identified deferred deletion of a fake enrollment
metadata process after fixture teardown, with the same QApplication throughout.
Test-only owner cleanup now checks stopped timers, destroys the exact dialog
before its fake fixture ends, and verifies destruction of owner/child wrappers.
No production cleanup, skipped rendering or crash suppression was introduced.

Both reduced cases and 89 adjacent tests pass. Root's final frozen combined
source suite passes **1290 tests in 16.64s**, normal exit, including six pinned
Plymouth interpreter checks and the next boot-artwork checkpoint. Correctness
lint/whitespace pass. Hosted acceptance of this repair remains pending.
See [CI_VALIDATION](CI_VALIDATION.md) for failure and reproduction evidence.

## 2026-10-21 checkpoint: isolate the broad-command bootstrap

Audit reproduced a pre-Bubblewrap module-shadowing defect using metadata and a
fake runner: a selected cwd could provide an `ai_os` package before the trusted
helper resolved. Broad grants now start the existing venv with `-I -m`, excluding
cwd, interpreter environment and user-site lookup. Intended command/cwd/timeout
are preserved; a missing installed helper fails without ordinary fallback.

Root independently ran **79 command regressions in 0.90s**, including six new
confinement cases and real read-only import-origin/flag checks. Correctness lint
and whitespace checks pass. No payload, actual broad command/grant, Bubblewrap
namespace or host security policy change was used. The resident core still needs
a separately approved reload before relying on this repair there. Same-account
editable-code trust and real revoke/confinement acceptance remain open.
See [COMMAND_CONFINEMENT](COMMAND_CONFINEMENT.md).

## 2026-10-21 checkpoint: explicit microphone routing

Native Voice settings now has a protected input selector and explicit asynchronous
Refresh. Stable selected inputs are shared by continuous, one-shot/guided and
enrollment capture; missing inputs fail visibly without automatic fallback.
Enrollment's selected-input check remains cancellable and rechecks consent and
configuration before capture, with no second blocking scan on the GUI thread.
The default microphone path, 16 kHz mono and five-second ending pause remain.

Root independently verified **223 focused regressions in 1.70s** and correctness
lint after reviewing the final source. The new suite has 64 fake-only cases,
including pending-event-loop, cancel, target/configuration drift and failure
coverage. No actual capture, input inventory, personal setting, model, service or
system-audio change occurred. Resident core has not been restarted for this or
the deadline repair. See [AUDIO_INPUT_SELECTION](AUDIO_INPUT_SELECTION.md).
Calibration/noise/VAD and physical routing/reconnect acceptance remain open.

## 2026-10-21 checkpoint: owner UKI report and hosted results

The owner supplied the focused elevated read-only UKI report. The fixed known
file has Arch OS-family metadata, kernel version `7.2.10-arch1-1` matching the
running release, an embedded command line without quiet/splash/Plymouth-disable
flags, and a **378,226-byte `.splash` section**. Its pixels/rendering, the exact
booted disk-file identity, selected entry and independent recovery remain
unverified. No image extraction/rebuild, boot write, mount, package/service change
or reboot occurred. See [BOOT_RECOVERY_INVENTORY](BOOT_RECOVERY_INVENTORY.md).

Read-only GitHub checks confirm complete supported-version CI success for
`6a7f6ee`, `82e89b2` and `945f3fc`, including normal Python exit, historical C++
tests and installer syntax. [CI_VALIDATION](CI_VALIDATION.md) links each run.
This supersedes the pending-run wording in the earlier historical entries below;
the excluded 6.12 teardown interaction itself remains unresolved. No host package
changed, and these runs are not physical or ISO acceptance.

## 2026-10-21 checkpoint: planner dispatch deadline

The original 120-second planning deadline now reaches the initial model request
and is rechecked before preparation/POST and each new tool dispatch. Previously a
fake initial request taking 121 seconds could still start an action. Completed
results survive expiry with an explicit notice; no action is retried to recover.
Fractional remaining HTTP time is no longer extended to one second. Root's
independent focused suite passed **55 tests in 0.29s**; source/new-test lint and
whitespace checks pass. No command, inference, microphone or service operation
was used. Resident core has not been reloaded for this new repair.
See [PLANNER_DEADLINES](PLANNER_DEADLINES.md).

This bounds new dispatch, not an already running executor or native confirmation;
those keep their independent limits. It is not hard wall-clock cancellation,
durable planning or GPU-memory reservation. Those acceptance items remain open.

## 2026-10-21 checkpoint: opt-in UKI metadata inspection

The bounded helper's new `--uki` mode reads only the fixed known Arch UKI via
captured `bootctl kernel-inspect` and `.splash` section headers. It exports known
OS family, bounded version/match and presentation flags, never embedded root
arguments, IDs, raw command lines or image contents. Unknown/truncated formats
stay unknown. Default inventory reads remain unchanged; no extraction, objcopy,
rewrite or mount is used. Root independently verified **95 mocked tests in 0.06s**
and correctness lint. The owner's subsequent real inspection is recorded above.
See [BOOT_RECOVERY_INVENTORY](BOOT_RECOVERY_INVENTORY.md) for the owner command.

The owner's earlier full report remains useful current-stub evidence, not proof
of exact booted on-disk contents or independent recovery. Inspection approval
does not authorize rebuilding a UKI, installing Plymouth or writing boot settings.

## 2026-10-21 checkpoint: supported Qt dependency range

Two controlled hosted comparisons isolate a version-specific project shutdown
failure: Python 3.12 / PySide 6.11.2 completes all Python, historical C++ and shell
checks; 6.12.0 passes assertions then exits 139. No upstream defect or Python
lifetime cause is claimed. Both Essentials/Addons extras now use `>=6.8,<6.12`;
required CI selects 6.11.2 and retains faulthandler and real failure exits.
See [CI_VALIDATION](CI_VALIDATION.md) for run/job links and counts.

On resumption, the existing venv independently passed the 89 focused command/
research regressions in 1.02s. TOML/YAML and paired-bound checks pass. No package
or dependency changed on this host. The supported-only hosted rerun remains to
be verified after this checkpoint is pushed; the earlier 1150-test local source
run remains the full-suite evidence until new code is accepted.

## 2026-10-20 checkpoint: owner boot evidence and approved core reload

The owner ran the improved elevated read-only helper. It reports a current stub
at `/EFI/Linux/arch-linux.efi` and loader path `/boot/EFI/Linux/arch-linux.efi`;
the known on-disk UKI is a readable regular file, 154340352 bytes. The reported
loader product is GRUB, but the single parsed custom/unknown GRUB declaration
does not establish that this configuration controls the current boot. The known
fallback UKI and plain linux initramfs now explicitly report **not found**, not
permission denied. Zen's existing initramfs and both kernel files are readable;
their recovery bootability is untested. Only default presets are enabled.
The existing 1GiB vfat `/boot` has 712892416 bytes available at inspection time;
hooks contain no Plymouth. Current boot flags omit splash/quiet/BOOT_IMAGE.
No active-entry or independently bootable recovery claim follows.

The owner separately approved restarting only `ai-os.service` for the tested
listener repairs. Restart/fresh readback passed: active/running, exit status 0,
NRestarts 0; config bytes unchanged and continuous listening/wake/speaker filtering
all off. No other service changed; no microphone was enabled. The full 1150-test
source run preceded this installed check. Normal-login logo appearance and real
English/Hindi guided checks remain owner acceptance. No boot write/ISO/VM occurred.

## 2026-10-20 checkpoint: guided voice latency measurements

Guided checks now return separate numeric detection-wait, capture, ending-silence,
speaker-filter, STT, synthesis and playback measurements. Existing combined and
model counters remain. PCM durations overlap wall timings and must not be added
as extra delay. Only explicitly requested diagnostics use a temporary collector;
resident/default calls do not persist timings. Valid completed stages can be
displayed after failure without its transcript, backend output or private paths.
See [VOICE_STAGE_TIMINGS](VOICE_STAGE_TIMINGS.md).

Final frozen-source regression run: **1150 passed in 11.92s**, including the six
optional interpreter checks with the pinned external Plymouth subset. The focused
voice suite passes 119 tests (28 new); correctness Ruff, full new-file Ruff and
whitespace checks pass. No actual recording, model inference, audible playback,
saved setting or service change occurred for this checkpoint. Hindi accuracy and
real latency remain pending. This instruments latency; it does not claim a speedup.

Hosted Python 3.12 assertions now pass but Qt teardown still exits 139. A strict
6.11.2/6.12.0 CI-only comparison with faulthandler is in progress; no crash is
ignored and no production version pin was inferred. ISO release work remains
blocked on critical runtime/security and recovery acceptance.

## 2026-10-20 checkpoint: bounded boot/recovery inspection

The helper now separates permission-denied from missing files, literal enabled
presets from inactive image assignments, and static GRUB declarations/defaults
from current-boot evidence. Fixed-path image type/size and mount-space metadata
omit identifiers; optional current-stub evidence is explicitly firmware-reported,
not a verified disk/recovery identity. No configuration is sourced or executed.
Root independent run: **60 mocked tests passed in 0.05s**, correctness lint clean.
See [BOOT_RECOVERY_INVENTORY](BOOT_RECOVERY_INVENTORY.md) for exact commands.

Nonprivileged readback reports standard kernel `7.2.10-arch1-1` (not Zen), no
BOOT_IMAGE/quiet/splash, default-only linux/zen presets and an inactive fallback
UKI declaration. Boot images remain permission-denied and active entry/recovery
unknown. No privileged command, boot/package/service/mount write or reboot ran.
The already approved elevated read-only inspection still needs the owner's
terminal context; no new boot-write permission is implied.

## 2026-10-20 checkpoint: headless CI test isolation

GitHub Python 3.12 runs exposed three desktop-dependent tests: two required an
installed Bubblewrap merely to inspect argv; one launched article links after
consent instead of faking DNS/browser dispatch. Tests now isolate those effects,
preserve confinement assertions and add an explicit missing-Bubblewrap denial.
Root independently verified **79 passed in 0.96s** across the three edited test
modules; the agent's broader article suite passed 89 tests. Correctness lint and
whitespace checks pass. No production confinement or host package changed.

Remote runs also exited 139 after their failing summaries; no local reproduction
or cause is established. The hosted rerun remains required, with no suppression
or speculative production workaround. See [CI_VALIDATION](CI_VALIDATION.md).

## 2026-10-20 checkpoint: compact GDM installation verified

The owner executed the approved compact correction and `dconf update`, reporting
`ok: true`, backup `6b784910f5954a72b897d3ab79599901`. Independent readback confirms
all four payloads match source at mode 0644, PNG 144×48/SHA256
`3817b717f0ec749c88fd48ede237ad5c5f713832dbad2569ebbfd9af0281b9e0`, and a freshly
compiled GDM database. `DCONF_PROFILE=gdm dconf read /org/gnome/login-screen/logo`
returns the compact wordmark path. The 33 installer tests pass; an initial test
command used a nonexistent filename and ran no tests before correction.

Installation/readback is complete; normal-login password visibility and scaling
remain owner acceptance. No GDM restart, forced lock/logout or boot write.
Earlier authentication failure below describes the preceding state, now superseded.
Boot startup still showing Arch is a separate pending recovery/boot integration.
See [LOGIN_LOGO_FIX](LOGIN_LOGO_FIX.md) and [CHECKPOINT_PROGRESS](CHECKPOINT_PROGRESS.md).

## 2026-10-20 incremental checkpoint: listener recovery

After source baseline `4ec0150`, a rejected transcription no longer terminates
the continuous-listener worker and incurs its supervisor's 15-second retry wait.
The narrow capture-only recovery preserves public error reporting, wake mode,
backlog removal and fatal handling of broken recorder transports. Rejected or
unfinished text never reaches the conversation or commands. See
[VOICE_LISTENER_RECOVERY](VOICE_LISTENER_RECOVERY.md).

Independent focused run: **39 passed in 0.23s**, including 14 new synthetic PCM
regressions. No recording, model inference, private data/config changes or service
restart occurred. This is a source checkpoint, not improved Hindi accuracy or
physical listener acceptance; existing resident processes have not been reloaded.

The already approved compact GDM correction remains **not installed**: its native
authentication dialog timed out, and fresh readback found neither the compact
asset nor its selected key. The exact copyable terminal command was supplied
again. An owner's acknowledgment alone is not execution evidence. No GDM restart,
forced lock/logout or boot write occurred. Follow the
[checkpoint ledger](CHECKPOINT_PROGRESS.md) for remaining owner/approval gates.

## 2026-10-20 runtime and graphical setup checkpoint

Full regression suite: **1080 passed in 12.63s**, including six optional
Plymouth interpreter tests using the reviewed external source subset; correctness
Ruff and whitespace checks pass. Without that explicitly supplied subset the
six checks skip; tests never download it automatically. Eleven fixed public local-model cases pass with zero tools executed.
An earlier temporary nine-page xcb greeting smoke passed, companion visible.
Two final attempts ended with window closure before the reply/check completed;
the diagnostic now reports that interruption explicitly and does not count it as
a pass. A separate current-source, tool-free local core greeting passed in 4.521s
with temporary memory off. The six-page first-run preview passed without saving.
These are limited checks, not physical voice, boot or installer acceptance.

- Optional 3D blue particle presentation is selectable in Companion Settings and
  the avatar menu; 2D remains default. Microphone/screen menu labels refresh from
  saved state; starts require native opt-in, stops request immediate disable.
  Geometry and owned-process cancellation repairs preserve manual placement and
  launched apps. Physical cross-monitor dragging/reconnect remains unverified.
- Current intent remains separate from bounded Ctrl+Enter interrupted context.
  Immediately before POST, recipient drift, memory/remote consent, app-usage
  consent and source-specific screen/accessibility revocation cancel prepared
  context. Critical late review defects received synthetic regressions.
- Research defaults to articles, with explicit native search/open-up-to-three
  review. A document is created only on an explicit report request. Saved report
  navigation offers separately approved one-shot en/hi commands, not continuous
  recording. Website synonyms accept equivalent correct tool routes; malformed
  read-only metadata arguments receive at most one repair, never action retries.
- [Power actions](POWER_ACTIONS.md) have a native time picker and final default-No
  review, fixed bounded shutdown argv, denial feedback and schedule cancellation.
  Thirty-six mocked tests pass. **No power-off, restart, scheduling or cancellation
  was executed on this host**; a spoken yes or a broad grant cannot self-approve it.
- Approved official Whisper small download is size/SHA256 verified and preserved
  alongside base. The pinned private CUDA build completed; after a separate owner
  approval only `whisper_cli` changed, with a private config backup. Base, language,
  profile and listening remain unchanged. CPU/CUDA fixed five-phrase comparison:
  80.243s/22.500s, sampled CUDA peak 961 MiB with Ollama unloaded. English exact;
  base Hindi rejected, small Hindi inaccurate on all four phrases. Hindi is **not
  fixed**, and concurrent LLM/voice peak remains unmeasured. See
  [VOICE_MODEL_COMPARISON](VOICE_MODEL_COMPARISON.md) for hashes/commands/rollback.
- The owner's photo is now the tracked default with private provenance metadata
  removed losslessly; the original is untouched. Matching Aurora Ridge SVG/PNG
  replaces tracked native/Plymouth/Calamares logos. Native icon resolution uses
  installed generic paths with a source fallback. Formal release rights still
  need review; no invented CC license. See [branding](BRANDING_AND_ARCHISO.md).
- [Native first-run setup](FIRST_RUN_SETUP.md) has six Qt pages, explicit static
  checks, language/personality drafts, consent guidance and native app links.
  Twenty-eight onboarding tests pass. The staged art/default/GDM installer now has
  33 disposable-root backup/rollback tests, hash-bound plans and symlink refusal;
  it never invokes package/service/boot commands. The owner separately approved
  and executed desktop art/defaults and the GDM logo stages plus dconf update.
  Fresh readback verifies all nine 0644 files against the reviewed source, compiled
  regenos/GDM databases and the GDM logo key. The existing owner wallpaper is
  preserved. Private rollback backups are outside Git; actual login appearance
  awaits the next owner login. Boot activation remains separately gated.
  Finish alone saves edited preferences/completion; Cancel writes nothing.
  Completed/live-session gating and an installed-only autostart template are
  source-tested. This is onboarding, not an OS disk installer. Existing venv's
  editable metadata was refreshed offline with no dependency changes; the new
  manual app-menu entry and per-user logo were installed with a private backup.
  **No setup autostart was installed on this host.**

The owner separately approved restarting only `ai-os.service` after tests.
Restart/readback passed: active/running, zero restarts, exit status0; config bytes
unchanged and listening/wake/speaker filtering all off. No other service changed. Runtime readiness reports voice ready, no blockers, microphone
unmuted and local selected model present; it explicitly does not verify personal
microphone/language accuracy. Listening/wake/filter remain off. The ordinary
companion was gracefully reloaded again after tests, loading 3D/menu/branding
source with config bytes unchanged. The actual first-run app was opened without
Finish; its manual menu entry validates. A benign test-site launch through Brave
was accepted; page-load correctness remains an owner check. Current Qt inventory
sees only eDP-1, so no physical second-monitor transfer is claimed.

The owner approved elevated **read-only** boot inspection. The executor cannot
share the owner's terminal sudo cache. The first helper also detached from the
terminal; it was fixed to preserve the session with an owned process group and
received 33 focused regressions. The owner's rerun reports GRUB and the regular
linux/zen kernel/UKI files, but no recognized fallback image; one preset references
an unlisted fallback UKI. Menu-entry classes are absent from the partial report.
This is not a verified recovery path. No boot write is authorized until exact
active entries/output paths and usable recovery are established. See the branding
proposal for sanitized evidence and limitations.

No system package/driver/firewall/boot/initramfs/mount/disk operation occurred.
Only the approved artwork/dconf files and compiled defaults were installed by
the owner; only the approved user core service restarted. GDM was not restarted.
**No ISO built, no VM tests, no publication.**

Commands (existing venv, repository cwd):

```bash
REGENOS_PLYMOUTH_SOURCE_DIR=$HOME/.ai_os/build/plymouth-script-check-26.134.222 QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q --tb=short
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests scripts/render_branding.py
git diff --check
~/.ai_os/venv/bin/python -m ai_os.model_probe qwen2.5:7b-instruct-q4_K_M
~/.ai_os/venv/bin/python scripts/verify_native_runtime.py
~/.ai_os/venv/bin/python -m ai_os.avatar_overlay --status
~/.ai_os/venv/bin/python scripts/render_branding.py --output /tmp/regenos-art-review
~/.ai_os/venv/bin/python -m pip install --no-index --no-deps --no-build-isolation -e .
desktop-file-validate config/desktop/regenos-setup.desktop config/autostart/regenos-setup.desktop
bash -n scripts/install_native_desktop.sh
```

Next: owner microphone/speaker/echo/wake/Hindi checks; physically review avatar/menu/
monitor transfer and first-run layout; obtain supported boot inspection before
requesting boot writes; validate the source Plymouth theme in a VM. Keep ISO Prompt F
architecture approval and asset-license checks ahead of packaging. The unrelated
`:memory:.ses` remains untouched; no private models/configuration/logs are tracked.

### Urgent login-layout correction after owner testing

The owner physically reported that the 512×512 square GDM image obscured the
password area. Installed GNOME 51.1 loads natural image dimensions and its CSS
has no 48px cap; the prior generic documentation assumption was wrong. The source
now provides a 144×48 landscape **REgenOS** wordmark, with Arch's approximately 3:1
proportions, and keeps square app icons separate. GDM installation validates
compact intrinsic SVG/PNG dimensions and rejects giant/square wordmarks.
33 focused installer regressions pass. Source Plymouth/Calamares also prefer
the named landscape artwork; this does not activate host boot branding.

The reviewed four-file corrective GDM plan is
`e26d1419c5cdd8ba7b68315478d3f183b2f541add69a22e423030830a336646e`.
The owner requested the correction and already approved GDM branding; the exact
copyable terminal command was provided. Execution/readback and a physical
password-field recheck remain pending. No password masking/PAM behavior changes.
See [LOGIN_LOGO_FIX](LOGIN_LOGO_FIX.md) and the complete
[remaining task inventory](REMAINING_TASKS.md), covering A001–A100/new requests.

The host rebooted between checkpoints (uptime 11minutes on reinspection).
Core is active/running, zero restarts, exit 0; listening/wake/filter remain off.
The old temporary Plymouth source subset vanished, causing six fixture errors
when explicitly selected. No product assertion failed in that attempt. Restored
22 official pinned sources/license/provenance/checksums under
`~/.ai_os/build/plymouth-script-check-26.134.222` outside Git; all six interpreter
checks and the final 1080-test suite pass. Source commit remains
`d15928a8e06c217aad0f2e3579df23fec93dc009`; manifest SHA256
`2ee30f0477c3f08cc97c859e9f00a371bc09c1c43a24c1dc1d146ccd4bc7a8eb`.
No automatic test download or new service restart occurred after that reboot.

## Continued runtime completion checkpoint — 2026-10-19

This follows `c8d2c28` on `main`. Preserve unrelated `:memory:.ses`.
Final full regression run: **774 passed in 10.53s**; correctness Ruff, whitespace,
native installer shell syntax and Chat/Research desktop validation pass.
[REQUEST_STATUS](REQUEST_STATUS.md) maps the owner's requests to implementation,
physical acceptance and approval gates. Work is not universally complete; Hindi
recognition remains a blocker before ISO release work.

- Native memory now supports explicit inspected-user-statement pinning to durable
  shared notes, selected-note editing/removal and stale-revision guards. No private
  memory was inspected; no semantic auto-merging or model-weight training claim.
- Closed legacy memory-tool consent/path gaps: all five read tools bind the active
  runtime, recheck memory and remote-sharing consent, and reject cached results
  after revocation, including immediately before network submission. Sixty new
  privacy regressions pass. Legacy vector APIs now return `semantic_setup_required`
  without importing Chroma, opening stores, fetching weights or enabling telemetry.
  Existing stores are preserved; trusted offline semantic provisioning is pending.
- Fixed Wikipedia `exchars` 2200 → supported 1200. Added short attributed Crossref
  abstract excerpts/evidence counts, en/hi structure, paragraph selection/Previous
  and incremental progress. Live `giant panda conservation` query: 7 sources
  (3 encyclopedia, 2 abstract, 2 metadata), no warnings, 1.70s. Temp report removed.
- Added [guided voice checks](VOICE_DIAGNOSTICS.md) with per-record consent,
  local current-utterance-only inference, no actions/history and owned-group
  cleanup. Opened the actual native window with recording off; no agent microphone
  capture or audible playback. Public STT errors replace private backend details;
  Hindi/script mismatch rejects before actions. Continuous speaker-filter errors
  now reach visible status with 15-second callback rate limiting.
- Existing openWakeWord ONNX assets/backend load in a bounded child (1.7s), no
  microphone/download. Wake accuracy remains untested; `pip check` still reports
  the package's missing TFLite dependency. Explicit ONNX loading succeeds.
- English synthetic Piper→Whisper→local reply→Piper completed in 19.214s initially
  (model 14.136s). After bounded diagnostic replies, hardware-policy reuse and
  timing counters, model-only turns took 3.645s/0.420s, load 3.111s/0.001s and
  generation 0.375s/0.367s. Cache/cold effects prevent a universal speedup claim.
  Whole-GPU peak sampled across sequential synthetic stages: 4701 MiB/103 samples,
  not simultaneous worst-case or real mic latency. Hindi base still fails closed.
- Actual installed Brave discovery and YouTube launch request passed; owner must
  confirm the intended visible page. No browser/account content was read.
- After the final 774-test run, `scripts/verify_native_runtime.py` passed again:
  nine native pages, xcb, visible temporary companion and a completed synthetic
  local greeting. It used temporary settings/history with voice and memory off.
- Owner approved three GNOME bindings only: Super+Alt+A Settings, +C Chat, +R
  Companion. Apply/fresh readback passed; physical keys remain unverified.
  [Rollback](DESKTOP_SHORTCUTS.md) backup `1b32cb89af574ced9d092e35d3261e34` is
  outside Git. Existing bindings preserved. The owner separately approved only
  `ai-os.service` restart for these latest repairs; it is active/running with
  exit status 0 and zero restarts. No driver/firewall/boot/disk change occurred.
- Readiness: continuous listening/filtering off, private profile present, PipeWire
  unmuted, core active, local model installed/reachable, `voice_blockers=[]`.
  Asset readiness is not personal recognition/quality acceptance. Official
  multilingual Whisper small download/comparison still awaits its own approval;
  resume and shortcut approval do not authorize model downloads.

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q --tb=short
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests
git diff --check
~/.ai_os/venv/bin/python -m ai_os.runtime_health
~/.ai_os/venv/bin/python -m ai_os.voice_diagnostics
~/.ai_os/venv/bin/python -m ai_os.desktop_shortcuts --action propose
# Only after the owner's explicit approval for this checkpoint:
systemctl --user restart ai-os.service
systemctl --user show ai-os.service --property=ActiveState --property=SubState --property=MainPID --property=ExecMainStatus --property=NRestarts
```

Live research used `run_research('giant panda conservation', home=temporary_path,
language='en', human_confirmed=True)`. Synthetic model checks used fixed public
questions with `voice_diagnostics.local_reply(..., metrics={})`; no private
history/actions. Reports/audio were temporary. No ISO/VM/release was produced.
Before the approved restart the unit was inactive/dead with prior exit status 0;
afterward active/running, PID 18484, `NRestarts=0`, `ExecMainStatus=0`. A diagnostic
script initially used a nonexistent raw speaker-filter key after successful restart;
corrected readback through `runtime_health.report` passed: core active,
`voice_ready=true`, no blockers, speaker filtering/listening/wake all off. No raw
journal or private conversations were read. Fresh native workers use current source;
already open Settings/Chat windows may need an ordinary close/reopen.

## Blue hologram and GitHub MCP checkpoint — 2026-10-19

**603 tests passed in 9.44s**; correctness Ruff, whitespace, native installer shell
syntax and Chat/Research desktop validation passed. Source/remote baseline was
merged and pushed as `af5b8b4`; this follow-up preserves the unrelated
`:memory:.ses`. No ISO or VM was built, no release/artifact was published.

- Replaced the cartoon core with original segmented blue particle rings, an
  animated energy aperture and speech waveform. Persistent particles still morph
  into built-in/topic/custom shapes. Native Sky/Ice/Electric shade controls work;
  invalid/non-blue legacy choices render as Sky. Existing blue shade is preserved.
  Gracefully reloaded only the ordinary companion app with `--show`; process is
  running, visibility preference true. Physical appearance/monitor acceptance pending.
- Installed the checksum-verified official GitHub MCP server v2.0.2 outside Git.
  Following the user's request, enabled reads only for `Aryan1771/ai-os`.
  Permissions has a separate exact-repository default-No opt-in and Disable button.
  Branch/README protocol smokes and a real local-model → `github_read` → ephemeral
  result passed (2.00s). Account content never enters another model turn, saved
  chat, automatic memory, action planning or automatic spoken content. Existing
  Codex GitHub connector metadata read passed; no duplicate client configuration.
  See [provenance, commands and limits](GITHUB_MCP.md).
- Real native smoke used temporary settings/history, nine pages and XWayland/xcb:
  greeting completed, companion visible, 5.60s total. Sampled whole-GPU usage
  peaked at **4707 MiB** across 25 samples (~200ms intervals). RTX 4060 Laptop,
  driver 615.78.08, 8188 MiB reported total; initial reading 41 MiB. This is one
  synthetic greeting, not the peak of concurrent voice/STT/TTS or a universal budget.
- Readiness now reports the saved profile present (0600); its inode/size/mtime
  were unchanged across companion reload. Listening/filtering stayed off, PipeWire
  ready/unmuted, core active, local model reachable. No additional service change,
  privileged install, driver, boot, firewall or disk operation occurred here.
  `pip check` still reports the pre-existing openWakeWord/tflite-runtime dependency
  gap; the selected RE/Whisper wake path is separate. The venv is not dependency-clean.

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q --tb=short
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests
git diff --check
bash -n scripts/install_native_desktop.sh
desktop-file-validate config/desktop/regenos-chat.desktop config/desktop/regenos-research.desktop
~/.ai_os/venv/bin/python scripts/verify_native_runtime.py
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv,noheader,nounits
~/.ai_os/venv/bin/python -m ai_os.github_mcp --status
~/.ai_os/venv/bin/python -m ai_os.companion_control
~/.ai_os/venv/bin/python -m ai_os.avatar_overlay --show
~/.ai_os/venv/bin/python -m ai_os.runtime_health
```

The GPU sampler ran `nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits`
with a two-second subprocess bound every ~200ms around the native smoke. GitHub
reads withheld returned account text from development output; no token or private
recording/profile contents were printed. See [acceptance](ARCH_ACCEPTANCE.md) for
the remaining physical voice/desktop checks. Hindi transcription quality remains
a known blocker. Do not proceed to ISO release work on this evidence alone.

## Speaker enrollment feedback repair — 2026-10-19

The owner reports that all five samples were accepted after two or three retries
and the voice profile was saved. This is owner-confirmed enrollment completion,
not measured recognition accuracy. Preserve the profile and selected threshold;
no agent recorded, inspected personal samples/embeddings, or lowered the threshold.
English/Hindi acceptance, false matches, replay resistance and everyday microphone
performance remain unverified. Speaker filtering still requires its separate opt-in
and never authorizes commands, sudo or login.

The wizard previously replaced safe voice-difference/model-change errors with a
generic backend/microphone message. It now keeps accepted samples, shows their
count and the specific safe retry reason. Extraction workers emit only fixed
public error codes/messages; raw backend diagnostics and private paths stay hidden.
Synthetic regressions cover consistent 512-dimensional enrollment, held-out
nonmatches, changed models and malformed worker output. They do not establish
personal speaker accuracy. The focused identity/setup/filter/regression run passed:

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q \
  tests/test_speaker_identity.py tests/test_speaker_setup.py \
  tests/test_speaker_filter.py tests/test_speaker_verification_regression.py --tb=short
# 54 passed after recording-setup failure cleanup coverage
```

## Native interaction and voice identity — 2026-10-19

Latest evidence supersedes older executor restrictions below: **603 tests pass**,
correctness Ruff passes. The private PTY helper now establishes its terminal in a fresh process, avoiding
forkpty in the Qt-threaded test runner. See [research/chat/cleanup](RESEARCH_AND_CLEANUP.md)
and [voice identity/voice choices](VOICE_IDENTITY_AND_VOICES.md) for controls/limits.

- Added reviewed interactive terminal jobs (1–900s), ordinary command cancellation
  cleanup, public per-request activity, compact chat with Enter/Shift+Enter/Ctrl+Enter
  and stale callback guards. Disk/boot/shell/script/OS restrictions remain.
- Native speaker wizard records four explicitly requested styles plus a fresh fifth
  check, saves only a private embedding, and requires a separate filtering opt-in.
  Per-utterance matching has a ten-second worker bound. After explicit user approval,
  sherpa-onnx/core 1.13.8 and the 29,596,978-byte CAMPPlus English candidate were
  provisioned. Synthetic extraction passes (512 dimensions, 0.448s); English/Hindi
  matching accuracy remains pending. The owner subsequently completed enrollment
  as recorded above; no agent microphone capture or personal enrollment.
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

The initial dry run resolved compatible 1.13.8/core wheels. The user subsequently
approved installing them and downloading the official speaker model:

```bash
~/.ai_os/venv/bin/python -m pip install --no-cache-dir sherpa-onnx==1.13.8
gh release download speaker-recongition-models --repo k2-fsa/sherpa-onnx \
  --pattern 3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx --dir ~/.ai_os/models
~/.ai_os/venv/bin/python -m ai_os.speaker_setup
```

Model SHA256: `357a834f702b80161e5b981182c038e18553c1f2ca752ed6cec2052365d4129b`.
The release had no published asset digest; size/source/local hash were checked,
not an independent publisher checksum. Model preference saved after private backup
`~/.ai_os/backups/pre-migration-rctjzwx8`, leaving listening/filtering off. The native
wizard was opened for explicit consent/Record; the owner later confirmed saving
the profile after retries. No automatic enrollment or filtering activation.
Stale ignored source egg-info shadowed newly installed metadata; refreshed it with
`from setuptools import setup; setup(script_args=['egg_info'])`. All four native
entry points are visible from the checkout and installed venv.
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
