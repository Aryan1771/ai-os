# AI-OS Completion, Branding, And ISO Conversion Plan

This file explains what exists now, what is still missing, what can be customized in Arch, and how the final AI-integrated system can later be packaged into an installable ISO.

## 1. Is The Code Fully Complete?

No. The current repository is a serious starter foundation, not the finished full AI-operated OS.

What is already present:

- Python package structure for the AI-OS interface layer.
- Core daemon starter: `ai_os/ai_os_core.py`.
- Tool registry and Ollama chat wrapper.
- Safe command assessment and command execution broker.
- Process, hardware, NVIDIA, volume, and brightness helpers.
- JSON habit/slang memory starter.
- Speech queue starter.
- Hardware monitor starter.
- Hyprland/Wayland UI tools intentionally disabled until the UI phase.
- Arch install scripts.
- systemd user service template.
- AppArmor template.
- Arch setup runbook.

What is not complete yet:

- Full LLM planning loop with robust multi-step tool execution.
- Whisper.cpp speech-to-text integration.
- Piper TTS audio playback wiring.
- openWakeWord always-listening wake trigger.
- ChromaDB semantic memory layer.
- External API router for Grok/OpenAI/Gemini.
- AppArmor profile hardening after real-world testing.
- UFW domain-aware broker integration.
- ClamAV download scanning hooks.
- Full hardware event reaction engine.
- Async job manager with pause/resume/kill.
- Mid-speech interrupt bridge connected to real TTS.
- Hyprland desktop automation.
- HUD or shell overlay.
- Lock screen/home screen branding.
- Archiso packaging.

Treat the repo as the build skeleton. The OS becomes real after each module is implemented, tested on Arch, and then integrated.

## 2. Final Completed AI-OS Feature Checklist

Once complete, the system should have:

- Offline local AI assistant using Ollama and Qwen 2.5.
- Safe command execution with risk levels: safe, moderate, destructive, prohibited.
- Human approval prompt for risky commands.
- System stats awareness: CPU, RAM, disk, battery, NVIDIA GPU, VRAM, temperature.
- Process listing and approved process termination.
- PipeWire volume control through `wpctl`.
- Brightness control through `brightnessctl`.
- Whisper.cpp voice dictation and command input.
- openWakeWord wake phrase activation.
- Piper TTS voice output.
- Sentence-aware speech queue.
- Mid-speech background task completion bridge.
- Local memory for habits and preferences.
- Slang/custom vocabulary autocorrect.
- Temporary overrides versus permanent habits.
- ChromaDB long-term semantic memory.
- Hardware monitor for display/GPU/RAM/device changes.
- Background async jobs with task IDs.
- External API broker with strict hostname allowlist.
- ClamAV scanning for downloaded files.
- UFW firewall baseline.
- AppArmor confinement for the AI daemon.
- No global `sudo pip`; all Python packages stay in `~/.ai_os/venv`.
- Later Hyprland integration through `hyprctl`.
- Later UI typing through `ydotool` or `wdotool`.
- Custom wallpaper, lock screen, boot splash, display manager theme, icon theme, and OS branding.
- Final Archiso image that installs your customized AI OS.

## 3. What Can Be Changed To Make Arch Feel Like A New OS?

You can customize nearly everything above the kernel and base filesystem:

- OS name shown in `/etc/os-release`.
- Hostname.
- Bootloader menu title and background.
- Plymouth boot splash.
- Login/display manager theme.
- Lock screen wallpaper.
- Desktop wallpaper.
- Hyprland config.
- Waybar theme.
- Terminal theme.
- GTK theme.
- Qt theme.
- Cursor theme.
- Icon theme.
- Fonts.
- Shell prompt.
- Neofetch/fastfetch logo.
- Default apps.
- Preinstalled services.
- System sounds.
- Installer branding.
- ISO filename.
- Package repository name if you later host custom packages.

You should not pretend the Linux kernel is your original kernel. The honest model is:

```text
Your OS name
Built on Arch Linux
Custom AI interface layer, branding, services, desktop, and install image
```

## 4. Suggested Identity

Possible names:

- Aionix OS
- AryaOS
- Neural Arch
- Sentra OS
- Kairo OS
- Nira OS
- Veda OS
- HaloCore OS

Suggested first branding set:

```text
OS name: Aionix OS
Base: Arch Linux
Assistant name: Aion
Default hostname: aionix
Repo name: ai-os
Runtime folder: ~/.ai_os
```

## 5. Prepare Brand Assets

Create this folder in the repo:

```bash
mkdir -p branding/wallpapers branding/logos branding/plymouth branding/sddm branding/icons
```

Recommended asset sizes:

```text
branding/logos/os-logo.svg
branding/logos/os-logo.png          1024x1024
branding/wallpapers/default.png     3840x2160
branding/wallpapers/lockscreen.png  3840x2160
branding/plymouth/logo.png          512x512
```

