#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: bash install/ai-os-install.sh <base|runtime|voice|security|native|desktop|all>

Run one stage at a time on Arch. "all" runs the stages in order and asks before
security and desktop changes. It never enables Hyprland automation by itself.
EOF
}

confirm() {
  read -r -p "$1 [Approve/Deny] " answer
  [[ "${answer,,}" =~ ^(approve|a|yes|y)$ ]]
}

install_base() {
  sudo bash "${REPO_ROOT}/scripts/install_arch_packages.sh"
}

install_runtime() {
  bash "${REPO_ROOT}/scripts/install_runtime.sh"
}

install_voice() {
  sudo pacman -S --needed whisper-cpp ffmpeg
  source "${AI_OS_HOME:-${HOME}/.ai_os}/venv/bin/activate"
  python -m pip install -e "${REPO_ROOT}[memory,voice,udev,dev]"
  mkdir -p "${AI_OS_HOME:-${HOME}/.ai_os}/models"
  echo "Place a local Whisper GGML model and Piper .onnx model in ~/.ai_os/models."
}

install_security() {
  sudo bash "${REPO_ROOT}/scripts/security_baseline.sh"
}

install_desktop() {
  bash "${REPO_ROOT}/scripts/install_native_desktop.sh"
  sudo pacman -S --needed hyprland hyprlock hyprpaper hypridle waybar xorg-xwayland wofi kitty thunar \
    papirus-icon-theme adwaita-cursors noto-fonts noto-fonts-emoji ttf-jetbrains-mono \
    xdg-desktop-portal-hyprland ydotool plymouth imagemagick
  mkdir -p "${HOME}/.config/hypr"
  install -m 0644 "${REPO_ROOT}/config/hypr/hyprlock.conf" "${HOME}/.config/hypr/hyprlock.conf"
  install -m 0644 "${REPO_ROOT}/config/hypr/hyprpaper.conf" "${HOME}/.config/hypr/hyprpaper.conf"
  install -m 0644 "${REPO_ROOT}/config/hypr/regenos-bindings.conf" "${HOME}/.config/hypr/regenos-bindings.conf"
  install -m 0644 "${REPO_ROOT}/config/hypr/regenos-companion.conf" "${HOME}/.config/hypr/regenos-companion.conf"
  echo "Desktop templates installed. Follow docs/PHASE_5_DESKTOP.md and docs/VOICE_AND_COMPANION.md before enabling services."
  echo "Add 'source = ~/.config/hypr/regenos-bindings.conf' to your Hyprland config after checking key conflicts."
}

case "${1:-}" in
  base) install_base ;;
  runtime) install_runtime ;;
  voice) install_voice ;;
  native) bash "${REPO_ROOT}/scripts/install_native_desktop.sh" ;;
  security) confirm "Apply the firewall and AppArmor baseline?" && install_security ;;
  desktop) confirm "Install the Hyprland desktop packages?" && install_desktop ;;
  all)
    install_base
    install_runtime
    install_voice
    confirm "Apply the firewall and AppArmor baseline?" && install_security
    confirm "Install the Hyprland desktop packages?" && install_desktop
    ;;
  *) usage; exit 2 ;;
esac
