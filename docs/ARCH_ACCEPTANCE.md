# Interaction acceptance — current source checkpoint

2026-10-20. Current Arch tests can access local sockets/services. Temporary synthetic
runtimes separate regression evidence from personal/hardware acceptance. The project
remains a preview prototype; no ISO/VM or production readiness claim follows.

| Check | Actual result | Status |
| --- | --- | --- |
| Boot/login/ISO/VM | Owner-run helper reports GRUB; referenced fallback unlisted, recovery unverified. Approved desktop/GDM artwork/defaults installed; nine file hashes, compiled DBs and logo-key readback pass; GDM not restarted | Visual login/lock/boot pending; no boot writes, ISO or VM tests |
| CUDA STT comparison | CPU 80.243s/CUDA 22.500s, sampled peak 961 MiB with LLM unloaded; English exact, Hindi poor | Limited synthetic comparison; personal/concurrent acceptance pending |
| Complete Python/Qt suite | 1080 passed in 12.63s, including new setup/privacy/3D/power/article checks | Automated suite passed |
| Focused voice/context/memory/hardware/grant regressions | 134 passed; silence endpointing, current-turn/language routing, speech ownership, expiry, busy hotplug delivery and prior permission/context controls covered | Locally tested |
| Correctness Ruff E4/E7/E9/F | All checks passed | Locally tested |
| Existing venv dependency audit | pip check still reports openwakeword 0.6.0 requires missing tflite-runtime | Unresolved pre-existing optional-backend gap; selected RE/Whisper wake path separate |
| Existing ONNX wake backend | Bounded isolated child loaded local openWakeWord ONNX backend/assets in 1.7s, no microphone | Backend loading passed; detection accuracy not tested |
| Guided voice diagnostic | 53 synthetic regressions; actual native window opened with consent unchecked; no agent mic capture | Source-tested; owner capture/relevance/audibility pending |
| Native memory curation | Explicit user-only pin, selected-note edit/remove and stale revision/session/expiry guards | Synthetic tests; no private memory inspection |
| Legacy memory boundaries | 60 regressions for runtime paths, opt-out, remote consent and cached-result revocation; vector APIs disabled without trusted offline setup | Source tested; no private stores inspected or changed |
| GNOME shortcuts | Owner approved three Super+Alt+A/C/R bindings; apply/fresh readback passed, no conflicts; private backup | Applied; physical key presses pending |
| Whitespace | git diff --check passed | Locally tested |
| Harmless namespace diagnostic | no_new_privs true, root read-only, physical NVMe node and D-Bus paths absent | Limited local smoke |
| Existing source/venv provenance | Editable checkout, installed Qt, four native entry points/desktop launchers confirmed | Locally inspected |
| Native blue hologram | Earlier temporary nine-page xcb greeting passed; final retries interrupted by window closure before reply, not counted as passes. Separate tool-free core greeting passed in 4.521s. Companion visible in temporary Qt status. Ordinary resident companion gracefully reloaded with saved blue preference | Limited native smoke; physical appearance/monitor acceptance pending |
| NVIDIA memory | RTX 4060 Laptop, driver 615.78.08, 8188 MiB total; 4707 MiB max observed in 25 samples during one native greeting | Sampled workload only; concurrent voice/peak budget pending |
| GitHub MCP | Verified official v2.0.2; exact ai-os repo opt-in. Protocol reads and local model-to-read smoke passed in 2.00s; existing Codex connector metadata read passed | Read-only, ephemeral; write capability not implemented |
| Model style/language | Local synthetic display reaction follows persona; explicit consciousness question answered honestly; en/hi replies tested | Limited model smoke; broad quality/latency/GPU peak pending |
| Real microphone/STT/TTS/listening/recovery | Synthetic English Piper→Whisper→local reply→Piper completed; base Hindi script mismatch now rejects before actions. No agent microphone capture/audible playback | Personal/hardware acceptance pending; approved CPU/CUDA comparison complete; base retained, CUDA executable-only switch approved/applied |
| Speaker enrollment | Approved sherpa/core 1.13.8 + CAMPPlus installed; 512-dimension synthetic extraction, 0.448s. Owner reports all five accepted after retries/profile saved; private file present/0600 | Completion owner-confirmed; English/Hindi accuracy not tested; filtering off |
| Cursor size 64 | GNOME helper verified readback 64 | Applied; human visual confirmation pending |
| Research/cleanup/compact chat | Native regression coverage; live research returned 7 sources (3 encyclopedia, 2 abstract, 2 metadata) in 1.70s without warnings | Live audible narration/user-file cleanup not exercised |
| GNOME accessibility text, lock/revoke and browser support | Synthetic protected-field and revocation tests pass; bindings import | Real desktop not tested |
| App usage accuracy, proactive conversation | Synthetic storage/retention/clear controls; collection defaults off | Real usage not tested |
| Website launch/app discovery/hardware hotplug | Actual Brave discovery and YouTube launch request accepted; no device attach performed | Visible page and hotplug owner acceptance pending |
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

Historical runs reported 350 passed/1 failure/7 errors with AF_UNIX `EPERM`.
The final 774-pass run includes those socket tests; assertions were not disabled.
This resolves the executor restriction, not the outstanding physical acceptance.

Host acceptance after approval of any service changes:

1. The full suite passes; rerun relevant checks after new changes. Stop on regressions.
2. User approved `systemctl --user restart ai-os.service`; it is active and listening
   remains off. No other service/unit was changed. Inspect readiness after future changes.
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

Source work was committed/pushed on main using the authenticated GitHub account's
public noreply identity, merging the two newer GitHub commits without force/reset.
No artifact publication or release occurred; exact revision is reported in the final handoff.

Earlier interaction results remain in [PERSONAL_INTERACTION](PERSONAL_INTERACTION.md).
The latest cursor/service results above supersede earlier denied writes/restarts.
