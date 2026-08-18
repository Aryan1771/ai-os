# AI-OS Arch Runbook

This file is the command checklist to run after booting into the Arch Linux install on the external NVMe drive.

The repo is developed on Windows, pushed to GitHub, then cloned on Arch. Linux-specific commands are not tested on Windows.

## 0. First Boot Sanity Checks

```bash
uname -a
lsblk -f
ping -c 3 archlinux.org
```

Confirm you are booted into the external NVMe system, not Windows.

## 1. Clone The Repository

Replace `YOUR_USERNAME` with your GitHub username.

```bash
mkdir -p ~/src
cd ~/src
git clone https://github.com/YOUR_USERNAME/ai-os-interface-layer.git
cd ai-os-interface-layer
```

If the repo is private:

```bash
git clone git@github.com:YOUR_USERNAME/ai-os-interface-layer.git
```

## 2. Install Arch Packages

```bash
cd ~/src/ai-os-interface-layer
sudo bash scripts/install_arch_packages.sh
```

Verify GPU and CUDA:

```bash
nvidia-smi
nvcc --version
```

Verify audio services:

```bash
systemctl --user status pipewire pipewire-pulse wireplumber
wpctl status
```

If PipeWire user services are not running:

```bash
systemctl --user enable --now pipewire pipewire-pulse wireplumber
```

## 3. Create Python Runtime

```bash
cd ~/src/ai-os-interface-layer
bash scripts/install_runtime.sh
```

Activate the venv:

```bash
source ~/.ai_os/venv/bin/activate
python --version
python -m pip --version
```

Arch rule: do not use `sudo pip`. All Python packages for this project live inside `~/.ai_os/venv`.

## 4. Pull And Verify Ollama Model

```bash
sudo systemctl enable --now ollama
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama list
```

Run one test prompt:

```bash
ollama run qwen2.5:7b-instruct-q4_K_M "Reply with one JSON object: {\"status\":\"ready\"}"
```

Watch VRAM in another terminal:

```bash
watch -n 1 nvidia-smi
```

For the RTX 4060 Laptop 8 GB target, keep normal local inference around 4.7 to 5.2 GB VRAM, leaving room for the display and system overhead.

## 5. Run Smoke Tests

```bash
cd ~/src/ai-os-interface-layer
bash scripts/run_smoke_tests.sh
```

Manual system tool checks:

```bash
source ~/.ai_os/venv/bin/activate
python -m ai_os.tools.system_tools
```

Risk assessment check:

```bash
python - <<'PY'
from ai_os.tools.system_tools import assess_command

commands = [
    ["ls", "/"],
    ["pacman", "-Q", "python"],
    ["sudo", "pacman", "-S", "vim"],
    ["rm", "-rf", "/"],
]

for command in commands:
    print(command)
    print(assess_command(command))
    print()
PY
```

## 6. Run The AI-OS Daemon Manually

Start Ollama if it is not already running:

```bash
sudo systemctl start ollama
```

Start the daemon:

```bash
source ~/.ai_os/venv/bin/activate
cd ~/src/ai-os-interface-layer
python -m ai_os.ai_os_core
```

Try:

```text
What are my hardware stats?
```

Try a safe command:

```text
Run uname -a
```

Try a risky command only to confirm it asks consent:

```text
Run sudo pacman -S vim
```

Choose `Deny` for this test.

## 7. Install User systemd Service

Only do this after the manual daemon works.

```bash
mkdir -p ~/.config/systemd/user
cp systemd/ai-os.service ~/.config/systemd/user/ai-os.service
systemctl --user daemon-reload
systemctl --user enable --now ai-os.service
systemctl --user status ai-os.service
```

View logs:

```bash
journalctl --user -u ai-os.service -f
tail -f ~/.ai_os/logs/ai_os.log
```

If you want the user service to start before login:

```bash
sudo loginctl enable-linger "$USER"
```

## 8. Apply Security Baseline

Do this after package installation and model downloads, because strict outbound firewall rules can interrupt setup.

```bash
cd ~/src/ai-os-interface-layer
sudo bash scripts/security_baseline.sh
```

Check:

```bash
sudo ufw status verbose
sudo aa-status
systemctl status clamav-daemon apparmor
```

Important: UFW cannot reliably whitelist changing cloud domains by name. Domain allow/deny is enforced inside the Python API broker later. UFW handles the coarse network wall.

## 9. Optional: noexec Mounts

Apply only after everything installs correctly.

Inspect current mounts:

```bash
findmnt /tmp
findmnt ~/.cache
```

For `/tmp`, systemd usually manages a tmpfs unit. Create an override:

```bash
sudo systemctl edit tmp.mount
```

Add:

```ini
[Mount]
Options=mode=1777,strictatime,nosuid,nodev,noexec
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart tmp.mount
findmnt /tmp
```

If anything breaks during builds, remove the override and restart `tmp.mount`.

## 10. GitHub Development Loop

On Windows:

```powershell
cd C:\path\to\ai-os-interface-layer
git status
git add .
git commit -m "Update AI-OS layer"
git push
```

On Arch:

```bash
cd ~/src/ai-os-interface-layer
git pull
source ~/.ai_os/venv/bin/activate
python -m pip install -e ".[memory,voice,vision,udev,dev]"
bash scripts/run_smoke_tests.sh
```

## 11. Hyprland Later

Do not install or rely on Hyprland for Phase 1. When the daemon is stable:

```bash
sudo pacman -S --needed hyprland waybar kitty xdg-desktop-portal-hyprland ydotool
```

Then edit `~/.ai_os/config.json`:

```json
{
  "hyprland_enabled": true
}
```

The `ai_os/tools/ui_tools.py` module is intentionally disabled until this phase.

## 12. Final Packaging Later

When the full system is ready:

```bash
sudo pacman -S --needed archiso
cp -r /usr/share/archiso/configs/releng ~/ai-os-archiso
```

Packaging should be a separate phase after all runtime behavior is stable.