Later, on Arch, install them to:

```bash
sudo mkdir -p /usr/share/ai-os/{logos,wallpapers}
sudo cp branding/logos/os-logo.png /usr/share/ai-os/logos/os-logo.png
sudo cp branding/wallpapers/default.png /usr/share/ai-os/wallpapers/default.png
sudo cp branding/wallpapers/lockscreen.png /usr/share/ai-os/wallpapers/lockscreen.png
```

## 6. Change OS Name

Create a backup first:

```bash
sudo cp /etc/os-release /etc/os-release.arch-backup
```

Edit:

```bash
sudo nano /etc/os-release
```

Example:

```ini
NAME="Aionix OS"
PRETTY_NAME="Aionix OS"
ID=aionix
ID_LIKE=arch
BUILD_ID=rolling
ANSI_COLOR="38;2;23;147;209"
HOME_URL="https://github.com/Aryan1771/ai-os"
DOCUMENTATION_URL="https://github.com/Aryan1771/ai-os"
SUPPORT_URL="https://github.com/Aryan1771/ai-os/issues"
BUG_REPORT_URL="https://github.com/Aryan1771/ai-os/issues"
LOGO=aionix
```

Set hostname:

```bash
sudo hostnamectl set-hostname aionix
```

Check:

```bash
cat /etc/os-release
hostnamectl
```

## 7. Bootloader Branding

### systemd-boot

Check if you use systemd-boot:

```bash
bootctl status
```

Edit loader config:

```bash
sudo nano /boot/loader/loader.conf
```

Example:

```ini
default aionix.conf
timeout 3
console-mode max
editor no
```

Create a branded entry:

```bash
sudo cp /boot/loader/entries/*.conf /boot/loader/entries/aionix.conf
sudo nano /boot/loader/entries/aionix.conf
```

Change the title:

```ini
title   Aionix OS
```

### GRUB

If you use GRUB:

```bash
sudo nano /etc/default/grub
```

Set:

```ini
GRUB_DISTRIBUTOR="Aionix OS"
GRUB_BACKGROUND="/usr/share/ai-os/wallpapers/default.png"
```

Regenerate:

```bash
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

## 8. Plymouth Boot Splash

Install Plymouth:

```bash
sudo pacman -S --needed plymouth
```

Create a theme:

```bash
sudo mkdir -p /usr/share/plymouth/themes/aionix
sudo cp branding/plymouth/logo.png /usr/share/plymouth/themes/aionix/logo.png
sudo nano /usr/share/plymouth/themes/aionix/aionix.plymouth
```

Paste:

```ini
[Plymouth Theme]
Name=Aionix
Description=Aionix OS boot splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/aionix
ScriptFile=/usr/share/plymouth/themes/aionix/aionix.script
```

Create script:

```bash
sudo nano /usr/share/plymouth/themes/aionix/aionix.script
```

Paste:

```text
logo.image = Image("logo.png");
logo.sprite = Sprite(logo.image);
logo.sprite.SetX(Window.GetWidth() / 2 - logo.image.GetWidth() / 2);
logo.sprite.SetY(Window.GetHeight() / 2 - logo.image.GetHeight() / 2);
```

Enable theme:

```bash
sudo plymouth-set-default-theme -R aionix
```

Add Plymouth hook to mkinitcpio:

```bash
sudo nano /etc/mkinitcpio.conf
```

Put `plymouth` in `HOOKS` after `base` and `udev`, then rebuild:

```bash
sudo mkinitcpio -P
```

For systemd-boot or GRUB kernel parameters, add:

```text
quiet splash
```

## 9. Login Screen And Lock Screen Branding

### SDDM Login Screen

Install:

```bash
sudo pacman -S --needed sddm qt6-svg qt6-declarative
sudo systemctl enable sddm
```

Install a theme later, or create one:

```bash
sudo mkdir -p /usr/share/sddm/themes/aionix
```

Set the SDDM theme:

```bash
sudo mkdir -p /etc/sddm.conf.d
sudo nano /etc/sddm.conf.d/theme.conf
```

Paste:

```ini
[Theme]
Current=aionix
```

### Hyprlock Lock Screen

When Hyprland phase starts:

```bash
sudo pacman -S --needed hyprlock
mkdir -p ~/.config/hypr
nano ~/.config/hypr/hyprlock.conf
```

Example:

```ini
background {
    monitor =
    path = /usr/share/ai-os/wallpapers/lockscreen.png
    blur_passes = 2
    contrast = 1.0
    brightness = 0.85
}

