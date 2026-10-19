# Guided local voice check

Open **Settings → Voice & listening → Guided voice check…**, or run:

```bash
~/.ai_os/venv/bin/python -m ai_os.voice_diagnostics
```

The dialog starts with recording consent unchecked and no audio process. It uses
saved settings; unsaved Settings edits are not silently applied. Choose English,
Hindi or detection for the current test. **Play test voice** plays a fixed phrase
without opening the microphone. To test the complete loop, explicitly check the
one-time consent box and click **Record & reply**. Continuous listening must be off
to avoid duplicate capture, and Speak replies must be enabled for the complete loop.

Speak a short sentence, then wait for the saved ending pause (currently five
seconds on this host). Initial speech wait is eight seconds; an utterance has a
20-second limit. The visible activity indicates capture, transcription, thinking
and speech. Stop or closing the dialog cancels the owned worker and audio children.
The GUI also has a 110-second timer. It never signals PID 0 or the desktop's
process group; a verified new worker session is required for group termination.

The result shows what Whisper actually recognized, the local reply and timing.
Only the current utterance and simulated mood guidance go to local Ollama.
There are no tools, automatic computer actions, private conversation retrieval,
remote providers or saved chat. Ordinary hardware admission/CPU overrides and
the inference/speech locks still apply. Diagnostic replies are capped at 96
generated tokens; this does not reduce the main chat's answer budget.
Temporary WAV/Whisper metadata is removed during normal completion/cancellation.
Displayed text clears on close; no acceptance transcript is written to Git/logs.

Model timing separates reported load, prompt evaluation and token generation
when Ollama supplies those counters. Capture/STT and synthesis/playback remain
combined stage measurements. Successful subprocess exits cannot prove audibility,
recognition accuracy or that a reply was relevant; the owner must assess those.

## Actual evidence, 2026-10-19

- Guided dialog launched, consent unchecked; no agent microphone capture.
- A fresh synthetic English Piper→16 kHz→Whisper→local reply→Piper loop completed.
  Initial stage timings: synthesis/resample 1.332s; STT 1.976s; model 14.136s;
  total 19.214s. No audible playback. This motivated tighter diagnostic replies,
  preserving hardware policy, and explicit model timing counters.
- After that change, two synthetic display-question model turns took 3.645s and
  0.420s. Ollama reported load 3.111s/0.001s and generation 0.375s/0.367s; both
  replies were 15 words without the canned feelings disclaimer. Cold/warm and
  prompt-cache effects prevent treating this as a universal speedup factor.
- Synthetic Hindi still produced the known script mismatch with the base model.
  It now fails closed with `transcription_script_mismatch`, retaining no transcript
  for action planning. It was not fixed by guessing a transliteration.
- Whole-GPU peak observed across the sequential synthetic stages: 4701 MiB in
  103 samples (~200ms cadence). This is not simultaneous worst-case VRAM or proof
  of real microphone latency. The previous native greeting sampled 4707 MiB.
- Existing openWakeWord **ONNX** assets and backend load successfully in a bounded
  isolated child, without a microphone. Trained wake detection accuracy remains
  untested. The venv's `pip check` still reports the package's TFLite dependency;
  explicit ONNX selection does not require that backend for this loading test.

Readiness now distinguishes `voice_assets_ready`, `voice_ready`, blockers and
unverified acceptance. It does not load models, record, speak or test recognition.
Continuous-listener speaker failures now surface fixed categorical errors, with
15-second callback rate limiting instead of silently discarding the failure.

Pending: approval for the official multilingual Whisper small comparison
([published file/hash](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-small.bin)),
owner microphone/relevance/audibility checks, real wake/echo/hotplug/recovery tests
and performance with the final selected assets. No new model was downloaded here.
