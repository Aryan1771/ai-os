# REgenOS: installed runtime, latency and continuity

2026-09-27. Source baseline `640183c`; prior uncommitted repair work was preserved.
The user confirmed Phase 1 meant using **Ollama CLI**, not a fully connected
REgenOS daemon or voice pipeline. Ollama CLI bypasses this project's memory,
permissions, tools, companion and settings. Windows source changes were pulled,
but that alone did not deploy or validate their features.

## Resume verification (same date, after reboot)

Latest follow-up: the user installed `ollama-cuda 0.34.4-1`, matching Ollama.
`pacman -Ql ollama-cuda` confirms the `cuda_v13` libraries, including
`libggml-cuda.so`. Tests reran: **121 passed, 1 skipped**. The same GPU probe
still reported `size_vram=0`; requests took 7.901/1.713 seconds, with 65 samples,
no sampling errors and a 12 MiB device-wide sampled peak. The service start time
remains `2026-09-27 08:01:43 IST`. An approved attempt with
`sudo -n systemctl restart ollama.service` failed because sudo requires a password;
no restart occurred. Next: user runs `sudo systemctl restart ollama.service`
locally, then repeat the existing probe. Do not send a sudo password through chat.
The package-absence observation below describes the earlier probe.

This section supersedes earlier kernel, service and test-count observations below.
Running kernel: `7.2.7-arch1-1`; loaded NVIDIA and userspace: `615.71.09`.
Outside the tool sandbox, `nvidia-smi` identifies the RTX 4060 Laptop and 8188 MiB
total VRAM. Inside the sandbox device access failed and the user systemd bus was
denied; these errors were not treated as host failures. The daemon, PipeWire and
WirePlumber are active. No service lifecycle changes were made during this resume.

