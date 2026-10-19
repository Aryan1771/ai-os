# Interaction acceptance — current source checkpoint

2026-10-19. Evidence is limited to this sandbox and synthetic temporary runtimes.
The project remains a preview prototype. Historical live results in HANDOFF and
RUNTIME_VALIDATION do not certify the modified harness.

| Check | Actual result | Status |
| --- | --- | --- |
| Complete Python/Qt suite | 350 passed, 1 failed, 7 errors; unsuccessful checks cannot bind local sockets | Blocked full acceptance |
| Focused voice/context/memory/hardware/grant regressions | 134 passed; silence endpointing, current-turn/language routing, speech ownership, expiry, busy hotplug delivery and prior permission/context controls covered | Locally tested |
| Correctness Ruff E4/E7/E9/F | All checks passed | Locally tested |
| Whitespace | git diff --check passed | Locally tested |
| Harmless namespace diagnostic | no_new_privs true, root read-only, physical NVMe node and D-Bus paths absent | Limited local smoke |
| Existing source/venv provenance | Editable checkout and installed Qt confirmed | Locally inspected |
| Model quality, latency and GPU peak | Host Ollama/device access unavailable here | Not tested for this checkpoint |
| Real microphone/STT/TTS/listening/recovery | Assets found; no capture or playback performed | Not tested |
| Cursor size 64 | Desired preference saved; live GNOME still 48 after rejected application | Not applied from executor |
| GNOME accessibility text, lock/revoke and browser support | Synthetic protected-field and revocation tests pass; bindings import | Real desktop not tested |
| App usage accuracy, proactive conversation | Synthetic storage/retention/clear controls; collection defaults off | Real usage not tested |
| Website launch/app discovery/hardware hotplug | Regression coverage; no real launch or device attach performed | Hardware/user acceptance pending |
| Full isolation/privilege mediation | Disabled-by-default grant prototype; no adversarial or policy enforcement certification | Pending security work |
| ISO/installer/VMs | No image built or VM started | Not tested; gated by runtime acceptance and architecture approval |

Reproduce source checks from the checkout:

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q \
  tests/test_interaction_harness.py tests/test_desktop_context.py \
  tests/test_listener.py tests/test_access_grants.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests
git diff --check
~/.ai_os/venv/bin/python -m ai_os.runtime_health
```

Do not hide the failed full run. A direct AF_UNIX bind also failed with `EPERM`,
confirming the current execution restriction. One native single-instance test and
seven screen-observer tests need a rerun outside this sandbox; their implementation
and assertions were not disabled to obtain a pass.

Host acceptance after approval of any service changes:

1. Run the full suite outside the restricted environment. Stop on a real regression.
2. Inspect readiness. Approve a one-time `systemctl --user restart ai-os.service`
   to load the new supervisor. Existing graphical environment/startup must be
   reviewed if the service lacks display/session access; do not overwrite its unit.
3. In native Settings choose either wake gating or explicit conversation listening,
   then test recognition, false activations, speech feedback, disable/re-enable,
   recorder failure and cancellation. Alternatively keep continuous listening off
   and click Speak once. Confirm audibility and input gain with the user.
4. Explicitly enable accessibility context if desired. Test a supported app, an
   unsupported app, editable/password exclusions, lock/unlock, revocation during
   generation and a changed scene. Verify no text is retained or sent remotely.
5. Enable app usage memory only if wanted; inspect approximate counts, clear them
   and disable collection. Test real app/website actions and an approved safe
   command; verify that a denied command stays denied and grants expire/revoke.
6. Compare already-installed models using model_probe; separately grade social
   quality and profile actual VRAM. Downloading/replacing models requires review.

No ISO path, ISO hash or VM pass exists for this checkpoint. Do not proceed to
release packaging while critical runtime acceptance remains blocked.

Checkpoint publication is also pending: source changes are staged, but Git could
not commit without an author identity. GitHub DNS access is unavailable in this
execution environment. No source push, artifact publication or release occurred.

Personal interaction follow-up: [PERSONAL_INTERACTION](PERSONAL_INTERACTION.md); 104 focused tests pass. Four user-requested preferences were privately backed up/saved; GNOME cursor write was rejected and readback remains 32. Resident services were not restarted.
