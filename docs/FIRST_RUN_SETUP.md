# Native first-run setup

`regenos-setup` is a Python/PySide6 onboarding wizard for an **already installed**
REgenOS runtime. It is separate from the Calamares disk-installer source and does
not make the current ISO installable. The six pages introduce RE, conversation
language/personality, permission boundaries, installed-component checks, native
app links and an explicit Finish action. Existing settings are preserved.

## Controls and writes

Opening or cancelling the wizard creates no runtime directory, completion marker,
recording, model download, service change, command grant or desktop configuration.
No check runs automatically. **Check installed runtime** launches a bounded,
read-only worker that checks executable/model-file presence. It does not contact
Ollama, query remote providers, perform inference, inspect private conversations,
record audio or capture a screen. Presence is not end-to-end hardware validation.

**Finish setup** is available on the final page after acknowledging that permissions
are separate. It saves only language/reply-mode/personality values edited in this
wizard. A fresh read preserves unrelated changes; a concurrently changed selected
preference prevents completion and asks for review. Existing microphone, screen,
memory, provider, command-access and desktop preferences are not reset or enabled.
Automatic speech language remains visible when it was already configured.

Completion is recorded in the selected runtime's `data/private/first-run.json`:
version, completion flag and timestamp only. The private directory/file use 0700/
0600 permissions, and the marker is written atomically. Symlink destinations are
rejected. It is not a hardware-acceptance record. If saving preferences succeeds
but the marker write fails, preferences may already be saved; setup remains
incomplete and the wizard reports the failure. Models and memory stores are never
copied, migrated or cleared by this flow.

App links open only after an explicit click. Settings opens the exact requested
page with companion auto-start disabled and reuses its panel so unfinished drafts
remain available. Settings retains its normal Save/approval controls and runtime
initialization behavior. Chat and Research receive the selected `AI_OS_HOME`.
The wizard does not close another dashboard or discard its drafts.

## Launch gating and future packaging

```bash
~/.ai_os/venv/bin/regenos-setup
# Source/module fallback:
~/.ai_os/venv/bin/python -m ai_os.first_run
# Intended installed-session first-login command:
~/.ai_os/venv/bin/python -m ai_os.first_run --if-needed
# Explicit read-only live preview:
~/.ai_os/venv/bin/python -m ai_os.first_run --live
```

`--if-needed` exits **before creating a GUI** when a valid completion marker exists
or the session is live. `REGENOS_LIVE_SESSION=1` or an existing `/run/archiso`
identifies live operation. Explicit `--live` permits browsing the wizard while
disabling preference edits and saving no completion marker. The installed target
must not retain live-session flags or directories.

Tracked launchers are `config/desktop/regenos-setup.desktop` (manual app-menu
entry) and `config/autostart/regenos-setup.desktop` (installed-session template,
`Exec=regenos-setup --if-needed`). **The autostart template was not installed on
the development host.** Future clean target-root packaging may install it after
review; live packaging must suppress installed onboarding and must not copy the
developer's marker/configuration. First-run setup never launches Calamares, and
the installer must not autostart on installed-system logins. See
[installer prerequisites](../archiso/calamares/README.md).

No signing, ISO building, mounting, partitioning or boot change is part of this
implementation. A graphical live/install experience still needs the approved
release architecture, clean target image and disposable-VM acceptance.

## Validation

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_first_run.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/first_run.py tests/test_first_run.py
desktop-file-validate config/desktop/regenos-setup.desktop config/autostart/regenos-setup.desktop
```

28 synthetic tests pass, covering cancel/Finish gates, isolated runtime selection,
preservation of existing private assets/settings, concurrent changes, malformed
markers, symlink rejection, live/completed gating and explicit inventory/app links.
A temporary native **xcb** preview opened the six-page wizard's welcome and REgenOS logo;
it closed after approximately two seconds without Finish and did not create its
temporary runtime. No personal settings, model, service or autostart was changed.
Manual onboarding on a clean installed system and final-ISO VM acceptance remain
pending. The preview emitted a Noto Sans OpenType warning for a Hindi script; Hindi
font rendering needs visual acceptance on the target desktop.

Development host integration: the editable package metadata was refreshed using
`pip install --no-index --no-deps --no-build-isolation -e .` in the existing
venv. Only the per-user manual Setup launcher and shared app icon were installed,
with a private backup. The ordinary Setup window was opened without automation
of Finish. No autostart, system default, boot file or login setting was applied.
