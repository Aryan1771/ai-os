# Product Branding And Archiso

AI-OS can be a distinct Arch-based product, but it should accurately state that it is built on Arch Linux. Change branding, defaults, services, artwork, desktop configuration, and installer behavior; do not claim ownership of the Linux kernel or third-party projects.

## Branding Steps

1. Choose a product name, identifier, hostname, and original logo.
2. Add original artwork under `branding/` without secrets or third-party copyrighted images.
3. Install wallpapers and logo into `/usr/share/ai-os/` using the Phase 5 instructions.
4. Configure `hyprpaper`, `hyprlock`, Waybar, terminal, fonts, icon theme, and cursor theme for the visual identity.
5. Add a product-specific `/etc/os-release` only to the final Archiso image or a tested installation profile. Back up the original file before changing a live system.

Example `/etc/os-release` content for a derivative:

```ini
NAME="AI-OS"
PRETTY_NAME="AI-OS (Arch-based)"
ID=ai-os
ID_LIKE=arch
BUILD_ID=rolling
HOME_URL="https://github.com/Aryan1771/ai-os"
```

## Archiso Build

Build the image on Arch, not Windows, after all hardware tests pass.

```bash
sudo pacman -S --needed archiso
mkdir -p ~/iso-work
cp -a /usr/share/archiso/configs/releng ~/iso-work/ai-os
cd ~/iso-work/ai-os
```

Copy the tracked additions into the copied profile:

```bash
cat ~/src/ai-os/archiso/packages.x86_64.add >> packages.x86_64
sudo install -d airootfs/usr/share/ai-os
sudo cp -a ~/src/ai-os/branding airootfs/usr/share/ai-os/branding
sudo install -d airootfs/etc/skel/src
sudo cp -a ~/src/ai-os airootfs/etc/skel/src/ai-os
```

Edit `profiledef.sh` in the copied profile and set an original ISO name, label, publisher, and application description. Do not include private models, API credentials, `~/.ai_os`, or personal data in the ISO.

```bash
sudo mkarchiso -v -w ~/iso-work/work -o ~/iso-work/out ~/iso-work/ai-os
ls -lh ~/iso-work/out
```

Test the ISO in a VM before writing it to removable media. When writing to a USB, identify the target with `lsblk` and use the exact device only after verifying it is not a disk containing data you need.
