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
- This host uses GNOME; preserve it while integrating installed Hyprland 0.56 Lua
  configuration. Biometric enrollment/PAM and boot changes require separate review.
