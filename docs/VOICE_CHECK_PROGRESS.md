# Guided voice progress and recorder closure

2026-10-21 source checkpoint. The owner reported a voice check appearing to stay
in Listening without a transcript. Source inspection found two concrete problems:
the dialog kept its initial microphone-on label throughout STT/model/speech, and
the one-shot recorder stayed alive until transcription returned. Neither finding
proves why a particular personal recording failed; no recording, private output,
owner screen or private log was inspected.

One-shot capture now terminates and reaps its owned recorder after a validated
ending pause, before speaker filtering, temporary WAV processing or Whisper.
Only a confirmed integer process-exit result permits a microphone-off indication
and processing. Failed reaping stops the request before filtering/STT. Cancellation
after the completion hook still rejects the utterance. The hook never sets the
listener cancellation flag on normal completion. Continuous listening retains its
existing recorder lifecycle. The companion switches from Listening to its existing
audio-processing phase after one-shot reaping.

The native check now starts with **Preparing**, then receives phase-only progress:

| Stage | Display |
| --- | --- |
| Input metadata / readiness | Microphone has not started |
| Recorder started | Waiting for speech |
| Speech detected | Recording, with current/required quiet pause |
| Recorder reaped | Microphone off |
| Optional filter / Whisper / model | Microphone off, with the current processing stage |
| Piper / playback | Microphone off, preparing or playing reply |

The existing default five-second ending silence is unchanged. Energy above the
existing threshold restarts the pause, including background noise; the displayed
pause helps distinguish that from STT latency. No adaptive gain, calibration, new
VAD threshold, language-model selection or inference speedup is claimed.

Only the native UI's worker adds `--progress`. That optional mode emits fixed
phase/numeric JSON lines followed by the unchanged final result object. Legacy
worker invocations still produce one final JSON object. Repeated phase updates
are throttled to four per second and reporters cap events; Qt retains the 64 KiB
total-output limit even after consuming progress lines. Split lines are buffered;
unknown fields, invalid phases and nonfinite/invalid numbers are rejected. Progress
contains no transcript, reply, RMS, source identifiers, paths or command arguments,
and is not sent to models or written to logs/history. Final text remains only in
the explicitly opened local diagnostic window as before.

The dialog retains its 110-second overall stop timer, explicit consent and Record
click, speech lease, verified owned-process-group cancellation and temporary-data
cleanup. Progress does not extend that deadline. It can expire before a slower
stage's separate maximum; that is an overall cancellation, not a successful check.
At this checkpoint the transcript appeared only after the whole diagnostic
completed. The early-text follow-up below supersedes that behavior. The status
has a named, minimum-height area.

An independent isolated audit checked 20 theme/size/font combinations and did not
reproduce missing status/details. New graphite/light tests at 680×540 and 480×320
verify that initial status and the result area are visible below the buttons.
These findings do not establish what was displayed in the owner's existing window.
No owner window was closed or reset to test the change.

A separate isolated rendering check demonstrated that the primary button ID
selector kept disabled Record controls blue in all five themes. The disabled
rule now explicitly includes `QPushButton#primary:disabled`; it shows the normal
disabled surface until consent enables recording. Twelve native UI tests pass
and all five enable/disable color transitions were checked without starting a
worker. Existing windows need reopening to load that stylesheet; this does not
establish the cause of the owner's missing result.

Validation uses synthetic PCM, fake processes, fake models and isolated native
windows only:

```bash
env -u DISPLAY -u WAYLAND_DISPLAY QT_QPA_PLATFORM=offscreen REGENOS_HUB_NO_COMPANION=1 ~/.ai_os/venv/bin/python -X faulthandler -m pytest -q tests/test_voice_progress.py tests/test_voice_diagnostics.py tests/test_voice_endpointing.py tests/test_voice_stage_timings.py tests/test_listener.py tests/test_voice_listener_recovery.py tests/test_audio_input.py tests/test_native_ui.py --tb=short
~/.ai_os/venv/bin/python -m ruff check ai_os/voice_progress.py tests/test_voice_progress.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/voice_diagnostics.py ai_os/services/listener.py ai_os/services/voice_input.py
git diff --check
```

