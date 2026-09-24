# Project Structure

```text
ai-os-interface-layer/
├── ai_os/
│   ├── ai_os_core.py
│   ├── config.py
│   ├── hardware_monitor.py
│   ├── logging_utils.py
│   ├── speech_queue.py
│   ├── security/
│   │   └── consent_broker.py
│   └── services/
│       ├── external_api.py
│       ├── jobs.py
│       ├── scanner.py
│       ├── stt.py
│       └── wakeword.py
├── archiso/
├── branding/
├── config/
│   └── tools/
│       ├── memory_tools.py
│       ├── system_tools.py
│       └── ui_tools.py
├── docs/
│   ├── ARCH_RUNBOOK.md
│   ├── BRANDING_AND_ARCHISO.md
│   ├── INSTALL_ON_ARCH.md
│   ├── PHASE_5_DESKTOP.md
│   ├── PROJECT_STRUCTURE.md
│   └── ROADMAP.md
├── install/
│   └── ai-os-install.sh
├── scripts/
│   ├── install_arch_packages.sh
│   ├── install_runtime.sh
│   ├── run_smoke_tests.sh
│   └── security_baseline.sh
├── security/
│   └── apparmor.ai-os
├── systemd/
│   └── ai-os.service
├── tests/
│   └── test_command_risk.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

Runtime files are created under `~/.ai_os/` on the Arch system:

```text
~/.ai_os/
├── venv/
├── config.json
├── habit_engine.json
├── slang_vocab.json
├── logs/
├── run/
└── models/
```
