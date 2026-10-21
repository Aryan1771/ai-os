# Explicit microphone selection

2026-10-21 source checkpoint for part of A049. Implemented and fake-tested; no
physical microphone, USB/Bluetooth reconnect or noise acceptance is implied.

Voice & listening now offers **Microphone input** and **Refresh inputs**. Opening
Settings performs no new input discovery or recording. Refresh explicitly runs
an asynchronous, four-second metadata query, with a 4 MiB combined output limit,
4096-node parser limit and at most 128 accepted sources. The UI stays available
while the query runs, shows busy/result/failure status, and stops its own query
when closed. Only `Audio/Source` nodes with supported bounded stable node names
are selectable; sink monitors and streams are excluded. Device-provided labels
stay in the local native form, with control/bidi characters removed. They do not
enter a model, tools, memory, speech, logs or reports.

The default remains `voice_input_target: ""`: use the existing system-default
microphone without a discovery requirement. Choosing another input is a protected
setting requiring native human confirmation even when the general settings lock
is off. Selection does not enable listening, wake activation or speaker filtering,
change the system default/gain, record sound, or download anything. Save applies
the choice to the next one-shot/enrollment capture or the already enabled worker's
ordinary settings reload. Unsaved/missing choices survive refresh; Revert restores
the saved choice. A model cannot approve a microphone change.

An explicit saved input is checked again immediately before every recorder starts:
continuous listening, Speak once/guided/report capture, and speaker enrollment.
Malformed/unavailable selections stop before recording with a public error and
never select another input automatically. Discovery's bounded single `pw-dump`
child stays in its calling voice worker's process group, so task cancellation also
covers that query; timeout/output-cap handling kills and reaps only its own child.
No group-wide signal is introduced. The native asynchronous query has separate
bounded Qt process ownership.

Explicit streams use `--target` plus fixed `node.dont-fallback`,
`node.dont-reconnect` and `node.dont-move` properties. This matters because naming
a target alone does not forbid fallback or movement. See the official
[pw-cat options](https://docs.pipewire.org/page_man_pw-cat_1.html) and
[PipeWire session-manager properties](https://docs.pipewire.org/page_man_pipewire-props_7.html).
No arbitrary stream properties or shell syntax are accepted from the model/user.
16 kHz signed-16-bit mono, the five-second default ending silence, leases,
endpointing, filtering and feedback suppression are preserved. Default recorder
argv is unchanged.

Speaker enrollment also checks an explicit input asynchronously after each
consented Record click. The shared audio lease remains held while checking;
Cancel stays available, and no recorder, temporary audio directory or profile
write occurs before success. The four-second/4 MiB query uses the same bounded
parser, then passes that current inventory directly to argv construction without
a second synchronous query. A changed target, speaker model/threshold, listening
mode, model file or revoked consent aborts before capture. Cancel/failure clears
metadata, releases the lease and ignores late callbacks. The default-input path
still starts directly without discovery. Fake event-loop callbacks verify that
the GUI continues processing while an explicit-input check is pending.

Readiness now reports sanitized explicit/default selection and selected-source
presence. An explicit input never borrows the default input's mute status:
`microphone_mute_check` is `not_checked_for_explicit_input`. Missing/uncheckable
selected inputs block readiness. Presence alone does not prove routing, mute/gain,
audio quality or recognition. The bounded recorder still detects a stalled/exited
stream; the supervisor retries only a listening mode already explicitly enabled.
Unplug/replug routing and property enforcement require physical acceptance.

Validation (no actual audio, personal config, model inference, service change or
host input inventory):

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_audio_input.py --tb=short
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q tests/test_audio_input.py tests/test_listener.py tests/test_voice_settings.py tests/test_voice_endpointing.py tests/test_speaker_setup.py tests/test_voice_runtime_readiness.py tests/test_voice_diagnostics.py tests/test_voice_stage_timings.py tests/test_voice_reply_grounding.py tests/test_voice_listener_recovery.py tests/test_desktop_context.py --tb=short
~/.ai_os/venv/bin/python -m ruff check ai_os/audio_input.py tests/test_audio_input.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/config.py ai_os/settings_store.py ai_os/native_settings.py ai_os/services/listener.py ai_os/services/voice_input.py ai_os/runtime_services.py ai_os/speaker_setup.py ai_os/services/voice_errors.py ai_os/runtime_health.py
git diff --check
```

The initial new suite passed **50 tests** and eleven-module combined run passed
**209 tests in 1.69s**. A review caught synchronous enrollment discovery on the GUI
thread; the asynchronous correction adds cancellation/config-drift coverage.
The final suite contains **64 tests**; the final eleven-module run passes
**223 tests in 1.80s**, and the audio-input/enrollment-only run passes **77 tests
in 1.35s**. Both lint checks and whitespace checks pass. Installed command help
confirms support for `pw-record --target` and `pw-dump --no-colors`; no capture was
started to validate those flags.

A049 remains incomplete: gain/noise/clipping calibration, laptop-specific VAD,
physical device removal/reconnect and actual selected/default microphone behavior
remain pending. The fixed RMS speech threshold is unchanged; automatic mic
switching or noise calibration is not silently enabled.
