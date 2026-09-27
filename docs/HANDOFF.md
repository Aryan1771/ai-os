# REgenOS handoff — 2026-09-27

Preserve exact **REgenOS** capitalization. This is an offline-first native desktop
and Arch runtime prototype, not a finished distribution. Start with
[RUNTIME_VALIDATION](RUNTIME_VALIDATION.md) for commands, measurements, rollback
and limitations, and [IMPLEMENTATION_CHECKLIST](IMPLEMENTATION_CHECKLIST.md) for
the dependency-ordered audit of all 100 feature checkboxes (33 unchecked).

## Actual installation versus source

- Resume validation supersedes the earlier machine snapshot below: running kernel
  `7.2.7-arch1-1`, NVIDIA module/userspace `615.71.09`, RTX 4060 Laptop with
  8188 MiB VRAM. Driver access works outside the tool sandbox. The user daemon,
  PipeWire and WirePlumber are active; this resume did not start/restart them.
- Ollama remains CPU-only: two synthetic requests took 4.601/1.609 seconds;
  `/api/ps` reported zero model VRAM. Across 52 device samples the maximum was
  12 MiB. `ollama-cuda` is absent despite installed `ollama` and `cuda` packages.
  Installing the backend and restarting Ollama requires user approval.
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
2. With user approval, install the matching `ollama-cuda` backend and restart
   Ollama, then rerun `scripts/verify_gpu_runtime.py`. Driver mismatch is resolved;
   actual model offload and inference peak VRAM remain pending.
3. Voice assets stay deferred per user. Later choose verified multilingual Whisper
   and suitable English/Hindi Piper voices; measure every audio stage separately.
4. Finish tokenizer-aware limits, robust request ordering, streaming/tool-result loop,
   speech cancellation/stall recovery and actual bilingual acceptance.
5. Follow the audit dependency order for trusted native approvals/security, desktop,
   branding and VM-only ISO/Calamares work. Do not mark unchecked items complete
   from source existence alone. Emotions are simulated; memory is not model training.
