from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ai_os.config import AI_OS_HOME, ensure_runtime_tree, load_raw_config


WEB_ROOT = Path(__file__).with_name("web")
EDITABLE_KEYS = {
    "ollama_url",
    "ollama_model",
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
PROTECTED_KEYS = {"allow_external_apis", "hyprland_enabled", "always_listening_enabled"}


def _validate_setting(key: str, value: Any) -> Any:
    if key in {"ollama_url", "ollama_model", "whisper_cli", "whisper_model", "piper_model", "avatar_corner", "avatar_accent", "theme"}:
        if not isinstance(value, str) or len(value) > 512:
            raise ValueError(f"Invalid {key} value.")
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
        return {str(name)[:64]: str(item)[:256] for name, item in value.items()}
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
    (home / "config.json").write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return current


class SettingsHandler(BaseHTTPRequestHandler):
    server_version = "AIOSSettings/1.0"

    def do_GET(self) -> None:  # noqa: N802
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
    print("AI-OS Settings is available at http://127.0.0.1:8765", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
