#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${AI_OS_HOME:-${HOME}/.ai_os}"

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this as your desktop user, not root." >&2
  exit 1
fi
if [[ ! -x "${RUNTIME_DIR}/venv/bin/python" ]]; then
  echo "Install the runtime first: bash install/ai-os-install.sh runtime" >&2
  exit 1
fi

sudo pacman -S --needed libxkbcommon-x11 xcb-util-cursor libxcb fontconfig noto-fonts desktop-file-utils
"${RUNTIME_DIR}/venv/bin/python" -m pip install -e "${REPO_ROOT}[desktop]"
bash "${REPO_ROOT}/scripts/install_cpp_hub.sh"
mkdir -p "${HOME}/.local/share/applications" "${HOME}/.local/share/icons/hicolor/scalable/apps"
install -m 0644 "${REPO_ROOT}/branding/regenos-mark.svg" "${HOME}/.local/share/icons/hicolor/scalable/apps/regenos.svg"
for app in regenos-settings regenos-companion; do
  target="${HOME}/.local/share/applications/${app}.desktop"
  install -m 0644 "${REPO_ROOT}/config/desktop/${app}.desktop" "${target}"
  desktop-file-edit --set-key=Exec --set-value="\"${RUNTIME_DIR}/venv/bin/${app}\"" "${target}"
done
update-desktop-database "${HOME}/.local/share/applications"
bash "${REPO_ROOT}/scripts/install_cursor_theme.sh" --apply
# Disable the removed HTTP service when upgrading a previous checkout.
systemctl --user disable --now ai-os-settings.service 2>/dev/null || true
echo "Launch: ${RUNTIME_DIR}/venv/bin/regenos-settings"
