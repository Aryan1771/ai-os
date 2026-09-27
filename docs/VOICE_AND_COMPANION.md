# Voice, Listening, Companion, And Settings

Current assistant name: **RE**, spoken **R E**. The new experimental local Whisper
wake option and current installed assets/validation are documented in
[RE session and identity](RE_SESSION_AND_IDENTITY.md). The older openWakeWord path
below remains selectable. An installed Jarvis model cannot detect RE by renaming it.

The microphone is disabled by default. When enabled, the pipeline is local:

```text
PipeWire microphone -> openWakeWord -> temporary WAV -> Whisper.cpp -> Ollama -> Piper -> PipeWire speaker
```

The temporary WAV is deleted after transcription. The listener will not start unless both `always_listening_enabled` and `wake_word_enabled` are true.

## 1. Install Models

```bash
cd ~/src/ai-os
bash install/ai-os-install.sh voice
mkdir -p ~/.ai_os/models
```

Download a Whisper GGML model and a Piper `.onnx` voice model from their official upstream releases, verify checksums, and place them in `~/.ai_os/models/`. Update only these paths in `~/.ai_os/config.json` if your filenames differ:

```json
{
  "whisper_model": "models/ggml-base.en.bin",
  "piper_model": "models/en_US-lessac-medium.onnx"
}
```

Confirm microphone capture before enabling the listener:

```bash
pw-record --raw --format s16 --rate 16000 --channels 1 - | head -c 32000 > /tmp/ai-os-mic-test.raw
rm /tmp/ai-os-mic-test.raw
```

## 2. Install Native Settings And Companion

```bash
cd ~/src/ai-os
bash install/ai-os-install.sh native
~/.ai_os/venv/bin/regenos-settings
```

Settings is a native Qt window with model, voice, emotion-bar, companion, appearance and permission controls. The web server has been removed. See [Native Desktop](NATIVE_DESKTOP.md) for migration, offline dependencies, X11/Wayland behavior and login startup.

The separate **Apply desktop appearance** button writes user GTK/Hyprland settings and backs up existing files. Saving unrelated AI or avatar preferences no longer overwrites those desktop files.

Enable **Show corner companion**, then save. To start its resident process manually:

```bash
~/.ai_os/venv/bin/regenos-companion
```

Click the companion to reopen Settings. The same pixels travel between robot expressions, twelve built-in silhouettes and optional model-generated pixel grids. Activity and speech events change its appearance and six simulated emotion channels. The emotion baseline, response strength and motion intensity are editable in Settings.

## 3. Enable Voice Deliberately

In the native panel, enable **Require wake word**, **Listen for wake word**, and optionally **Speak replies**. With sandbox locking enabled, the panel asks for a native protected-settings confirmation.

Restart the daemon after saving:

```bash
systemctl --user restart ai-os.service
journalctl --user -u ai-os.service -f
```

To immediately stop microphone access, disable `always_listening_enabled` in the panel and restart the service, or run:

```bash
systemctl --user stop ai-os.service
```

## 4. Offline Learning And Memory

Do not fine-tune the 7B model first. Start with local memory: permanent habits, temporary overrides, slang vocabulary, event history, and optional Chroma semantic memory. These stay under `~/.ai_os` and `~/.local/share/ai_os/chroma`.

For better long-term behavior, collect only consented, non-sensitive examples in a separate dataset; remove secrets, private documents, and credentials; validate behavior against a held-out test set; then fine-tune a copy of the model on stronger hardware. Never train directly on an unattended live microphone stream.

## Hindi and English preparation (models deferred)

The Python panel now exposes `whisper_language` (`auto`, `en`, `hi`) and an
optional `piper_hindi_model`. Keep listening disabled until assets and real audio
are validated. Hindi recognition requires a multilingual Whisper model, not an
English-only `.en` model. `auto` supplies `-l auto`; transcription does not request
translation to English. See the [upstream CLI options](https://github.com/ggml-org/whisper.cpp/blob/master/examples/cli/README.md).

Piper routes sentences containing Devanagari to the explicitly configured Hindi
voice; other sentences use the primary voice. Missing Hindi voice fails clearly.
Hindi danda sentence boundaries are supported. Romanized Hindi detection,
code-switching pronunciation, expressive prosody and voice quality are unverified.
This routing is not a claim of complete bilingual understanding. No models were
downloaded in the current validation session. See [results](RUNTIME_VALIDATION.md).
