# Guided voice stage measurements

The guided native voice check now separates capture, recognition and output
timing. This is diagnostic instrumentation, not a claim of lower real-world
latency or improved Hindi accuracy. It changes no saved timing, model, voice,
language, listening, consent or service setting. Resident/default capture and
speech calls supply no collector and store no timing record.

Open **Settings → Voice & listening → Guided voice check…** only when an owner
wants an explicit check. Opening the dialog and checking consent do not start
recording. Each **Record & reply** click still needs consent, continuous
listening off and spoken replies enabled. **Play test voice** never records or
calls the conversational model. This source checkpoint performed neither check
with real audio.

## Meaning of the fields

All fields are seconds, rounded to three decimal places. Wall-clock measurements
use a monotonic clock. A missing field means that stage was not reached or no
valid measurement was available; it does not mean the stage took zero seconds.

| Field | What it measures |
| --- | --- |
| `speech_detection_wait_seconds` | From starting the recorder stream wait until three speech frames satisfy the existing gate. Includes detection debounce; this is not an exact measurement of the first spoken phoneme. On a no-speech failure it measures the completed wait. |
| `capture_seconds` | Wall time in the utterance capture loop, from the existing pre-roll handoff to endpoint, cancellation or capture failure. Includes the ending pause; excludes filtering and STT. |
| `captured_audio_seconds` | PCM samples in the captured window divided by sample rate, including pre-roll and the full ending pause before trimming. This is audio duration, not another wall-clock stage. |
| `ending_silence_audio_seconds` | Final contiguous quiet PCM duration when the configured endpoint is actually reached. Frame rounding may produce 5.04s for a requested 5s. Absent for incomplete or cancelled captures. |
| `speaker_filter_seconds` | Wall time in the existing optional filter call, including its config check and subprocess when enabled. A quick disabled-filter return is not speaker verification. |
| `stt_seconds` | Wall time around the complete Whisper adapter call, including CLI/model startup and result parsing, even when it returns a rejection. |
| `synthesis_seconds` | Wall time in Piper, including model startup. If one collector is explicitly reused for several sentences, their synthesis durations accumulate. |
| `playback_seconds` | Wall time in `pw-play`, accumulated when explicitly measured across sentences. It is absent if playback was never attempted, including cancelled output. Successful exit is not proof of audibility. |

Existing `capture_and_stt_seconds`, `model_seconds`,
`synthesis_and_playback_seconds` and `total_seconds` remain. Ollama's available
`model_load_seconds`, `model_prompt_eval_seconds` and `model_eval_seconds` remain
separate server-reported counters. Total/combined timings include boundary work
outside the individual calls, so component sums need not equal the total.

Do not add PCM durations to wall timings. Pre-roll overlaps the detection wait;
the ending quiet interval is already included in capture. The saved five-second
pause remains intentional waiting and is not silently shortened by this feature.

## Privacy and failure behavior

The optional collector is a fresh in-memory dictionary for one guided check.
Only a fixed allowlist of numeric fields is returned; booleans, strings,
non-finite/negative values, unknown keys and durations above one hour are dropped.
Caller-provided collectors are cleared only once a permitted check acquires its
speech lease and are sanitized before completion or ordinary failure. There are
no wall-clock timestamps, device identifiers, paths, embeddings, raw backend
output or transcript fields in timing data. No timing log, history entry or
configuration key is created.

The native window can display valid reached-stage measurements after failure,
alongside the existing public error. It does not display a failed turn's
transcript or private exception. The normal successful check still shows the
current transcript/reply in that window only. Closing clears the display; a hard
worker cancellation may end before a measurement result can be returned. Existing
recording cleanup, inference/speech leases, Stop and process-group limits remain.

The implementation adds optional `metrics=None` parameters to `capture_once`,
the capture helper and `SpeechQueue.speak_text`. It does not change
`TranscriptionResult`, the speaker backend, Whisper arguments, output voices or
the action-planning harness. A small shared `voice_timings.py` module enforces
the numeric boundary without writing files or starting processes.

## Source verification

```sh
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_voice_stage_timings.py tests/test_voice_diagnostics.py tests/test_voice_listener_recovery.py tests/test_voice_endpointing.py tests/test_voice_reply_grounding.py tests/test_voice_languages.py tests/test_speech_lease.py --tb=short
~/.ai_os/venv/bin/python -m ruff check ai_os/voice_timings.py tests/test_voice_stage_timings.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/services/voice_input.py ai_os/services/listener.py ai_os/speech_queue.py ai_os/voice_diagnostics.py tests/test_voice_diagnostics.py
```

Result on 2026-10-20: **119 focused tests passed in 0.69s**; both Ruff commands and
the whitespace check passed. The new 28 tests use synthetic PCM, an advanced fake clock, fake capture/model
interfaces and fake subprocesses. They verify distinct stage durations, the actual
63-frame/5.04s endpoint accounting, unchanged audio trimming/arguments, failure
and no-speech measurements, omitted unreached stages, sentence accumulation,
numeric filtering, fresh-check isolation, consent preservation and safe native
error display. Existing diagnostic cancellation and lease regressions are also
included in the focused command. No microphone, audible speech, model inference,
download, personal configuration or service operation is needed by these tests.

Next evidence should come from the owner's explicitly requested guided check,
with only sanitized timing/error categories retained. Use those measurements to
decide whether any later optimization should target capture, recognition, model
startup, Piper startup or playback. Hindi recognition still needs acceptance
against what the owner actually said; these counters do not establish accuracy.
