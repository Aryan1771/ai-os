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
No transcript appears until the whole diagnostic completes. An empty-results
placeholder now explains this, and the status has a named, minimum-height area.

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
