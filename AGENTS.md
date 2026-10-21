# REgenOS development constraints

- Preserve the exact product capitalization **REgenOS** (lowercase `gen`) and
  the `ai-os` repository/package compatibility. REgenOS is an offline-first
  Arch desktop/runtime prototype, not a finished distribution.
- Read `docs/HANDOFF.md`, `docs/RUNTIME_VALIDATION.md` and relevant feature docs before work; inspect git status
  and preserve unrelated changes. Older Windows results are not hardware validation.
- Supported desktop apps are Python/PySide6 Qt Widgets only. No browser frontend,
  HTML/JavaScript UI, Electron or WebEngine. Retained C++ hub code is historical;
  do not restore it as the default launcher without explicit user direction.
- Prefer `~/src/ai-os` and `~/.ai_os/venv`, Python 3.12+. Respect PEP 668;
  never use sudo pip or alter system Python for project dependencies.
- Never modify or format the internal Windows disk. Ask before privileged installs,
  firewall/AppArmor changes, boot changes, disk operations or other impactful changes.
- Keep subprocesses shell-free and bounded. Audit arguments, not just executable
  names. Models cannot approve actions; background consent must fail closed.
- Access-grant phrases request trusted human confirmation; never expose grant
  confirmation as a model tool. Preserve expiry, scoped execution and revocation.
- Continuous microphone listening requires explicit opt-in, visible state and an
  easy stop. Do not enable it during ordinary diagnostics. Simulated emotions are
  presentation state; saved memory does not train model weights.
- Test before native UI, Ollama, audio and service smoke checks. Isolate test runtime
  data; never commit credentials, private memory, recordings, models, venvs or logs.
- Record exact commands and distinguish implemented, locally tested,
  hardware-verified and pending. Prioritize runtime reliability over ISO work.
- Commit and push intentional tested source/docs changes when requested; never
  force-push. Keep this file concise and update the handoff after substantive work.

- Ollama CLI use bypasses REgenOS memory/tools. Verify actual installed entry points
  separately from source. Back up affected private runtime data before migrations.
- Hindi/English voice assets are installed; consult the handoff for validation
  limits before enabling listening. Never claim expressive behavior is sentience.
- The assistant is RE, pronounced as the letters R E. Wake detection is not
  identity verification; never use it to approve actions or unlock a session.
- Debug labels may hide, but microphone and access-grant indicators must remain
  visible. Screen capture/proactive speech are opt-in. Browser submissions need
  exact native approval; never reuse personal browser profiles or bypass site checks.
- This host uses GNOME; preserve it while integrating installed Hyprland 0.56 Lua
  configuration. Biometric enrollment/PAM and boot changes require separate review.
- Screen OCR is ephemeral, local-only and read-only: never pass observations to
  tool planning, saved memory or remote providers. Preserve the sharing indicator,
  pause control, lock checks and portal selection. See docs/SCREEN_AWARENESS.md.
- Optional AT-SPI context follows the same read-only/local/ephemeral boundary;
  it requires its own native opt-in and must stop on lock or permission revocation.
- App usage memory is a separate opt-in: app names/time estimates only, bounded
  retention and explicit inspect/clear controls. Never add keystroke/clipboard capture.
- Broad command grants require the Bubblewrap boundary; never silently fall back
  to ordinary execution. Launch its installed Python helper with isolated mode
  before entering an untrusted cwd. Tool discovery changes schemas, never permissions.

- Reinforced memory stores only bounded, opt-in repeated user statements as untrusted
  reference data. Preserve session scope, decay, inspection, forget/clear revision guards
  and pre-migration private backups; never promote assistant claims into facts.
- Keep speech wait, ending silence and maximum utterance separate. Incomplete audio
  must not submit partial commands. Selected mode follows saved language; match mode
  uses current Whisper metadata, with unknown language failing closed. Share speech leases.
- Speaker embeddings are private conversation filters, not command/login approval;
  never record, enable filtering or download assets implicitly. Recognition is not cloning.
- Public progress exposes tool names/status, never private internal reasoning,
  arguments, passwords or screen text. Mood affects tone, never facts or consent.
- Cleanup uses native previews/recoverable Trash; reuse only explicitly approved
  directory/pattern/inode rules. Never infer broad deletion consent from past actions.
- Research sends only reviewed topics to fixed public APIs. Keep citations real,
  distinguish metadata/excerpts from verified findings, and keep explanations local.
- GitHub MCP uses the pinned official binary, read-only tools and a native exact
  repository opt-in. Keep account results ephemeral and outside model planning,
  remote providers, automatic memory and speech content. Never expose setup/auth as tools.
- Guided voice diagnostics require each explicit Record click, remain local and
  tool-free, and save no conversation. Group cancellation must never signal PID 0
  or the desktop group; verify the task's fresh process group before signalling.
  Latest-check status is private, schema-only metadata; never add transcripts,
  audio, arbitrary errors or paths to it, and never turn it into a history log.
- GNOME shortcut changes need exact native approval, private backups and readback.
  Preserve unrelated/custom concurrent changes and refuse rollback over later edits.
- Bind legacy memory reads to the selected runtime and recheck memory/remote consent
  before reads and cached inference. Semantic APIs stay disabled until trusted offline
  embeddings with no implicit downloads or telemetry are implemented.
- First-run onboarding is separate from the disk installer: Finish alone records
  completion; live sessions never consume/copy the developer marker or autostart
  Calamares in installed sessions. Boot/logo activation needs verified recovery
  and exact approval; a source theme is not a boot test. Preserve photo provenance
  without publishing private embedded metadata or inventing redistribution licenses.
- GNOME 51 loads greeter logos at natural size. Use the compact named landscape
  wordmark (144×48), never the 512px square app icon; preserve password-field space.
- Keep desktop/screen PySide dependency bounds paired. The current supported
  range excludes 6.12 after controlled hosted teardown crashes; lifting the cap
  requires a full-process pass, not only a passing pytest summary. See CI_VALIDATION.
- Qt tests must dispose of owned dialogs/timers and fake QObject children before
  fake fixture teardown; defer no test process-double deletion into later tests.
