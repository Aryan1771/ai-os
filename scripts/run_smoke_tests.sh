#!/usr/bin/env bash
set -euo pipefail

source "${AI_OS_HOME:-${HOME}/.ai_os}/venv/bin/activate"

python -m pytest -q
python -m ai_os.tools.system_tools

python - <<'PY'
from ai_os.config import load_config
from ai_os.tools import ui_tools

print(load_config())
print(ui_tools.ui_status())
PY

echo "Smoke tests complete."

