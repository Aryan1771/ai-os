"""One-request JSON bridge for the C++ hub over private child-process pipes."""

from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from ai_os.config import AI_OS_HOME, DEFAULT_CONFIG, load_config, load_raw_config
from ai_os.conversation_memory import ConversationMemory
from ai_os.settings_store import (
    BOUNDS,
    CHOICES,
    PROTECTED_KEYS,
    apply_user_appearance,
    save_settings,
)


def revision(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def schema() -> list[dict]:
    fields = []
    labels = {
        "hardware_auto_adapt": "Adapt inference to this computer",
        "hardware_backend": "Default compute policy",
        "hardware_allow_model_fallback": "Allow installed fallback models",
        "hardware_fallback_models": "Allowed fallback models",
        "allow_external_apis": "Allow approved online providers",
        "allowed_api_hosts": "Approved hostnames",
        "speech_enabled": "Speak replies",
        "wake_word_threshold": "Wake-word threshold",
        "ollama_url": "Model endpoint",
        "ollama_model": "Model name",
        "api_key_env": "API key environment variable",
        "ai_provider": "Provider",
        "always_listening_enabled": "Listen for wake word",
        "wake_word_enabled": "Require wake word",
        "piper_model": "Piper voice model",
        "piper_length_scale": "Voice duration multiplier",
        "wake_word_model": "Custom wake-word model",
        "model_context_tokens": "Context window (tokens)",
        "memory_enabled": "Remember conversations and retrieve context notes",
        "memory_retention_days": "Conversation retention (days)",
        "theme": "Window theme",
        "sandbox_lock_settings": "Confirm protected settings changes",
        "whisper_cli": "Whisper executable",
        "voice_command_seconds": "Recording duration (seconds)",
    }
    for key, default in DEFAULT_CONFIG.items():
        page = "AI connection"
        if key.startswith("hardware_"):
            page = "Hardware"
        elif key.startswith("avatar_"):
            page = "Companion"
        elif key.startswith(("wake_", "whisper", "piper", "voice_")) or key in {
            "speech_enabled",
            "always_listening_enabled",
        }:
            page = "Voice & listening"
        elif key in {"theme", "branding"}:
            page = "Appearance"
        elif key.startswith("memory_"):
            page = "Memory preferences"
        elif key in {"sandbox_lock_settings", "hyprland_enabled"}:
            page = "Permissions"
        for name, value in default.items() if isinstance(default, dict) else [(None, default)]:
            path = f"{key}.{name}" if name else key
            label = labels.get(key, key.replace("avatar_", "").replace("_", " ").capitalize())
            if name:
                label = name.replace("_", " ").capitalize()
            kind = (
                "bool"
                if isinstance(value, bool)
                else "number"
                if isinstance(value, (int, float))
                else "lines"
                if isinstance(value, list)
                else "text"
            )
            field = {"key": path, "label": label, "page": page, "type": kind}
            if key in CHOICES:
                field.update(type="choice", choices=sorted(CHOICES[key]))
            if kind == "number":
                field.update(
                    min=BOUNDS.get(key, (0, 100))[0],
                    max=BOUNDS.get(key, (0, 100))[1],
                    integer=isinstance(value, int),
                )
            if key == "avatar_accent":
                field["type"] = "color"
            if key in {"whisper_cli", "whisper_model", "piper_model", "wake_word_model"} or (
                name and name.endswith("_path")
            ):
                field["type"] = "file"
            fields.append(field)
    return fields


def dispatch(request: dict, home: Path = AI_OS_HOME) -> dict:
    action = request.get("action")
    config = load_raw_config(home)
    if action in {"hardware", "hardware_override"}:
        from ai_os.hardware_profile import discover, refresh_profile, save_override

        if action == "hardware_override":
            if request.get("confirmed") is not True:
                raise PermissionError("Hardware overrides require local confirmation.")
            save_override(home, discover()["machine_key"], request.get("override"))
        return {"report": refresh_profile(home)}
    if action == "load":
        return {
            "config": config,
            "revision": revision(config),
            "fields": schema(),
            "protected": sorted(PROTECTED_KEYS),
            "home": str(home.resolve()),
        }
    if action == "save":
        if request.get("revision") != revision(config):
            raise ValueError("Settings changed in another process. Reload before saving.")
        changes = request.get("changes")
        if not isinstance(changes, dict):
            raise ValueError("Settings changes must be an object.")
        config = save_settings(changes, home, human_confirmed=request.get("confirmed") is True)
        return {"config": config, "revision": revision(config)}
    if action == "appearance":
        if request.get("confirmed") is not True:
            raise PermissionError("Desktop changes require confirmation.")
        apply_user_appearance(config)
        return {"message": "Appearance saved. Reload the affected desktop session/applications."}
    if action == "service":
        command = request.get("command")
        if command not in {"start", "stop", "restart", "is-active"}:
            raise ValueError("Unsupported service action")
        result = subprocess.run(
            ["systemctl", "--user", command, "ai-os.service"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode and command != "is-active":
            raise RuntimeError(result.stderr.strip() or "Service action failed")
        return {"message": result.stdout.strip() or f"Service {command} complete"}
    if action == "chat":
        from ai_os.ai_os_core import handle_user_text, json_default

        result = handle_user_text(request.get("text"), home=home)
        return {"response": json.loads(json.dumps(result, default=json_default))}
    if action in {"speech_test", "speech_text"}:
        from ai_os.companion_state import publish_state
        from ai_os.speech_queue import SpeechQueue

        voice = load_config(home)
        text = (
            "Hello. This is your REgenOS voice." if action == "speech_test" else request.get("text")
        )
        if action == "speech_text" and not voice.speech_enabled:
            raise PermissionError("Spoken replies are disabled.")
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Speech text must contain 1-8000 characters.")
        publish_state("speaking", home=home)
        try:
            SpeechQueue(voice.piper_model, length_scale=voice.piper_length_scale).speak_text(text)
        except Exception:
            publish_state("error", home=home)
            raise
        publish_state("idle", home=home)
        return {"message": "Voice playback completed"}
    if action in {"notes", "put_note", "delete_note", "clear_history", "history", "import_notes"}:
        memory = ConversationMemory(home)
        if (
            action in {"delete_note", "clear_history", "import_notes"}
            and request.get("confirmed") is not True
        ):
            raise PermissionError("This memory change requires confirmation.")
        if action == "put_note":
            memory.put(request.get("title"), request.get("body"), request.get("id"))
        elif action == "delete_note":
            memory.delete_note(request["id"])
        elif action == "clear_history":
            memory.clear_history()
        elif action == "history":
            return {"history": memory.history(days=config["memory_retention_days"])}
        elif action == "import_notes":
            notes = request.get("notes")
            if not isinstance(notes, list) or not 1 <= len(notes) <= 256:
                raise ValueError("Import requires 1-256 notes.")
            for note in notes:
                if (
                    not isinstance(note, dict)
                    or not isinstance(note.get("title"), str)
                    or not 1 <= len(note["title"].strip()) <= 120
                    or not isinstance(note.get("body"), str)
                    or not 1 <= len(note["body"].strip()) <= 8192
                ):
                    raise ValueError("Invalid note in import; nothing imported.")
            import time

            with memory.connect() as db:
                if db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] + len(notes) > 256:
                    raise ValueError("Import would exceed the 256-note limit.")
                db.executemany(
                    "INSERT INTO notes(title,body,updated) VALUES(?,?,?)",
                    [(n["title"], n["body"], time.time()) for n in notes],
                )
        return {"notes": memory.notes(), "path": str(memory.path)}
    raise ValueError("Unknown hub action")


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("Hub request exceeds 16 MiB")
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise ValueError("Hub request must be an object")
        with contextlib.redirect_stdout(sys.stderr):
            result = dispatch(request)
        reply = {"ok": True, **result}
    except Exception as exc:
        reply = {"ok": False, "error": str(exc)}
    sys.stdout.write(json.dumps(reply, ensure_ascii=True, allow_nan=False) + "\n")
    return 0 if reply["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
