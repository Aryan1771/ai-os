#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
AI_OS_HOME="${AI_OS_HOME:-${HOME}/.ai_os}"

mkdir -p "${AI_OS_HOME}/logs" "${AI_OS_HOME}/run" "${AI_OS_HOME}/models" "${AI_OS_HOME}/tools"
mkdir -p "${HOME}/.local/share/ai_os/chroma"

python -m venv "${AI_OS_HOME}/venv"
source "${AI_OS_HOME}/venv/bin/activate"

python -m pip install --upgrade pip wheel setuptools
python -m pip install -e "${REPO_ROOT}[memory,voice,vision,udev,dev]"

python - <<'PY'
from ai_os.config import ensure_runtime_tree
ensure_runtime_tree()
print("Runtime tree created under ~/.ai_os")
PY

echo "Runtime installation complete."
echo "Activate with: source ~/.ai_os/venv/bin/activate"

