from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AI_OS_HOME = Path(os.environ.get("AI_OS_HOME", "~/.ai_os")).expanduser()


@dataclass(frozen=True)
class AiOsConfig:
    home: Path
    log_dir: Path
    run_dir: Path
    model_dir: Path
    chroma_dir: Path
    ollama_url: str
    ollama_model: str
    allow_external_apis: bool
    allowed_api_hosts: tuple[str, ...]
    hyprland_enabled: bool


DEFAULT_CONFIG = {
    "ollama_url": "http://127.0.0.1:11434/api/chat",
    "ollama_model": "qwen2.5:7b-instruct-q4_K_M",
    "allow_external_apis": False,
    "allowed_api_hosts": [
        "api.x.ai",
        "api.openai.com",
        "generativelanguage.googleapis.com",
    ],
    "hyprland_enabled": False,
}


def ensure_runtime_tree(home: Path = AI_OS_HOME) -> None:
    for path in [
        home,
        home / "logs",
        home / "run",
        home / "models",
        home / "data",
        home / "data" / "private",
        Path("~/.local/share/ai_os/chroma").expanduser(),
    ]:
        path.mkdir(parents=True, exist_ok=True)

    for file_name, default_value in {
        "config.json": DEFAULT_CONFIG,
        "habit_engine.json": {"defaults": {}, "temporary_overrides": {}, "notes": []},
        "slang_vocab.json": {"replacements": {}, "protected_terms": []},
    }.items():
        target = home / file_name
        if not target.exists():
            target.write_text(json.dumps(default_value, indent=2) + "\n", encoding="utf-8")


def load_raw_config(home: Path = AI_OS_HOME) -> dict[str, Any]:
    ensure_runtime_tree(home)
    config_path = home / "config.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    merged = DEFAULT_CONFIG | data
    return merged


def load_config(home: Path = AI_OS_HOME) -> AiOsConfig:
    raw = load_raw_config(home)
    return AiOsConfig(
        home=home,
        log_dir=home / "logs",
        run_dir=home / "run",
        model_dir=home / "models",
        chroma_dir=Path("~/.local/share/ai_os/chroma").expanduser(),
        ollama_url=str(raw["ollama_url"]),
        ollama_model=str(raw["ollama_model"]),
        allow_external_apis=bool(raw["allow_external_apis"]),
        allowed_api_hosts=tuple(str(host) for host in raw["allowed_api_hosts"]),
        hyprland_enabled=bool(raw["hyprland_enabled"]),
    )

