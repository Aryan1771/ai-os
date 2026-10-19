"""Read-only readiness report. Never opens the microphone, captures a screen or logs text."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import requests

from ai_os.config import AI_OS_HOME, load_config, load_raw_config
from ai_os.hardware_profile import local_api_url
from ai_os.runtime_services import voice_mode


def report(home: Path = AI_OS_HOME):
    config = load_config(home)
    raw = load_raw_config(home)
    piper = Path(sys.executable).with_name("piper")
    result = {
        "ok": True,
        "listening_mode": voice_mode(raw),
        "command_access": raw["command_access"],
        "broad_access_boundary_installed": Path("/usr/bin/bwrap").is_file(),
        "recorder_installed": bool(shutil.which("pw-record")),
        "whisper_cli_installed": bool(shutil.which(config.whisper_cli)),
        "whisper_model_present": config.whisper_model.is_file(),
        "piper_installed": piper.is_file() or bool(shutil.which("piper")),
        "voice_model_present": config.piper_model.is_file(),
        "voice_config_present": Path(str(config.piper_model) + ".json").is_file(),
        "playback_installed": bool(shutil.which("pw-play")),
        "speak_replies_enabled": config.speech_enabled,
        "reply_language_mode": config.reply_language_mode,
        "speaker_filter_enabled": raw["speaker_recognition_enabled"],
        "accessibility_context_enabled": raw["desktop_context_enabled"],
        "screen_sharing_enabled": raw["screen_context_enabled"],
        "app_usage_memory_enabled": raw["activity_memory_enabled"],
        "pipewire_source_query": "unavailable",
        "core_service": "unavailable",
        "local_model_endpoint": "unavailable",
    }
    from ai_os.speaker_identity import backend_available, profile_path
    result["speaker_backend_installed"] = backend_available()
    result["speaker_model_present"] = bool(raw["speaker_model"]) and Path(raw["speaker_model"]).expanduser().is_file()
    result["speaker_profile_present"] = profile_path(home).is_file()
    for key, command in (
        ("pipewire_source_query", ["/usr/bin/wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"]),
        ("core_service", ["/usr/bin/systemctl", "--user", "is-active", "ai-os.service"]),
    ):
        try:
            process = subprocess.run(command, capture_output=True, text=True,
                                     timeout=2, shell=False, stdin=subprocess.DEVNULL)
            if key == "core_service":
                result[key] = "active" if process.returncode == 0 else "inactive_or_inaccessible"
            else:
                result[key] = "ready" if process.returncode == 0 else "unavailable"
                if process.returncode == 0:
                    result["microphone_muted"] = "[MUTED]" in process.stdout
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(local_api_url(config.ollama_url, "tags"),
                                   timeout=2, allow_redirects=False)
            response.raise_for_status()
            models = response.json()["models"]
            result["local_model_endpoint"] = "reachable"
            result["selected_model_installed"] = config.ollama_model in {m.get("name") for m in models}
    except (requests.RequestException, ValueError, KeyError):
        pass
    try:
        status = json.loads((home / "run/voice-status.json").read_text())
        result["voice_worker"] = str(status["state"])[:40]
        result["voice_status_fresh"] = 0 <= time.time() - status["updated"] < 45
        result["last_voice_error_code"] = str(status.get("last_error_code", ""))[:80]
        result["last_voice_error"] = str(status.get("last_error", ""))[:300]
    except (OSError, ValueError, TypeError, KeyError):
        result["voice_worker"] = "no_status"
    return result


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
