from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ai_os.config import AI_OS_HOME, ensure_runtime_tree, load_raw_config


WEB_ROOT = Path(__file__).with_name("web")
EDITABLE_KEYS = {
    "ollama_url",
    "ollama_model",
    "ai_provider",
    "api_key_env",
    "allow_external_apis",
    "allowed_api_hosts",
    "hyprland_enabled",
    "wake_word_enabled",
    "speech_enabled",
    "always_listening_enabled",
    "wake_word_threshold",
    "voice_command_seconds",
    "sandbox_lock_settings",
    "avatar_enabled",
    "avatar_corner",
    "avatar_scale",
    "avatar_animation_enabled",
    "avatar_accent",
    "whisper_cli",
    "whisper_model",
    "piper_model",
    "theme",
    "branding",
}
PROTECTED_KEYS = {"allow_external_apis", "hyprland_enabled", "always_listening_enabled", "ai_provider", "ollama_url"}


def _validate_setting(key: str, value: Any) -> Any:
    if key in {"ollama_url", "ollama_model", "ai_provider", "api_key_env", "whisper_cli", "whisper_model", "piper_model", "avatar_corner", "avatar_accent", "theme"}:
        if not isinstance(value, str) or len(value) > 512:
            raise ValueError(f"Invalid {key} value.")
        if key == "ai_provider" and value not in {"ollama", "openai_compatible"}:
            raise ValueError("Provider must be ollama or openai_compatible.")
        if key == "api_key_env" and not value.replace("_", "").isalnum():
            raise ValueError("API key must be referenced by an environment variable name.")
        return value
    if key in {"allow_external_apis", "hyprland_enabled", "wake_word_enabled", "speech_enabled", "always_listening_enabled", "sandbox_lock_settings", "avatar_enabled", "avatar_animation_enabled"}:
        if not isinstance(value, bool):
            raise ValueError(f"Invalid {key} value.")
        return value
    if key == "allowed_api_hosts":
        if not isinstance(value, list) or any(not isinstance(host, str) or len(host) > 253 for host in value):
            raise ValueError("Invalid allowed API hosts.")
        return value
    if key == "wake_word_threshold":
        return max(0.0, min(1.0, float(value)))
    if key == "voice_command_seconds":
        return max(2, min(30, int(value)))
    if key == "avatar_scale":
        return max(60, min(160, int(value)))
    if key == "branding":
        if not isinstance(value, dict):
            raise ValueError("Invalid branding settings.")
        clean = {str(name)[:64]: str(item)[:256] for name, item in value.items()}
        allowed = {"brand_name", "assistant_name", "logo_path", "wallpaper_path", "lockscreen_path", "icon_theme", "cursor_theme", "font"}
        if not set(clean).issubset(allowed) or any("\n" in item or "\r" in item for item in clean.values()):
            raise ValueError("Branding settings contain unsupported values.")
        for key_name in ("icon_theme", "cursor_theme", "font"):
            if key_name in clean and not re.fullmatch(r"[A-Za-z0-9 ._-]{1,80}", clean[key_name]):
                raise ValueError(f"Invalid {key_name}.")
        for key_name in ("logo_path", "wallpaper_path", "lockscreen_path"):
            if key_name in clean and clean[key_name] and not Path(clean[key_name]).is_absolute():
                raise ValueError(f"{key_name} must be an absolute path.")
        return clean
    raise ValueError(f"Unsupported setting: {key}")


