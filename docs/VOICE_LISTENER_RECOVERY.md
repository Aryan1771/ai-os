# Recovery after a rejected voice utterance

An expected transcription rejection used to escape the resident capture loop.
For example, multilingual base could reject a Hindi recording with
`transcription_script_mismatch`; the worker then exited and its supervisor waited
15 seconds before retrying. That rejection protected action planning, but the
worker restart added avoidable dead time before the next utterance.

The capture loop now catches `VoicePipelineError` from that utterance alone. It
reports the same public error through the existing callback, applies the existing
15-second limit to repeated errors with the same code, discards captured backlog,
resets wake detection and the speech pre-roll, and resumes its existing armed
mode. A changed error code is reported immediately. Rejected and incomplete text
never reaches the conversation or command handler. The configured wake-word
requirement, echo-tail suppression, shared speech handling, timing preferences and
consent controls are unchanged.

Recorder stalls, recorder transport failures and unexpected backend exceptions
remain fatal so the supervisor can clean up and retry the broken worker. Errors
from processing an accepted transcript are outside this capture-only recovery.
One-shot and guided diagnostics still return their explicit failure to the person
who requested that recording; this change does not silently retry a recording.

## Source verification

```sh
~/.ai_os/venv/bin/python -m pytest -q tests/test_voice_listener_recovery.py tests/test_listener.py tests/test_voice_endpointing.py tests/test_voice_runtime_readiness.py --tb=short
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/services/listener.py tests/test_voice_listener_recovery.py
```

Result on 2026-10-20: **39 tests passed**, including 14 new recovery tests. The new
tests feed synthetic PCM to the real endpointing loop with a fake recorder and
transcriber. They cover rejected Hindi/metadata/timeouts followed by a successful
English utterance with one recorder, rejection of an unfinished request, retention
of the wake requirement, discard/reset order, error-rate limits, fatal transport
failures before and during capture, unexpected backend exceptions, and temporary
WAV removal. No microphone, speaker output, model inference, download, personal
configuration, voice profile, private conversation or service was used or changed.

## Acceptance still required

This repairs listener recovery; it does not improve Whisper's Hindi recognition
accuracy. The previous fixed public-phrase comparison found base Hindi script
failures and inaccurate small-model Hindi despite CUDA acceleration; see
[VOICE_MODEL_COMPARISON](VOICE_MODEL_COMPARISON.md). The selected model remains
unchanged. Do not bypass the script guard, guess a transcript or substitute the
model solely because a synthetic script check passes.

After this source checkpoint is reviewed and loaded through the separately
approved runtime process, the owner still needs the explicit guided
microphone → transcription → local reply → playback check in each chosen
language. Check relevance and audibility against what was actually said; record
only sanitized timing/error categories. Real continuous-listener recovery needs
its own visible opt-in and stop check. Nothing in this source test enables it.
The chosen five-second ending pause is intentional waiting; compare it separately
from transcription, model loading/generation and playback before changing latency
settings. No physical voice acceptance is claimed here.
