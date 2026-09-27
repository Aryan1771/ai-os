# REgenOS handoff — 2026-09-27

Preserve exact **REgenOS** capitalization. This is an offline-first native desktop
and Arch runtime prototype, not a finished distribution. Start with
[RUNTIME_VALIDATION](RUNTIME_VALIDATION.md) for commands, measurements, rollback
and limitations, and [IMPLEMENTATION_CHECKLIST](IMPLEMENTATION_CHECKLIST.md) for
the dependency-ordered audit of all 100 feature checkboxes (33 unchecked).

## Actual installation versus source

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