def save_settings(
    changes: dict[str, Any],
    home: Path = AI_OS_HOME,
    *,
    human_confirmed: bool = False,
) -> dict[str, Any]:
    ensure_runtime_tree(home)
    current = load_raw_config(home)
    if current.get("sandbox_lock_settings"):
        protected = PROTECTED_KEYS.intersection(changes)
        if protected and not human_confirmed:
            raise PermissionError(
                "Sandbox lock requires local confirmation before changing: " + ", ".join(sorted(protected))
            )
    for key, value in changes.items():
        if key not in EDITABLE_KEYS:
            raise ValueError(f"Unsupported setting: {key}")
        current[key] = _validate_setting(key, value)
    if current.get("ai_provider") == "openai_compatible":
        if not current.get("allow_external_apis"):
            raise PermissionError("Enable approved external APIs before selecting a remote provider.")
        from urllib.parse import urlparse

        parsed = urlparse(str(current.get("ollama_url", "")))
        if parsed.scheme != "https" or parsed.hostname not in current.get("allowed_api_hosts", []):
            raise ValueError("Remote endpoints must be HTTPS and use an approved API host.")
    (home / "config.json").write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    _apply_user_appearance(current, home)
    return current


def _apply_user_appearance(config: dict[str, Any], home: Path) -> None:
    branding = config.get("branding", {})
    icon_theme = branding.get("icon_theme", "Papirus-Dark")
    cursor_theme = branding.get("cursor_theme", "Bibata-Modern-Ice")
    font = branding.get("font", "Noto Sans 10")
    gtk_dir = home.parent / ".config" / "gtk-3.0"
    gtk_dir.mkdir(parents=True, exist_ok=True)
    gtk_data = (
        "[Settings]\n"
        f"gtk-icon-theme-name={icon_theme}\n"
        f"gtk-cursor-theme-name={cursor_theme}\n"
        f"gtk-font-name={font}\n"
    )
    gtk_target = gtk_dir / "settings.ini"
    gtk_temp = gtk_target.with_suffix(".tmp")
    gtk_temp.write_text(gtk_data, encoding="utf-8")
    gtk_temp.replace(gtk_target)

    wallpaper = branding.get("wallpaper_path", "/usr/share/regenos/wallpapers/default.png")
    lockscreen = branding.get("lockscreen_path", "/usr/share/regenos/wallpapers/lockscreen.png")
    hypr_dir = home.parent / ".config" / "hypr"
    hypr_dir.mkdir(parents=True, exist_ok=True)
    for name, content in {
        "hyprpaper.conf": f"preload = {wallpaper}\nwallpaper = ,{wallpaper}\nsplash = false\n",
        "hyprlock.conf": f"background {{\n    monitor =\n    path = {lockscreen}\n    blur_passes = 2\n    brightness = 0.85\n}}\n\ninput-field {{\n    monitor =\n    size = 300, 56\n    position = 0, -120\n    dots_center = true\n    fade_on_empty = false\n    placeholder_text = Password\n}}\n",
    }.items():
        target = hypr_dir / name
        temporary = target.with_suffix(".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)


class SettingsHandler(BaseHTTPRequestHandler):
    server_version = "REGENOSSettings/1.0"

    def do_GET(self) -> None:  # noqa: N802
        if self.headers.get("Host") not in {"127.0.0.1:8765", "localhost:8765"}:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if self.path == "/api/config":
            self._send_json(HTTPStatus.OK, load_raw_config())
            return
        relative = "index.html" if self.path in {"/", "/index.html"} else self.path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "text/html" if target.suffix == ".html" else "text/css" if target.suffix == ".css" else "application/javascript"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def do_POST(self) -> None:  # noqa: N802
        if self.headers.get("Host") not in {"127.0.0.1:8765", "localhost:8765"}:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://127.0.0.1:8765", "http://localhost:8765"}:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if self.path != "/api/config":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32_768:
                raise ValueError("Invalid request size.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not isinstance(payload.get("changes"), dict):
                raise ValueError("Settings payload must contain a changes object.")
            self._send_json(
                HTTPStatus.OK,
                save_settings(payload["changes"], human_confirmed=payload.get("confirmation") == "APPLY"),
            )
        except (ValueError, PermissionError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), SettingsHandler)
    print("REGENOS Settings is available at http://127.0.0.1:8765", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
