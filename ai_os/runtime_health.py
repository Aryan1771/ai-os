"""Read-only readiness report. Never opens the microphone, captures a screen or logs text."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

import requests

from ai_os.config import AI_OS_HOME, load_config, load_raw_config
from ai_os.hardware_profile import local_api_url
from ai_os.runtime_services import voice_mode
from ai_os.services.stt import WhisperCppTranscriber
from ai_os.services.voice_errors import VOICE_MESSAGES
from ai_os.services.wakeword import WakeWordService


def voice_readiness(config, raw):
    """Asset/dependency inspection only; it does not load or run neural models."""
    transcriber = WhisperCppTranscriber(
        config.whisper_cli, config.whisper_model, language=config.whisper_language,
        detect_language=config.reply_language_mode == "match",
    )
    ready, reason = transcriber.availability()
    if config.wake_backend == "re_whisper":
        wake_ready, wake_reason = WhisperCppTranscriber(
            config.whisper_cli, config.whisper_model, language="en",
        ).availability()
    else:
        wake_ready, wake_reason = WakeWordService(
            config.wake_word_threshold, config.wake_word_model,
        ).availability()
    hindi = config.piper_hindi_model
    return {
        "transcriber_ready": ready,
        "transcriber_status": reason,
        "wake_backend": config.wake_backend,
        "wake_assets_ready": wake_ready,
        "wake_status": wake_reason,
        "wake_check": "static_assets_only; detection_accuracy_not_tested",
        "hindi_voice_model_present": bool(hindi and hindi.is_file()),
        "hindi_voice_config_present": bool(hindi and Path(str(hindi) + ".json").is_file()),
        "hindi_voice_required": bool(raw["speech_enabled"] and (
            config.reply_language_mode == "match" or config.whisper_language == "hi")),
    }


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
        "microphone_selection": "explicit" if config.voice_input_target else "system_default",
        "selected_input_status": "not_checked" if config.voice_input_target else "system_default",
        "microphone_mute_check": "not_checked",
        "core_service": "unavailable",
        "local_model_endpoint": "unavailable",
    }
    result.update(voice_readiness(config, raw))
    from ai_os.speaker_identity import backend_available, profile_path
    result["speaker_backend_installed"] = backend_available()
    result["speaker_model_present"] = bool(raw["speaker_model"]) and Path(raw["speaker_model"]).expanduser().is_file()
    result["speaker_profile_present"] = profile_path(home).is_file()
    try:
        info = profile_path(home).lstat()
        result["speaker_profile_private"] = (stat.S_ISREG(info.st_mode)
                                             and info.st_uid == os.getuid()
                                             and not info.st_mode & 0o077)
    except OSError:
        result["speaker_profile_private"] = False
    result["speaker_profile_check"] = "presence_permissions_only; personal_matching_not_tested"
    for key, command in (
        ("pipewire_source_query", ["/usr/bin/wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"]),
        ("core_service", ["/usr/bin/systemctl", "--user", "is-active", "ai-os.service"]),
    ):
        if key == "pipewire_source_query" and config.voice_input_target:
            from ai_os.audio_input import AudioInputError, discover_input_devices, validate_input_target
            try:
                selected = validate_input_target(config.voice_input_target)
                present = selected in {item.target for item in discover_input_devices()}
                result[key] = "ready" if present else "unavailable"
                result["selected_input_status"] = "present" if present else "unavailable"
            except (ValueError, AudioInputError):
                result["selected_input_status"] = "unavailable"
            result["microphone_mute_check"] = "not_checked_for_explicit_input"
            continue
        try:
            process = subprocess.run(command, capture_output=True, text=True,
                                     timeout=2, shell=False, stdin=subprocess.DEVNULL)
            if key == "core_service":
                result[key] = "active" if process.returncode == 0 else "inactive_or_inaccessible"
            else:
                result[key] = "ready" if process.returncode == 0 else "unavailable"
                if process.returncode == 0:
                    result["microphone_muted"] = "[MUTED]" in process.stdout
                    result["microphone_mute_check"] = "default_source_only"
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
        status_path = home / "run/voice-status.json"
        if status_path.stat().st_size > 4096:
            raise ValueError("Voice status is too large")
        status = json.loads(status_path.read_text())
        state = status["state"]
        result["voice_worker"] = (state if state in {"off", "starting", "armed", "listening", "transcribing",
                                                   "thinking", "speaking", "reply", "error", "needs_activation_choice"}
                                  else "unknown")
        result["voice_status_fresh"] = 0 <= time.time() - status["updated"] < 45
        code = status.get("last_error_code", "")
        result["last_voice_error_code"] = code if code in VOICE_MESSAGES else ""
        result["last_voice_error"] = VOICE_MESSAGES.get(code, "")
    except (OSError, ValueError, TypeError, KeyError):
        result["voice_worker"] = "no_status"
    blockers = []
    for key, code in (("recorder_installed", "recorder_missing"), ("transcriber_ready", "transcriber_unavailable")):
        if not result[key]:
            blockers.append(code)
    if raw["wake_word_enabled"] and not result["wake_assets_ready"]:
        blockers.append("wake_assets_unavailable")
    if raw["speech_enabled"]:
        for key, code in (("piper_installed", "piper_missing"), ("voice_model_present", "english_voice_missing"),
                          ("voice_config_present", "english_voice_config_missing"), ("playback_installed", "playback_missing")):
            if not result[key]:
                blockers.append(code)
        if result["hindi_voice_required"] and not (
            result["hindi_voice_model_present"] and result["hindi_voice_config_present"]
        ):
            blockers.append("hindi_voice_assets_missing")
    if raw["speaker_recognition_enabled"] and not (
        result["speaker_backend_installed"] and result["speaker_model_present"] and result["speaker_profile_private"]
    ):
        blockers.append("speaker_filter_setup_incomplete")
    result["voice_assets_ready"] = not blockers
    if result["pipewire_source_query"] != "ready":
        blockers.append("pipewire_input_unverified")
    elif result.get("microphone_muted"):
        blockers.append("microphone_muted")
    if config.ai_provider == "ollama":
        if result["local_model_endpoint"] != "reachable":
            blockers.append("local_model_unreachable")
        elif not result.get("selected_model_installed"):
            blockers.append("selected_model_missing")
    else:
        blockers.append("remote_provider_not_checked")
    result["voice_blockers"] = blockers
    result["voice_ready"] = not blockers
    result["voice_acceptance"] = "hardware_microphone_and_language_accuracy_not_tested"
    return result


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
