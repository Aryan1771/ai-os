from __future__ import annotations

import configparser
import math
import os
import re
import shutil
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from ai_os.companion_state import EMOTIONS, SHAPE_NAMES
from ai_os.config import AI_OS_HOME, DEFAULT_CONFIG, atomic_json, load_raw_config
from ai_os.cursor_theme import apply_preferences

EDITABLE_KEYS = set(DEFAULT_CONFIG)
PROTECTED_KEYS = {
    "allow_external_apis",
    "allowed_api_hosts",
    "hyprland_enabled",
    "ai_provider",
    "ollama_url",
    "always_listening_enabled",
    "sandbox_lock_settings",
    "whisper_cli",
}
CHOICES = {
    "ai_provider": {"ollama", "openai_compatible"},
    "avatar_corner": {"top-left", "top-right", "bottom-left", "bottom-right"},
    "theme": {"forest", "graphite", "ocean", "light", "sunrise"},
    "avatar_idle_shape": set(SHAPE_NAMES),
}
BOUNDS = {
    "avatar_scale": (60, 160),
    "avatar_motion": (0, 100),
    "avatar_reactivity": (0, 100),
    "voice_command_seconds": (2, 30),
    "wake_word_threshold": (0, 1),
}


def validate_model_endpoint(config: dict[str, Any]) -> None:
    url = urlparse(config["ollama_url"])
    try:
        port = url.port
    except ValueError as exc:
        raise ValueError("Invalid model endpoint port.") from exc
    if url.username or url.password or url.fragment or not url.hostname or port == 0:
        raise ValueError("Model endpoints must not contain credentials or fragments.")
    if url.hostname in {"localhost", "127.0.0.1", "::1"} and url.scheme == "http":
        return
    if config["ai_provider"] == "ollama":
        raise ValueError("Ollama requires a loopback HTTP endpoint.")
    if not config["allow_external_apis"]:
        raise PermissionError("Enable external providers before selecting a remote endpoint.")
    if url.scheme != "https" or url.hostname not in config["allowed_api_hosts"]:
        raise ValueError("Remote endpoints require HTTPS and an approved hostname.")


def validate_setting(key: str, value: Any) -> Any:
    if key not in EDITABLE_KEYS:
        raise ValueError(f"Unsupported setting: {key}")
    default = DEFAULT_CONFIG[key]
    if isinstance(default, bool):
        if type(value) is not bool:
            raise ValueError(f"{key} must be a checkbox value.")
    elif key in BOUNDS:
        low, high = BOUNDS[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}.")
        if isinstance(default, int) and int(value) != value:
            raise ValueError(f"{key} must be a whole number.")
    elif key == "allowed_api_hosts":
        if not isinstance(value, list) or len(value) > 64:
            raise ValueError("Provide at most 64 approved hostnames.")
        if any(
            not isinstance(host, str)
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host)
            for host in value
        ):
            raise ValueError("Approved hosts must be lowercase hostnames without paths or ports.")
    elif key == "avatar_emotions":
        if not isinstance(value, dict) or set(value) - set(EMOTIONS):
            raise ValueError("Unknown emotion channel.")
        if any(type(level) is not int or not 0 <= level <= 100 for level in value.values()):
            raise ValueError("Emotion bars range from 0 to 100.")
        value = DEFAULT_CONFIG[key] | value
    elif key == "branding":
        if not isinstance(value, dict) or set(value) - set(default):
            raise ValueError("Unknown branding field.")
        value = default | value
        for name, item in value.items():
            if not isinstance(item, str) or len(item) > 512 or any(ord(c) < 32 for c in item):
                raise ValueError(f"Invalid branding field: {name}")
            if name.endswith("_path") and item:
                absolute = Path(item).is_absolute() or PurePosixPath(item).is_absolute()
                if not absolute or any(c in item for c in ",{}#$"):
                    raise ValueError(
                        f"{name} requires an absolute path without configuration syntax."
                    )
            elif name in {"icon_theme", "cursor_theme", "font"} and not re.fullmatch(
                r"[A-Za-z0-9 ._-]{1,80}", item
            ):
                raise ValueError(f"Invalid {name}.")
    elif isinstance(default, str):
        if not isinstance(value, str) or len(value) > 512 or any(ord(c) < 32 for c in value):
            raise ValueError(f"Invalid {key}.")
        if key in CHOICES and value not in CHOICES[key]:
            raise ValueError(f"Unsupported {key}.")
        if key == "avatar_accent" and not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise ValueError("Accent must be a six-digit hex color.")
        if key == "api_key_env" and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("Specify an environment variable name, not an API key.")
    return value


def protected_changes(current: dict, changes: dict) -> set[str]:
    return {key for key in PROTECTED_KEYS.intersection(changes) if current.get(key) != changes[key]}


def save_settings(
    changes: dict[str, Any], home: Path = AI_OS_HOME, *, human_confirmed=False
) -> dict[str, Any]:
    current = load_raw_config(home)
    validated = {key: validate_setting(key, value) for key, value in changes.items()}
    protected = protected_changes(current, validated)
    if current["sandbox_lock_settings"] and protected and not human_confirmed:
        raise PermissionError("Local confirmation required: " + ", ".join(sorted(protected)))
    result = current | validated
    validate_model_endpoint(result)
    atomic_json(home / "config.json", result)
    return result


def apply_user_appearance(config: dict[str, Any], config_root: Path | None = None) -> None:
    branding = validate_setting("branding", config["branding"])
    root = config_root or Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    gtk_path = root / "gtk-3.0" / "settings.ini"
    gtk = configparser.ConfigParser(interpolation=None)
    if gtk_path.exists():
        gtk.read(gtk_path, encoding="utf-8")
    if not gtk.has_section("Settings"):
        gtk.add_section("Settings")
    for field, key in (
        ("icon_theme", "gtk-icon-theme-name"),
        ("cursor_theme", "gtk-cursor-theme-name"),
        ("font", "gtk-font-name"),
    ):
        gtk.set("Settings", key, branding[field])
    buffer = StringIO()
    gtk.write(buffer)
    contents = {
        gtk_path: buffer.getvalue(),
        root / "hypr" / "hyprpaper.conf": (
            f"preload = {branding['wallpaper_path']}\nwallpaper = ,{branding['wallpaper_path']}\nsplash = false\n"
        ),
        root / "hypr" / "hyprlock.conf": (
            "background {\n    monitor =\n"
            f"    path = {branding['lockscreen_path']}\n    blur_passes = 2\n}}\n"
            "input-field {\n    monitor =\n    size = 300, 56\n    position = 0, -120\n"
            "    dots_center = true\n    fade_on_empty = false\n}\n"
        ),
    }
    for target, content in contents.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = target.with_suffix(target.suffix + ".regenos-backup")
        if target.exists() and not backup.exists():
            shutil.copy2(target, backup)
        temporary = target.with_suffix(".regenos-tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
    data_root = (
        Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        if config_root is None
        else None
    )
    apply_preferences(root, data_root, branding["cursor_theme"])
