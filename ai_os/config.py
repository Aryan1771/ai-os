from __future__ import annotations

import json
import os
import tempfile
import threading
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

AI_OS_HOME = Path(os.environ.get("AI_OS_HOME", "~/.ai_os")).expanduser()
_JSON_WRITE_LOCK = threading.Lock()


@dataclass(frozen=True)
class AiOsConfig:
    home: Path
    log_dir: Path
    run_dir: Path
    model_dir: Path
    chroma_dir: Path
    ollama_url: str
    ollama_model: str
    ai_provider: str
    api_key_env: str
    allow_external_apis: bool
    allowed_api_hosts: tuple[str, ...]
    hyprland_enabled: bool
    wake_word_enabled: bool
    whisper_cli: str
    whisper_model: Path
    piper_model: Path
    speech_enabled: bool
    always_listening_enabled: bool
    wake_word_threshold: float
    voice_command_seconds: int
    sandbox_lock_settings: bool
    avatar_enabled: bool
    avatar_corner: str
    avatar_scale: int
    avatar_animation_enabled: bool
    avatar_accent: str


DEFAULT_CONFIG = {
    "ollama_url": "http://127.0.0.1:11434/api/chat",
    "ollama_model": "qwen2.5:7b-instruct-q4_K_M",
    "ai_provider": "ollama",
    "api_key_env": "AI_OS_API_KEY",
    "allow_external_apis": False,
    "allowed_api_hosts": [
        "api.x.ai",
        "api.openai.com",
        "generativelanguage.googleapis.com",
    ],
    "hyprland_enabled": False,
    "wake_word_enabled": False,
    "whisper_cli": "whisper-cli",
    "whisper_model": "models/ggml-base.en.bin",
    "piper_model": "models/en_US-lessac-medium.onnx",
    "speech_enabled": False,
    "always_listening_enabled": False,
    "wake_word_threshold": 0.5,
    "voice_command_seconds": 8,
    "sandbox_lock_settings": True,
    "avatar_enabled": True,
    "avatar_corner": "bottom-right",
    "avatar_scale": 100,
    "avatar_animation_enabled": True,
    "avatar_accent": "#4de3a7",
    "avatar_motion": 65,
    "avatar_reactivity": 75,
    "avatar_show_emotion_bars": True,
    "avatar_topic_morphing": True,
    "avatar_idle_shape": "core",
    "avatar_emotions": {
        "joy": 35,
        "curiosity": 50,
        "focus": 40,
        "calm": 75,
        "concern": 10,
        "energy": 45,
    },
    "theme": "forest",
    "branding": {
        "brand_name": "REgenOS",
        "assistant_name": "Companion",
        "logo_path": "/usr/share/regenos/branding/regenos-mark.svg",
        "wallpaper_path": "/usr/share/regenos/wallpapers/default.png",
        "lockscreen_path": "/usr/share/regenos/wallpapers/lockscreen.png",
        "icon_theme": "Papirus-Dark",
        "cursor_theme": "REgenOS-Cool",
        "font": "Noto Sans 10",
    },
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
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object.")
    merged = deepcopy(DEFAULT_CONFIG) | data
    for key in ("branding", "avatar_emotions"):
        merged[key] = deepcopy(DEFAULT_CONFIG[key]) | data.get(key, {})
    return merged


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    """Publish a complete snapshot, including when speech and the daemon write together."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
        with _JSON_WRITE_LOCK:
            temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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
        ai_provider=str(raw["ai_provider"]),
        api_key_env=str(raw["api_key_env"]),
        allow_external_apis=bool(raw["allow_external_apis"]),
        allowed_api_hosts=tuple(str(host) for host in raw["allowed_api_hosts"]),
        hyprland_enabled=bool(raw["hyprland_enabled"]),
        wake_word_enabled=bool(raw["wake_word_enabled"]),
        whisper_cli=str(raw["whisper_cli"]),
        whisper_model=home / str(raw["whisper_model"]),
        piper_model=home / str(raw["piper_model"]),
        speech_enabled=bool(raw["speech_enabled"]),
        always_listening_enabled=bool(raw["always_listening_enabled"]),
        wake_word_threshold=max(0.0, min(1.0, float(raw["wake_word_threshold"]))),
        voice_command_seconds=max(2, min(30, int(raw["voice_command_seconds"]))),
        sandbox_lock_settings=bool(raw["sandbox_lock_settings"]),
        avatar_enabled=bool(raw["avatar_enabled"]),
        avatar_corner=str(raw["avatar_corner"]),
        avatar_scale=max(60, min(160, int(raw["avatar_scale"]))),
        avatar_animation_enabled=bool(raw["avatar_animation_enabled"]),
        avatar_accent=str(raw["avatar_accent"]),
    )