The new module contains 31 cases, including recorder ordering, kill/reap failures,
invalid exit evidence, cancellation races, incomplete input, continuous capture
preservation, protocol privacy/throttling/bounds, legacy result compatibility and
native layout. The final frozen eight-module run passes **219 tests in 5.11s**,
including the recorder-off companion-phase assertion. Both lint checks and
whitespace checks pass.
Root's combined frozen suite passes **1321 tests in 16.57s**, normal exit. A
caption-only correction escapes Qt mnemonic ampersands so the button/consent
render the literal `Record & reply`; the 31-case suite passes again in 0.28s.
Automated validation started no actual microphone, playback or model request,
and changed no user preference or service.
Personal English/Hindi accuracy, reply relevance, audibility and measured latency
remain owner acceptance.

Root's frozen combined validation after the latest-status addition passes
**1352 tests in 16.66s**, normal exit, with correctness lint/whitespace clean.
The read-only live reader initially reports `unavailable`; no new explicitly
requested check had populated it. This is not a failed recording or voice pass.

The owner's next explicit Record produced sanitized phases waiting → capturing
→ cancelled. Metrics: speech-detection wait 0.601s, captured PCM 16.48s, capture
wall time 16.025s, total 16.634s. No completed ending-pause, STT or model stage was
reported. The input stream worked and crossed the speech-energy threshold; this
does not identify the source or verify spoken words. The check was cancelled
before a completed quiet pause, with no recording/transcript read by the agent.
Whether the then-labelled Stop button or closing caused that cancellation was
not established. The control is now named **Cancel check** and cancels/discards;
it is not an explicit finish-and-transcribe control.

A later, separate owner check completed in 22.224s: ending quiet 5.04s, STT
4.626s, model 2.384s, synthesis 1.313s and playback 6.339s. The owner heard a reply
but reported no transcript, motivating the early private-text display below.
The earlier cancelled result does not describe this completed attempt. No owner
words or recording were read by the agent.

## Latest check metadata without reading a recording or window

Every explicitly confirmed diagnostic worker now replaces one sanitized current
snapshot at `~/.ai_os/run/private/voice-check-status.json`. This applies to both
older final-JSON-only dialogs and newer phase-progress dialogs on their **next
explicit Record or Play click**; it does not require another GUI/service restart.
Opening a dialog or enabling its consent checkbox creates no worker/snapshot.
Legacy worker stdout remains a single final JSON object unless `--progress` is
explicitly requested.

The safe, read-only command is:

```bash
~/.ai_os/venv/bin/python -m ai_os.voice_check_status
```

It returns `fresh`, `stale` or `unavailable`. Fresh metadata contains only version,
the `play`/`record` action, a fixed phase, fixed error code, bounded numeric stage
timings, and start/update timestamps. Terminal phases are `completed`, `failed`
or best-effort `cancelled`; `utterance_too_long`, for example, distinguishes a
missing ending pause from transcription/model errors. There are no messages,
transcripts, replies, RMS, device/account identifiers, process IDs, paths or model
arguments in the snapshot. Raw files or private subprocess logs are unnecessary.

An existing 0755 runtime/run directory stays unchanged. The private child must
be owned and 0700; snapshot and its fixed lock must be owned private regular files
with one link. Directory-descriptor operations, no-follow opens, bounded schema/
size checks and atomic replacement reject unsafe existing paths without chmod or
following links. Only the latest check is retained; a superseded worker cannot
overwrite its successor, even when wall-clock readings are equal. No history or
audio log is created. Missing/unsafe storage makes this optional metadata
unavailable while ordinary explicitly requested diagnostic behavior is preserved.