input-field {
    monitor =
    size = 300, 56
    position = 0, -120
    dots_center = true
    fade_on_empty = false
    placeholder_text = Password
}
```

## 10. Home Screen Wallpaper

### Hyprland

Install wallpaper tool:

```bash
sudo pacman -S --needed hyprpaper
mkdir -p ~/.config/hypr
nano ~/.config/hypr/hyprpaper.conf
```

Paste:

```ini
preload = /usr/share/ai-os/wallpapers/default.png
wallpaper = ,/usr/share/ai-os/wallpapers/default.png
splash = false
```

In `~/.config/hypr/hyprland.conf`, add:

```ini
exec-once = hyprpaper
```

### Minimal X11

Install:

```bash
sudo pacman -S --needed feh
```

Set wallpaper:

```bash
feh --bg-fill /usr/share/ai-os/wallpapers/default.png
```

Persist in `~/.xinitrc`:

```bash
echo 'feh --bg-fill /usr/share/ai-os/wallpapers/default.png &' >> ~/.xinitrc
```

## 11. Icons, Cursor, Fonts, And Themes

Install useful defaults:

```bash
sudo pacman -S --needed papirus-icon-theme bibata-cursor-theme noto-fonts noto-fonts-emoji ttf-jetbrains-mono
```

Set GTK theme files:

```bash
mkdir -p ~/.config/gtk-3.0 ~/.config/gtk-4.0
nano ~/.config/gtk-3.0/settings.ini
```

Example:

```ini
[Settings]
gtk-icon-theme-name=Papirus-Dark
gtk-cursor-theme-name=Bibata-Modern-Ice
gtk-font-name=Noto Sans 10
```

Copy to GTK 4:

```bash
cp ~/.config/gtk-3.0/settings.ini ~/.config/gtk-4.0/settings.ini
```

## 12. Terminal And Shell Identity

Install:

```bash
sudo pacman -S --needed fastfetch zsh starship
```

Set shell prompt:

```bash
echo 'eval "$(starship init bash)"' >> ~/.bashrc
```

Create OS info:

```bash
mkdir -p ~/.config/fastfetch
nano ~/.config/fastfetch/config.jsonc
```

Later add a custom ASCII or logo config.

## 13. AI-OS Service Branding

Install the AI service after runtime works:

```bash
cd ~/src/ai-os
mkdir -p ~/.config/systemd/user
cp systemd/ai-os.service ~/.config/systemd/user/ai-os.service
systemctl --user daemon-reload
systemctl --user enable --now ai-os.service
systemctl --user status ai-os.service
```

Logs:

```bash
journalctl --user -u ai-os.service -f
```

## 14. Convert Your Customized System Into An ISO

Use Archiso only after the live installed OS is stable.

Install:

```bash
sudo pacman -S --needed archiso
```

Create profile:

```bash
mkdir -p ~/iso-work
cp -r /usr/share/archiso/configs/releng ~/iso-work/aionix
cd ~/iso-work/aionix
```

Edit package list:

```bash
nano packages.x86_64
```

Add project packages:

```text
git
python
python-pip
python-virtualenv
nvidia-dkms
nvidia-utils
cuda
pipewire
pipewire-pulse
wireplumber
ollama
ufw
clamav
apparmor
brightnessctl
hyprland
hyprpaper
hyprlock
waybar
kitty
```

Add custom files into the ISO root:

```bash
mkdir -p airootfs/usr/share/ai-os
mkdir -p airootfs/etc/skel/src
mkdir -p airootfs/etc/systemd/system
```

Copy branding:

```bash
sudo cp -r ~/src/ai-os/branding airootfs/usr/share/ai-os/branding
```

Copy repo source for the default user skeleton:

```bash
cp -r ~/src/ai-os airootfs/etc/skel/src/ai-os
```

Customize ISO profile name:

```bash
nano profiledef.sh
```

Change:

```bash
iso_name="aionix-os"
iso_label="AIONIX_$(date +%Y%m)"
iso_publisher="Aryan1771"
iso_application="Aionix OS Live/Install Image"
```

Build:

```bash
sudo mkarchiso -v -w ~/iso-work/work -o ~/iso-work/out ~/iso-work/aionix
```

The ISO appears in:

```bash
ls -lh ~/iso-work/out
```

Flash to USB:

```bash
lsblk
sudo dd bs=4M if=~/iso-work/out/aionix-os-*.iso of=/dev/sdX status=progress oflag=sync
```

Replace `/dev/sdX` carefully. A wrong disk will destroy data.

## 15. Safer ISO Build Strategy

Recommended order:

1. Build normal Arch external NVMe install.
2. Install AI-OS repo.
3. Test all modules manually.
4. Enable systemd service.
5. Add branding.
6. Reboot and confirm branding.
7. Add Hyprland UI.
8. Confirm AI still works without the UI.
9. Build Archiso.
10. Test ISO in a VM.
11. Flash ISO to spare USB.
12. Test on real hardware.

## 16. Git Commands For This File

From Windows:

```powershell
cd C:\Users\aryan\Documents\GitHub\ai-os
git status
git add change.md
git commit -m "Add OS customization and ISO plan"
git push
```

