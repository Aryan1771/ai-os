# Local screen awareness

2026-09-28. REgenOS remains a desktop/runtime prototype. Screen awareness now has
a continuous local OCR path, distinct from the older one-shot corner-texture
heuristic. This is text recognition, not general image/video understanding.

## Controls and actual behavior

In **Companion**, enable **Let RE read my shared screen locally**. The resident
companion starts a separate native Qt Widgets screen reader. On GNOME Wayland,
select the monitor through the desktop's screen-sharing dialog. The avatar stays
on XWayland for positioning; the reader uses a real Wayland Qt Multimedia client.
The reader is started at login through the existing companion startup when this
permission is saved. Portal authorization is not bypassed or guaranteed to persist
across restarts. Only the selected screen is shared, not every monitor automatically.

The **RE · Screen awareness** window shows sharing status, **Pause**, **Resume /
select screen**, and **Ask RE**. Pause stops capture, clears the observation and
comment, and cancels owned OCR/model/speech processes. Closing this window disables
the setting. The avatar menu also has **Stop screen awareness**. Sharing has its own
indicator even if the avatar or debug labels are hidden.

Ask **“What is on my screen?”** in the conversation or use **Ask RE** in the screen
window. Such requests use an isolated, read-only model call. Screen text and derived
answers are not appended to conversation memory. Ordinary command requests retain
their existing reviewed tool path and do not automatically receive screen text.
Screen text cannot approve a command or become a tool request: structured tool
responses from screen inference are rejected. This separation also applies when a
timed command grant is active. It is not a claim that prompting eliminates every
possible misleading model response.

**Offer comments when my screen changes** shows a short local comment, at most once
per configured 1–120 minutes (default five). The first attempt waits 30 seconds.
The GNOME idle monitor must report activity within two minutes, and the assistant
must be idle, awaiting a wake word, or showing a previous reply. Small OCR changes
are ignored using text similarity. This cannot establish whether a screen change
was caused by you, another person, or an application. Comments must not claim that
attribution. They also may be mistaken or unhelpful; normal model limits apply.

**Speak screen comments** additionally requires **Speak replies**. Microphone
listening is independent. A prompt asks RE not to read secrets/identifiers aloud,
but this is not a reliable sensitive-information classifier. Pause sharing before
displaying secrets; leave spoken comments off if others should not hear them.

Locking or losing the GNOME lock-state service stops capture and clears context.
Use Resume after unlocking; another portal selection may be required. Unknown lock
state fails closed. Other desktop lock protocols, including Hyprland's, are pending.
GNOME inactivity suppresses automatic comments but not screen reading.

## Processing and limits

- Qt `QScreenCapture` → `QVideoSink`, no audio source. Frames are sampled at most
  once every five seconds and scaled to a maximum 1920-pixel edge.
- Tesseract English OCR receives PNG bytes over stdin. No screenshot or recording
  files. One OCR child at a time, two worker threads, eight-second timeout.
- The latest observation is bounded to 6000 characters and expires after 20 seconds.
  The previous commented frame is held in memory for similarity checking and cleared
  on pause/lock/staleness. No OCR database or private screen log is written.
- A per-runtime mode-0600 Unix socket exposes fresh context only to the same local
  account. This is not isolation against malicious software already running as you.
  Like other applications, process memory can be subject to system swap/core-dump
  policy; this feature does not change that policy.
- Screen inference requires loopback HTTP Ollama. Remote OpenAI-compatible providers
  receive no screen context even if remote conversation memory is separately enabled.
  No images are sent to the installed text-only Qwen model or browser AI.
- Generation has no tools and no saved conversation history. Model/speech child
  groups have a 90-second deadline and are cancelled when sharing stops. Comments
  are discarded when permission, activity, or the observed scene materially changes.
- OCR may miss small text, obscured text, non-English text, pictures, animations and
  other monitors. Always-on means an enabled shared desktop session, not access to
  login/lock screens or an unrestricted operating-system surveillance capability.

## Dependencies and reproducible checks

Installed with explicit user approval on this host:

```bash
sudo pacman -S --needed tesseract tesseract-data-eng
# Actual authenticated invocation also used --noconfirm after explicit approval.
```

Installed Tesseract 5.5.3-1, English/osd data 2:4.1.0-5, leptonica 1.87.0-2.
Qt Multimedia was added only to the existing venv, matching Essentials:

```bash
~/.ai_os/venv/bin/python -m pip install 'PySide6-Addons==6.11.2'
~/.ai_os/venv/bin/python -m pip install --no-deps --no-build-isolation -e .
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests scripts/verify_screen_runtime.py
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python scripts/verify_screen_runtime.py
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python scripts/verify_screen_runtime.py --model
~/.ai_os/venv/bin/python scripts/verify_native_runtime.py
~/.ai_os/venv/bin/python scripts/verify_screen_runtime.py --status
git diff --check
```

`--status` prints only availability and character count, never the captured text.
Synthetic OCR draws a known test image in memory and checks the real Tesseract
binary. It does not capture the desktop. Fresh text availability proves the capture
and recognition path is producing output, not semantic accuracy or user attribution.

Current-user permission was explicitly requested in conversation; settings were
backed up at `~/.ai_os/backups/pre-migration-7cf28wkw` before enabling
`screen_context_enabled` and `screen_commentary_enabled`. New installations default
off. Existing microphone and speech settings were preserved.

## Verified checkpoint and pending acceptance

- **Automated:** 225 tests pass; correctness lint and whitespace checks pass.
  Regression coverage includes expiry, permission changes, local-only endpoint
  races, no history retention, injected tool rejection, private socket access,
  lock-state denial, idle-user gating, late frames, OCR cancellation, manual-close
  versus process-shutdown behavior, and preserving explicit app-launch requests.
  The final bounded D-Bus call change also passes all 16 screen regressions and a
  read-only real GNOME lock/idle query. D-Bus requests have 250 ms deadlines.
- **Locally tested with real dependencies:** synthetic Qt image → Tesseract →
  private ephemeral socket → local Ollama correctly returned the test number.
  Native UI/local model smoke passed: nine pages, xcb companion visible.
- **Hardware verified, limited:** GNOME portal capture reported active and returned
  2574 characters of fresh OCR. The text and screenshot were not printed or saved.
  Sharing subsequently became disabled and was left paused. The follow-up real
  screen → model request correctly declined unavailable context. Core remains
  active, zero restarts, exit status zero.
- **Pending:** sustained live commentary, spoken comments, manual lock/unlock and
  resume, cross-login portal behavior, OCR accuracy on varied applications,
  multi-monitor selection and non-GNOME lock backends. No claim of general visual
  understanding, attribution to a specific person, or complete OS control.

The first `sudo -n pacman ...` failed because authentication was required.
`timeout 180 pkexec /usr/bin/pacman -S --needed --noconfirm tesseract tesseract-data-eng`
then succeeded after the user's desktop authentication. A lifecycle bug discovered
during smoke checks initially treated process shutdown as manual opt-out; it was
fixed and regression-tested before the successful live capture. The final later
opt-out was preserved. To resume, enable screen reading in Companion, select a
monitor in the portal, then use Ask RE. Minimize the screen window to keep sharing;
closing it disables sharing. Do not restore the old flag without renewed user intent.

References: [Qt screen capture and Wayland portal requirements](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QScreenCapture.html),
[Qt capture session](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QMediaCaptureSession.html),
[Tesseract CLI and sparse-text mode](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html).
