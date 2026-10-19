# Voice enrollment, reply language and voice choices

2026-10-19: implemented with automated tests; personal voice matching is not yet
hardware verified. Existing assets are multilingual `ggml-base.bin`, English
`en_US-lessac-medium.onnx` and Hindi `hi_IN-pratham-medium.onnx`.

## Setup and recognition

Open **Settings → Voice & listening → Set up / test my voice…**. Select a compatible
local speaker embedding ONNX model first. The optional `speaker` dependency uses
[sherpa-onnx's speaker API](https://k2-fsa.github.io/sherpa/onnx/speaker-identification/).
It is separate from Whisper transcription and Piper synthesis. No model or backend
is downloaded by setup. The current venv lacks sherpa-onnx and no speaker model or
profile has been provisioned; Record is unavailable until those prerequisites exist.
The pip resolver dry run found compatible CPython 3.14 wheels for sherpa-onnx 1.13.8
and sherpa-onnx-core 1.13.8. This is dependency resolution, not installed validation.

The wizard requires explicit recording consent, four seven-second samples with
different natural styles/languages, a fresh fifth verification, and Save. Record
is always a deliberate click. Cancel kills/reaps the recording/extraction worker
and removes temporary WAVs. Raw recordings are not saved. The normalized embedding
and encoder SHA256 live in `~/.ai_os/data/private/speaker/speaker-profile.json`
(directory 0700, file 0600). Treat the embedding as private personal data.

Saving a profile does not enable filtering or listening. Enable **Respond only to
my enrolled voice** separately and approve the native confirmation. Disable it in
the same place; Delete profile is available in setup. An enabled filter with a
missing/stale profile, backend failure, malformed result or ten-second verification
timeout rejects the utterance before transcription. Matching starts a bounded
local worker for each utterance; this adds unmeasured startup/inference overhead.
The status indicator shows the saved state and sanitized last result.

This is conversation filtering, not fingerprint-grade authentication. Similar
voices, replay and synthesis may pass. Voice never confirms commands, sudo,
permissions, account access, screen sharing or login. No PAM integration is added.
Threshold 0.75 is an uncalibrated starting preference, not an accuracy guarantee.

## English and Hindi replies

**Reply language → Match each message (English / Hindi)** uses multilingual
Whisper's JSON `result.language` per utterance. Unsupported/unknown detection asks
for clarification before any action. The selected recognition language remains
the fallback. **Use the selected language** preserves the previous behavior.
Typed matching uses the model's interpretation of the current message, including
clear Romanized Hindi, rather than guessing from Unicode script or older history.

Synthetic installed-asset smoke: English detected `en` and transcribed correctly;
Hindi detected `hi` but base Whisper emitted Urdu-script text with recognition
errors. Language metadata plumbing works; Hindi transcription quality is still a
known blocker. No new Whisper model was downloaded. Real speech, accents, short
utterances, code switching, false admission/rejection and end-to-end latency need
user acceptance. Two local synthetic model turns replied in English and Hindi;
that does not establish consistent fluency.

## Better voices and your own voice

| Option | Appropriate use | REgenOS status |
| --- | --- | --- |
| [Piper voices](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md) | Lightweight offline voices. Download both `.onnx` and `.onnx.json`; review each voice's model card/license and audition it first. | Existing adapter; independent English/Hindi voices generally sound different. |
| [Chatterbox Multilingual V3](https://huggingface.co/ResembleAI/chatterbox) | Recommended candidate for one reference voice across English and Hindi. Its model card lists multilingual voice cloning and MIT licensing. | Recommendation only; needs a separate synthesis adapter and compatibility/VRAM/latency tests. |
| [XTTS-v2](https://huggingface.co/coqui/XTTS-v2) | Cross-language cloning including English/Hindi from short reference audio; multiple reference clips supported. | Alternative; review the Coqui Public Model License before distribution/commercial use. No integration yet. |

Chatterbox/XTTS weights cannot be selected as a Piper ONNX file. The installed
runtime uses Python 3.14; inspect the chosen engine's supported Python/dependencies
before proposing a separate isolated environment. Do not replace this venv or
assume simultaneous Ollama and TTS fit the RTX 4060's 8 GiB. Peak VRAM, streaming,
audio quality and cancellation must be measured with the final selected assets.

To use your own voice, record clean, dry reference clips in a quiet room using
your normal English and Hindi voice. A practical audition set is several short
clips with different sentences and pacing. Keep them private and use local
inference rather than uploading to a demo. Speaker enrollment's five samples do
not train a TTS pack and are intentionally deleted. Voice cloning conditions an
existing model; fine-tuning a pack is a separate workflow.

For a lightweight Piper pack, follow the official
[training guide](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/TRAINING.md):
prepare clean WAVs paired with exact transcripts, choose the language/phonemizer,
fine-tune an appropriate checkpoint, then export ONNX plus its JSON configuration.
Dataset quantity, pronunciation and bilingual consistency need evaluation; a few
enrollment phrases are not a claim of sufficient training data. Nothing here
automatically records, trains, downloads, publishes or redistributes your voice.

Launch setup directly if needed:

```bash
~/.ai_os/venv/bin/python -m ai_os.speaker_setup
~/.ai_os/venv/bin/python -m ai_os.runtime_health
```
