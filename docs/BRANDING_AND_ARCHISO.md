# REgenOS Branding And Archiso

REgenOS is an Arch-based desktop product. Keep attribution clear: it does not replace or claim ownership of Arch Linux, Linux, or third-party components. The tracked identity includes an original pixel-cycle mark, desktop and lock-screen art, a Plymouth theme, and a retro companion concept atlas. The native Qt overlay renders spring-animated particles, twelve topic forms and validated model-generated pixel grids; the atlas is source artwork, not the live rendering engine.

## Apply Branding To An Existing Arch Install

Run this only on the Arch installation on the external NVMe. It installs a Linux boot splash for the OS startup stage, not the motherboard firmware logo or systemd-boot/GRUB menu logo.

```bash
cd ~/src/ai-os
sudo pacman -S --needed plymouth imagemagick
mkdir -p ~/regenos-branding
magick -background none branding/regenos-mark.svg -resize 512x512 ~/regenos-branding/regenos-mark.png
magick branding/wallpapers/default.svg ~/regenos-branding/default.png
magick branding/wallpapers/lockscreen.svg ~/regenos-branding/lockscreen.png
sudo install -d /usr/share/regenos/branding /usr/share/regenos/wallpapers
sudo install -m 0644 branding/regenos-mark.svg /usr/share/regenos/branding/regenos-mark.svg
sudo install -m 0644 branding/regenos-companion-atlas.png /usr/share/regenos/branding/companion-atlas.png
sudo install -m 0644 ~/regenos-branding/default.png /usr/share/regenos/wallpapers/default.png
sudo install -m 0644 ~/regenos-branding/lockscreen.png /usr/share/regenos/wallpapers/lockscreen.png
sudo install -d /usr/share/plymouth/themes/regenos
sudo install -m 0644 ~/regenos-branding/regenos-mark.png /usr/share/plymouth/themes/regenos/regenos-mark.png
sudo install -m 0644 branding/plymouth/regenos.plymouth branding/plymouth/regenos.script /usr/share/plymouth/themes/regenos/
sudo plymouth-set-default-theme regenos
```

Review `/etc/mkinitcpio.conf` and add `plymouth` to `HOOKS` after `udev` (or after `systemd` when using the systemd hook). Add `quiet splash` to the active bootloader kernel command line, then rebuild with `sudo mkinitcpio -P`. Keep a known-good boot entry and recovery USB available. Test this on the portable drive, not a host install you rely on.

The DE background is configured with Hyprpaper and lock screen with Hyprlock; see [Phase 5](PHASE_5_DESKTOP.md). Changing the GRUB/systemd-boot theme is a separate step and cannot change a vendor firmware logo.

## Build A Branded Live ISO

Include the default cursor artwork and new-user preferences using the
[cursor packaging guide](CURSOR_THEME.md#ship-in-a-future-iso).

Build the image on Arch after the runtime and desktop have been validated. These commands make a branded live image; they do **not** create an installer that partitions a disk.

```bash
sudo pacman -S --needed archiso imagemagick
mkdir -p ~/iso-work
cp -a /usr/share/archiso/configs/releng ~/iso-work/regenos
cd ~/iso-work/regenos
cat ~/src/ai-os/archiso/packages.x86_64.add >> packages.x86_64
mkdir -p airootfs/usr/share/regenos/branding airootfs/usr/share/regenos/wallpapers
cp ~/src/ai-os/branding/regenos-mark.svg airootfs/usr/share/regenos/branding/
cp ~/src/ai-os/branding/regenos-companion-atlas.png airootfs/usr/share/regenos/branding/
magick -background none ~/src/ai-os/branding/regenos-mark.svg -resize 512x512 airootfs/usr/share/regenos/branding/regenos-mark.png
magick ~/src/ai-os/branding/wallpapers/default.svg airootfs/usr/share/regenos/wallpapers/default.png
magick ~/src/ai-os/branding/wallpapers/lockscreen.svg airootfs/usr/share/regenos/wallpapers/lockscreen.png
mkdir -p airootfs/usr/share/plymouth/themes/regenos
cp ~/src/ai-os/branding/plymouth/regenos.plymouth ~/src/ai-os/branding/plymouth/regenos.script airootfs/usr/share/plymouth/themes/regenos/
cp airootfs/usr/share/regenos/branding/regenos-mark.png airootfs/usr/share/plymouth/themes/regenos/
```

Edit `profiledef.sh` in this copied profile and set a unique ISO name, label, publisher, and application description. Configure Plymouth in the copied profile's initramfs and boot entries, then ensure the theme is selected in the live root. The package list is a starting point; resolve packages against the current Arch repositories and remove hardware-specific packages that make the image unnecessarily fragile.

Create a live-session user and desktop autostart deliberately. Do not place personal home data, API keys, voice models, Ollama model files, or the developer's checkout in the ISO. Ship the runtime as a reviewed package or install it into the live root; `/etc/skel` alone only copies files to newly created users and does not install a working system service.

```bash
sudo mkarchiso -v -w ~/iso-work/work -o ~/iso-work/out ~/iso-work/regenos
ls -lh ~/iso-work/out
```

Boot the ISO in a VM first. For USB media, identify the destination with `lsblk` and verify the exact device before using any imaging command; writing an ISO erases the selected device.

## Add An Ubuntu-Style Installer

Archiso supplies live media, not a graphical installer. Calamares is a plausible installer UI, but this repository does not yet contain a package source, a complete Calamares config, a tested target-system strategy, or an installer launcher. See [`archiso/calamares/README.md`](../archiso/calamares/README.md). Treat Calamares as future packaging work, not an enabled feature.

Before including it in an ISO, create a reproducible signed package source or build it in a clean chroot. Configure distribution-specific modules and branding, then test UEFI bootloader setup, manual partitioning, disk encryption, erase-disk flow, cancellation, low disk space, failed installs, NVIDIA handling, and recovery in disposable VMs and on spare hardware. Never test destructive installer flows on the portable system that holds development work.

For a product identity, a final derivative image should also set its own `/etc/os-release` in the image profile, supply original GRUB/systemd-boot assets if desired, and provide licensing/attribution and update/recovery policies. Keep `ID_LIKE=arch` and credit upstream Arch packages. None of these changes replaces the kernel or filesystem; they customize the distribution defaults and shipped userland.
