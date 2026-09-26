#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${AI_OS_HOME:-${HOME}/.ai_os}"
if [[ ${EUID} -eq 0 || ! -x "${RUNTIME_DIR}/venv/bin/python" ]]; then
  echo "Run as your desktop user after installing the runtime." >&2
  exit 1
fi
sudo pacman -S --needed base-devel cmake ninja qt6-base qt6-wayland
"${RUNTIME_DIR}/venv/bin/python" -m pip install -e "${REPO_ROOT}"
cmake -S "${REPO_ROOT}/native/hub" -B "${REPO_ROOT}/build/hub-linux" \
  -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="${RUNTIME_DIR}"
cmake --build "${REPO_ROOT}/build/hub-linux" --parallel 2
QT_QPA_PLATFORM=offscreen REGENOS_TEST_PYTHON="${RUNTIME_DIR}/venv/bin/python" \
  ctest --test-dir "${REPO_ROOT}/build/hub-linux" --output-on-failure
cmake --install "${REPO_ROOT}/build/hub-linux"
echo "Launch: ${RUNTIME_DIR}/venv/bin/regenos-settings"