The reader creates nothing, never returns malformed/raw content, and omits stale
records after 180 seconds. A fresh phase identifies the latest recorded stage;
it does not prove that a worker is still alive, microphone access is allowed,
audio was useful or playback was heard. Forced SIGKILL/power loss can leave the
last phase until it expires. Normal TERM cancellation publishes `cancelled` where
the worker can unwind safely. Timestamps help distinguish the latest click from
an earlier result. Reader errors print only `unavailable`.

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_voice_check_status.py tests/test_voice_progress.py tests/test_voice_stage_timings.py --tb=short
env -u DISPLAY -u WAYLAND_DISPLAY QT_QPA_PLATFORM=offscreen REGENOS_HUB_NO_COMPANION=1 ~/.ai_os/venv/bin/python -X faulthandler -m pytest -q tests/test_voice_check_status.py tests/test_voice_progress.py tests/test_voice_diagnostics.py tests/test_voice_endpointing.py tests/test_voice_stage_timings.py tests/test_listener.py tests/test_voice_listener_recovery.py tests/test_audio_input.py tests/test_native_ui.py --tb=short
~/.ai_os/venv/bin/python -m ruff check ai_os/voice_check_status.py tests/test_voice_check_status.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/voice_diagnostics.py tests/test_voice_progress.py tests/test_voice_stage_timings.py
git diff --check
```

The focused run passes **90 tests in 0.48s**, including 31 new metadata cases:
schema/privacy omission, freshness, concurrency, unsafe permissions/owners,
symlink/hardlink/FIFO/size/read failures, confirmed old/new UI paths, cancellation
and unconfirmed-worker denial. Existing worker tests now explicitly isolate their
metadata homes in temporary directories. No personal runtime status, recording,
configuration or log was read; no microphone/playback/model/service was started.
The final combined nine-module headless run passes **250 tests in 5.13s**, normal
exit; new-file Ruff, edited-file correctness lint and whitespace checks pass.

## Early private transcript and reply display

The owner subsequently completed a real recording and heard a reply, but reported
no visible transcript. That establishes a display concern rather than proof of
missing microphone permission. Earlier source displayed all text only after
playback ended, and closing the dialog cleared it. No owner transcript or private
audio was read to investigate.

The native dialog now requests a separate `--ui-text` channel. Recognized words
appear immediately after successful STT/language validation; the local reply
appears after model processing, **before Piper/playback starts**. These private
events have a separately named `on_ui_text` callback and strict `voice_ui_text`
schema. They never enter the public phase callback, current-status snapshot,
history, logs or remote providers. Ordinary worker invocations retain their prior
single final JSON response; the GUI-specific final summary omits duplicate text.

The plain native result box retains already validated text if speech fails or
the owner chooses **Cancel check**. Starting another check clears it, and closing
clears both the widget and its private text/timing fields. Cancel still discards
the ongoing operation; it is not a manual ending-pause command. No manual Finish
recording action was added. The 110-second overall bound, per-Record consent,
tool-free processing, speech lease and owned-group cancellation are unchanged.

Only `transcript`/`reply` events with exactly the defined fields are accepted.
Transcript limits are 8000 characters and 16384 UTF-8/serialized-JSON text bytes;
reply limits are 2000 characters and 8192 such bytes. JSON escape expansion counts
toward those budgets. UTF-8 framing avoids multiplying Hindi text into ASCII
escape sequences. Each kind is emitted once; the two text events leave room for
the bounded diagnostic phase updates and final summary within the existing
64 KiB stream cap. Fragmented UTF-8 and coalesced lines are supported; invalid,
oversized, unknown-field or duplicate events stop without displaying rejected
content. Text uses `setPlainText`, with no HTML or executable interpretation.

Worker stdout/finish/start/error callbacks are bound to their specific QProcess;
late events from a cancelled worker cannot write into or finish its successor.
An early private callback failure aborts before later model/speech stages, and
unrecognized language never emits unverified words. Reached valid text remains
visible on cancellation or final-result failure, until the next check/close.

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_voice_ui_text.py --tb=short
env -u DISPLAY -u WAYLAND_DISPLAY QT_QPA_PLATFORM=offscreen REGENOS_HUB_NO_COMPANION=1 ~/.ai_os/venv/bin/python -X faulthandler -m pytest -q tests/test_voice_ui_text.py tests/test_voice_check_status.py tests/test_voice_progress.py tests/test_voice_diagnostics.py tests/test_voice_endpointing.py tests/test_voice_stage_timings.py tests/test_listener.py tests/test_voice_listener_recovery.py tests/test_audio_input.py tests/test_native_ui.py --tb=short
~/.ai_os/venv/bin/python -m ruff check ai_os/voice_ui_text.py tests/test_voice_ui_text.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/voice_diagnostics.py
git diff --check
```

Synthetic tests cover stage ordering, private/public separation, unchanged legacy
output, byte/escape limits, split/coalesced framing, speech errors, cancellation,
late callbacks, close cleanup and plain-text rendering. Independent read-only
review additionally checked eight encoding-boundary examples. No actual
recording, playback, model request, owner window or private data was used.
The final combined ten-module headless run passes **286 tests in 5.22s**, including
36 new private-text cases; new-file Ruff, edited-file correctness lint and
whitespace checks pass, with normal interpreter exit.
Fresh native-window transcript visibility and spoken-word correctness still
require owner acceptance after the automated checks.

Root's frozen full-suite command from [RUNTIME_VALIDATION](RUNTIME_VALIDATION.md)
passes **1388 tests in 16.86s**, normal exit, including the six explicitly supplied
pinned Plymouth interpreter checks. Correctness lint and whitespace pass. A new
dialog loads the early-text code; no resident-service restart is required.
