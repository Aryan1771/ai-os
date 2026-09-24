# Install On Arch

Run these commands only after booting the external NVMe into Arch Linux. Windows is the editing machine; it cannot validate PipeWire, NVIDIA, udev, systemd, or Hyprland.

## 1. Clone And Inspect

```bash
mkdir -p ~/src
git clone https://github.com/Aryan1771/ai-os.git ~/src/ai-os
cd ~/src/ai-os
git status
```

## 2. Base And Runtime

```bash
bash install/ai-os-install.sh base
bash install/ai-os-install.sh runtime
source ~/.ai_os/venv/bin/activate
python -m pytest -q
python -m ruff check ai_os tests
```

Install and verify Ollama separately:

```bash
sudo systemctl enable --now ollama
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama list
nvidia-smi
```

Start the daemon only after those checks succeed:

```bash
cd ~/src/ai-os
source ~/.ai_os/venv/bin/activate
python -m ai_os.ai_os_core
```

## 3. Voice And Memory

```bash
cd ~/src/ai-os
bash install/ai-os-install.sh voice
command -v whisper-cli
mkdir -p ~/.ai_os/models
```

Download Whisper GGML and Piper voice models only from their upstream publishers, verify their checksums, then place them at the paths configured in `~/.ai_os/config.json`. Do not commit models to Git. Set `wake_word_enabled` to `true` only after a microphone and voice pipeline test.

Smoke checks:

```bash
source ~/.ai_os/venv/bin/activate
python - <<'PY'
from ai_os.config import load_config
from ai_os.services.stt import WhisperCppTranscriber

config = load_config()
print(WhisperCppTranscriber(config.whisper_cli, config.whisper_model).availability())
PY
```

## 4. Security

This stage modifies the firewall and loads AppArmor policy. Review the script first, then run it from a local terminal with recovery access.

```bash
cd ~/src/ai-os
less scripts/security_baseline.sh
bash install/ai-os-install.sh security
sudo ufw status verbose
sudo aa-status
```

The Python external API broker stays disabled unless `allow_external_apis` is changed to `true`. Keep API credentials outside the repository and pass them through a protected runtime secret mechanism.

## 5. Hardware And Background Work

```bash
source ~/.ai_os/venv/bin/activate
python -m ai_os.hardware_monitor
```

Use `Ctrl+C` to stop the polling monitor. The optional udev monitor is for device notifications; it does not execute actions automatically.

## 6. User Service

```bash
mkdir -p ~/.config/systemd/user
cp ~/src/ai-os/systemd/ai-os.service ~/.config/systemd/user/ai-os.service
systemctl --user daemon-reload
systemctl --user enable --now ai-os.service
systemctl --user status ai-os.service
journalctl --user -u ai-os.service -f
```

The checked-in unit assumes `~/src/ai-os`. If you choose another checkout path, adjust only your installed user unit, not the tracked template.
