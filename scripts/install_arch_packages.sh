#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/install_arch_packages.sh" >&2
  exit 1
fi

pacman -Syu --needed \
  base-devel git neovim nano curl wget unzip jq \
  python python-pip python-virtualenv \
  linux-zen linux-zen-headers dkms \
  nvidia-dkms nvidia-utils cuda opencl-nvidia \
  pipewire pipewire-pulse pipewire-alsa wireplumber alsa-utils \
  brightnessctl lm_sensors pciutils usbutils \
  ollama ffmpeg \
  ufw clamav apparmor audit

systemctl enable --now ollama
systemctl enable apparmor
systemctl enable ufw

echo "Arch package installation complete."

