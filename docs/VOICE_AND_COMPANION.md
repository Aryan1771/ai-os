# Voice, Listening, Companion, And Settings

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

## 2. Start Settings And Companion

```bash
mkdir -p ~/.config/systemd/user
cp ~/src/ai-os/systemd/ai-os-settings.service ~/.config/systemd/user/
cp ~/src/ai-os/systemd/ai-os-avatar.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ai-os-settings.service
```

Open `http://127.0.0.1:8765` locally. The panel configures model connection, online-provider opt-in, voice, listener, companion appearance, themes, branding paths, Hyprland IPC, and sandbox confirmation.

After setting your companion preferences, start it from a graphical session:

```bash
systemctl --user enable --now ai-os-avatar.service
```

Click the companion to open the panel. It is a lightweight temporary visual; replace it with your selected mascot artwork in the next branding stage.

## 3. Enable Voice Deliberately

In the local panel, enable **Require wake word**, **Always listening**, and optionally **Speak responses**. With sandbox locking enabled, the panel asks for a local protected-settings confirmation.

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