The existing GPU probe completed two synthetic requests (4.601 and 1.609 seconds).
Ollama reported `size_vram=0`; 52 samples at approximately 100 ms intervals plus
query overhead measured device-wide peak usage of **12 MiB**, with no sample
errors. This confirms CPU inference, not successful GPU offload or an 8 GB cap.
`pacman -Q` finds `ollama 0.34.4-1` and `cuda 13.4.2-1`, but no `ollama-cuda`.
The official [Arch package file list](https://archlinux.org/packages/extra/x86_64/ollama-cuda/files/)
places `libggml-cuda.so` in that separate backend package. Its absence is the
likely immediate blocker. Package installation and an Ollama restart await approval;
no boot modification is indicated by these checks.

Both listening flags remain false and configured Whisper/Piper model files are
absent. No recording, model download or real voice validation was performed.
Native smoke passed: nine pages, `xcb` platform, companion visible, synthetic
chat completed, temporary runtime removed. The retention repair uses saved policy
for omitted history/context/append arguments; previously inspection could prune
90-day history at 30 days. Tests use synthetic 45-day-old records under 7/90-day
policies. **121 tests passed, 1 skipped**; correctness lint and diff checks passed.
One sandbox run failed Qt local socket creation; the approved outside-sandbox run
passed. Historical full-Ruff limitations still apply.

Exact commands from the checkout (device/session checks require host access):

```bash
uname -r
cat /proc/driver/nvidia/version
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv
systemctl --user is-active ai-os.service pipewire.service wireplumber.service
pacman -Q ollama ollama-cuda cuda
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests
~/.ai_os/venv/bin/python scripts/verify_gpu_runtime.py
~/.ai_os/venv/bin/python scripts/verify_native_runtime.py
git diff --check
```

## Installation audit and changes

- Importing Python **from `/tmp`**, outside checkout shadowing, resolves `ai_os`
  to `/home/aryan/src/ai-os/ai_os`. The existing Python 3.14 venv is editable.
  Old installed distribution metadata had no desktop entry points. Refreshed
  only project metadata using `pip install --no-deps --no-build-isolation -e .`;
  `~/.ai_os/venv/bin/regenos-settings` and `regenos-companion` now exist.
- The installed user service uses that venv/source path and is inactive. Its
  unit lacks the newer AppArmorProfile/EnvironmentFile entries. No unit or
  hardening setting was replaced. Previous start/stop smoke exited cleanly.
- Runtime config has older Phase 1 keys; new defaults are merged in memory.
  Existing config, habits and slang were backed up under
  `~/.ai_os/backups/pre-migration-7n_o9uf6` (directory 0700, files 0600).
  No conversation database or voice model files existed before these changes.
  Saved runtime settings were not rewritten; test conversations used `/tmp`.
- Log review used diagnostic counts, not transcript dumps. Local log: 13 lines,
  no error/warning keywords. Last 100 service journal lines included historical
  failures; those counts alone do not diagnose their cause. Ollama logs showed
  CPU-related messages. No private log contents are committed.
- NVIDIA mismatch persists: loaded `610.57.04`, installed userspace `615.71.09`.
  DKMS modules exist for installed 7.2.7 standard/Zen kernels, but the running
  kernel is 7.1.11 standard Arch. No reboot/boot/package change was performed.
- Ollama and its 4.7 GB Qwen model were preserved. No model download or Ollama
  reinstall. Approximately 15 GiB usable RAM; during probes 5.8–6.0 GiB remained
  available with the model loaded. This is a sample, not a peak-memory trace.

## Measured latency

Synthetic local requests, one client, CPU-only, eight threads, temperature zero,
32 output-token cap for simple baseline; 64 for protocol-prompt comparisons.
Streaming probes measure first nonempty text arrival; production replies still
buffer the full model response. Ollama duration fields are nanoseconds, converted
here to seconds; see [Ollama's metrics](https://github.com/ollama/ollama/blob/main/docs/api/usage.mdx).

| Probe | Load s | Prompt s | Generation s | First text s | Wall s |
|---|---:|---:|---:|---:|---:|
| Simple prompt, 4096 context, first cold request | 5.823 | 0.782 | 1.609 | 6.610 | 8.220 |
| Same prompt, warm repetition | 0.001 | 0.079 | 1.579 | 0.085 | 1.665 |
| Same prompt, second warm repetition | 0.001 | 0.084 | 1.567 | 0.090 | 1.658 |
| Switch to 2048 context, model reload | 8.937 | 0.755 | 1.619 | 9.696 | 11.318 |
| 2048 warm repetition | 0.001 | 0.078 | 1.588 | 0.083 | 1.673 |
| 2048 second warm repetition | 0.001 | 0.083 | 1.617 | 0.088 | 1.707 |
| Previous full protocol, 392 prompt tokens | 3.654 | 6.912 | 1.754 | 10.573 | 12.327 |
| Previous protocol, warm cached repetition | 0.001 | 0.082 | 1.763 | 0.089 | 1.852 |
| Compact protocol experiment, 235 prompt tokens | 4.329 | 4.366 | 1.177 | 8.700 | 9.877 |
| Compact protocol, warm cached repetition | 0.001 | 0.086 | 1.171 | 0.092 | 1.263 |
| Final bilingual protocol, 247 prompt tokens, explicitly cold | 9.360 | 4.510 | 1.823 | 13.875 | 15.698 |
| Final bilingual protocol, warm repetition | 0.001 | 0.078 | 1.817 | 0.084 | 1.901 |

Uncached prompt processing fell about **35%** for the final protocol versus the
old protocol; cold load varied substantially and remains a major cost. These are
small samples, not a controlled statistical benchmark. Shorter warm total time
in the compact experiment also reflects fewer generated tokens (16 versus 23).
Generation stayed around **13 tokens/second**. Lowering context did not improve
warm speed here, so no saved context setting was changed. Warm identical prompts
benefit from cache and are not representative of every new conversation turn.

`/api/ps` reported `size_vram=0`, confirming these requests used CPU. Loaded
model allocation was 5,062,566,870 bytes at 4096 context and 4,943,029,206 at 2048.
**GPU peak VRAM and an enforced 8 GB ceiling are not verified.** Never infer GPU
readiness merely from a loaded driver name. Current hardware policy remains an
estimate, not resource isolation; other Ollama clients bypass the REgenOS lock.

No measured recognition, Piper synthesis or time-to-first-audible-response is
reported: assets are intentionally deferred. Source review identifies potential
voice delays: fixed capture duration (default eight seconds), complete model
reply before speech, and a fresh Piper process for each sentence. These are
architectural observations, not measured speech performance. Raw microphone and
synthetic WAV transport passed earlier; they do not establish speech readiness.
The core makes one inference POST per turn, plus inventory/profile checks;
there is no complete result-grounded multi-tool planning loop yet.

Reproduce (existing model only; do not run alongside another inference client):

```bash
cd ~/src/ai-os
~/.ai_os/venv/bin/python -m ai_os.latency_probe --cpu --cold --trials 3
~/.ai_os/venv/bin/python -m ai_os.latency_probe --cpu --context 2048 --trials 3
```

`--cold` unloads only the selected model from RAM, never deletes it. The probe
prints metrics and allocation metadata only, no prompt/response/private history.
It keeps the model loaded for two minutes; it does not edit runtime preferences.

## Connected entry points and memory

```bash
cd ~/src/ai-os
~/.ai_os/venv/bin/regenos-settings
# Or use the terminal integration, with a persistent named session:
~/.ai_os/venv/bin/python -m ai_os.ai_os_core --session personal
```

The native window has nine pages: conversation, companion, AI connection,
hardware policy, voice, memory, appearance, desktop and permissions. Background
system actions still fail closed without human terminal approval. This is not a
privileged native approval broker. Native chat uses a bounded Python child,
keeps the UI responsive, and cancels/reaps its child on cancellation/window close.
A 150-second UI deadline cancels a stuck request; cancellation cannot undo already
completed actions or memory writes. It does not stop the independent core service.

Recent turns persist in `~/.ai_os/data/private/conversations.sqlite3`; default
session is shared by terminal/voice/default native session. Named sessions isolate
recent and older-turn retrieval. Explicit preferences and curated notes are shared
across sessions. Limits: 2,000 total turns, default 30-day retention, 12 recent
turns considered for prompt context, 256 notes, 64 explicit preferences. Expiration
is enforced on history access/write, not by a timer while the application is off.

Retrieval is local lexical matching, not embeddings or training. It adds relevant
notes and older turns within the selected session, plus bounded explicit
preferences. Memory has a conservative character budget reduced by current
message/system-prompt size; this is **not exact tokenizer accounting**. Very long
messages, multilingual token density and output headroom require further tuning.

Memory is local by default. Saved context is excluded from remote provider
requests unless separately approved with `memory_allow_remote`. Disabling memory
stops automatic retrieval/writes; it does not erase existing data. No automatic
model tools may write explicit preferences/notes. Common credential-like turns
are skipped by a heuristic, not a complete sensitive-data classifier. Avoid
entering secrets. Voice transcripts/responses are no longer printed to daemon
logs; local activity files contain presentation metadata rather than conversations.

In Settings → Memory, use Inspect, Remember preference, Save context note, Forget
matching text, Clear selected session, or Clear all active memory. Inspection is
explicit; memory is not displayed automatically at launch. Deletion requires a
native confirmation. Forget removes matching turns as well as notes/preferences;
a revision check prevents an in-flight response from restoring records after a
forget/clear operation. Already displayed or submitted text cannot be retroactively withdrawn;
close/reload other clients after forgetting. Existing backups and older habit/event/Chroma stores are
separate and are **not** erased by these controls. Review those separately before
claiming complete removal from all storage; backups may reintroduce forgotten data.

Equivalent terminal controls (values read from stdin to avoid shell history;
finish interactive input with Ctrl+D):

```bash
~/.ai_os/venv/bin/python -m ai_os.memory_cli --session personal inspect
~/.ai_os/venv/bin/python -m ai_os.memory_cli sessions
~/.ai_os/venv/bin/python -m ai_os.memory_cli remember response_style
~/.ai_os/venv/bin/python -m ai_os.memory_cli note 'Project context'
~/.ai_os/venv/bin/python -m ai_os.memory_cli forget
~/.ai_os/venv/bin/python -m ai_os.memory_cli --session personal clear-session --confirm
~/.ai_os/venv/bin/python -m ai_os.memory_cli clear-all --confirm
```

Do not redirect inspect output into the repository or share it as a diagnostic log.

## Evidence and remaining acceptance

- **108 passed, 1 skipped** in the final Python/Qt suite; skipped cursor conversion.
  Native cancellation, memory confirmation, session separation, cross-process
  persistence, long-term lexical retrieval, retention/context bounds, remote opt-in,
  migration backup and in-flight forgetting are covered by regression tests.
- Real Ollama, synthetic temporary memory: follow-up from a fresh Python process
  recalled the fictional codename. Forget deleted two turns; another fresh process
  did not repeat it. This validates a simple case, not arbitrary recall reliability.
- Real XWayland native window: conversation request completed through the Python
  bridge; all nine pages exist. Detailed manual usability and long-session testing
  remain pending. No real private conversations were seeded or migrated.
- Whisper language and Hindi Piper routing are unit-tested only. Models, Hindi/
  English quality, Romanized Hindi and mixed-language speech remain pending.
  Emotions/moods are simulated presentation state, not consciousness or training.
- Correctness lint `E4,E7,E9,F` passes. Full default Ruff still has 17 pre-existing
  findings; no full-lint-clean claim. The [100-item audit](IMPLEMENTATION_CHECKLIST.md)
  lists every source checklist item and its remaining dependencies.

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests
git diff --check
```

## Backup and rollback

No privileged installs, boot, firewall, AppArmor, disk or model-file changes were
made. Runtime settings and existing habits remain unchanged. No service was enabled.
Before future migrations, stop REgenOS clients and back up affected data:

```bash
~/.ai_os/venv/bin/python -m ai_os.runtime_backup
```

The helper copies config/habits/slang and uses SQLite's backup API if a database
exists. It never copies models or recordings. Old conversation schemas are backed
up automatically before adding new memory tables. Preserve backups privately.

To roll back source after publication, review `git log`, then `git revert` the
specific checkpoint commit(s), preserving unrelated work; never reset/force-push.
Refresh editable metadata with the same no-dependencies command if entry points
changed. The original commit's C++ launcher is not usable without its separately
built executable; use `python -m ai_os.native_settings` to access retained Python
Settings if reverting the launcher repair.

Only if restoring runtime data is actually needed: close Settings, stop the user
service if running, back up the current state again, then explicitly copy selected
files from the private backup to their original locations. For SQLite, close all
clients and restore `conversations.sqlite3` to `data/private/`; do not restore into
a live connection. Keep directory mode 0700 and files 0600. Restoring old memory
can undo forgetting and discard newer turns. This session's initial backup had no
conversation database because none existed. Do not delete data to simulate rollback.
