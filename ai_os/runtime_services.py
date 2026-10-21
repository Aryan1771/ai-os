"""Reloadable voice worker and read-only device notifications for the resident core."""
from __future__ import annotations

import os
import json
from pathlib import Path
import signal
import subprocess
import sys
import threading
import tempfile
import time

from ai_os.config import atomic_json, load_raw_config

VOICE_KEYS = (
    "always_listening_enabled", "wake_word_enabled", "conversation_listening_enabled",
    "wake_backend", "wake_word_model", "wake_word_threshold", "voice_command_seconds",
    "voice_silence_seconds", "voice_max_utterance_seconds",
    "voice_input_target",
    "whisper_cli", "whisper_model", "whisper_language", "reply_language_mode",
    "speaker_recognition_enabled", "speaker_model", "speaker_threshold",
    "piper_model", "piper_hindi_model",
    "piper_length_scale", "speech_enabled", "speech_emotion_enabled",
)


def voice_mode(config):
    if not config["always_listening_enabled"]:
        return "off"
    if config["wake_word_enabled"]:
        return "wake"
    if config["conversation_listening_enabled"]:
        return "conversation"
    return "needs_activation_choice"


def voice_status(home, state, message="", *, error_code=""):
    path = home / "run/voice-status.json"
    previous = {}
    try:
        previous = json.loads(path.read_text())
        if not isinstance(previous, dict):
            previous = {}
        if (previous.get("state") == state and previous.get("message") == message
                and 0 <= time.time() - previous.get("updated", 0) < 15):
            return
    except (OSError, ValueError, TypeError):
        pass
    last_error = message if state == "error" else previous.get("last_error", "")
    if state in {"off", "reply"}:
        last_error = ""
    atomic_json(path, {"state": state, "message": message,
                       "last_error": last_error,
                       "last_error_code": error_code if state == "error" else ("" if state in {"off", "reply"} else previous.get("last_error_code", "")),
                       "updated": time.time()})


class VoiceSupervisor:
    def __init__(self, home):
        self.home = home
        self.process = None
        self.signature = None
        self.retry_after = 0
        self.audio_directory = None

    def stop(self, *, clear_status=True):
        if self.process is not None:
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            # Reap descendants too, including STT, model requests and audio playback.
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=2)
            self.process = None
        if self.audio_directory is not None:
            self.audio_directory.cleanup()
            self.audio_directory = None
        if clear_status:
            voice_status(self.home, "off")

    def tick(self):
        config = load_raw_config(self.home)
        signature = tuple(config[k] for k in VOICE_KEYS)
        if signature != self.signature:
            self.stop()
            self.signature = signature
            self.retry_after = 0
        mode = voice_mode(config)
        if mode in {"off", "needs_activation_choice"}:
            voice_status(self.home, mode,
                         "Choose Require wake word or Conversation listening in Voice settings."
                         if mode != "off" else "Microphone disabled")
            return
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    status = json.loads((self.home / "run/voice-status.json").read_text())
                    if time.time() - status["updated"] > 15:
                        voice_status(self.home, status["state"], status.get("message", ""))
                except (OSError, ValueError, KeyError, TypeError):
                    pass
                return
            self.stop(clear_status=False)
            self.retry_after = time.monotonic() + 15
            try:
                status = json.loads((self.home / "run/voice-status.json").read_text())
            except (OSError, ValueError):
                status = {}
            if not isinstance(status, dict) or status.get("state") != "error":
                voice_status(self.home, "error", "Voice worker stopped; retrying in 15 seconds", error_code="worker_exit")
        if time.monotonic() >= self.retry_after:
            voice_status(self.home, "starting", mode)
            temporary_root = self.home / "run/private"
            temporary_root.mkdir(parents=True, mode=0o700, exist_ok=True)
            self.audio_directory = tempfile.TemporaryDirectory(prefix="voice-worker-", dir=temporary_root)
            self.process = subprocess.Popen(
                [sys.executable, "-m", "ai_os.runtime_services", "--voice"],
                env=os.environ | {"AI_OS_HOME": str(self.home), "AI_OS_VOICE_TMP": self.audio_directory.name},
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True, shell=False,
            )


def device_notice(action, subsystem, device_type):
    """No serials, labels or device-provided text is sent to the model or a shell."""
    categories = {("usb", "usb_device"): "USB device", ("block", "disk"): "Storage device",
                  ("drm", ""): "Display connection", ("sound", ""): "Audio device"}
    category = "Display connection" if subsystem == "drm" else categories.get((subsystem, device_type))
    if category is None or action not in {"add", "remove", "change"}:
        return None
    return f"{category} { {'add': 'connected', 'remove': 'disconnected', 'change': 'changed'}[action]}."


def watch_devices(home: Path, stop: threading.Event):
    from ai_os.hardware_reactions import watch_devices as watch
    watch(home, stop)


def run_services(home, shutdown):
    from ai_os.activity_memory import collect_activity
    voice = VoiceSupervisor(home)
    devices = threading.Thread(target=watch_devices, args=(home, shutdown), daemon=True)
    devices.start()
    activity = threading.Thread(target=collect_activity, args=(home, shutdown), daemon=True)
    activity.start()
    try:
        while not shutdown.is_set():
            try:
                voice.tick()
            except (OSError, ValueError):
                voice.stop()
                voice_status(home, "error", "Could not load voice settings or start recorder")
            shutdown.wait(1)
    finally:
        voice.stop()
        activity.join(timeout=5)


def voice_worker():
    from ai_os.ai_os_core import build_tool_registry, handle_user_text, spoken_response
    from ai_os.companion_state import publish_state, read_state
    from ai_os.config import load_config
    from ai_os.services.listener import AlwaysListeningService
    from ai_os.services.stt import WhisperCppTranscriber
    from ai_os.speech_queue import SpeechQueue
    from ai_os.speech_lease import speech_lease
    from ai_os.speaker_filter import filter_utterance

    config = load_config()
    raw = load_raw_config(config.home)
    if voice_mode(raw) not in {"wake", "conversation"}:
        return 0
    speech = SpeechQueue(config.piper_model, hindi_model=config.piper_hindi_model,
                         length_scale=config.piper_length_scale,
                         emotion_enabled=raw["speech_emotion_enabled"])

    phase = "starting"

    def activity(value):
        nonlocal phase
        phase = value
        voice_status(config.home, value)
        publish_state(value, home=config.home)

    def capture_error(exc):
        from ai_os.services.voice_errors import diagnostic
        code, message = diagnostic(exc, phase)
        voice_status(config.home, "error", message, error_code=code)
        publish_state("error", home=config.home)

    def transcript(text):
        try:
            # Hold the output turn through reasoning and every spoken sentence.
            # Independent proactive/device/native processes must never interleave
            # an unrelated announcement with this reply.
            with speech_lease(config.home) as acquired:
                if not acquired:
                    from ai_os.services.voice_errors import VoicePipelineError
                    raise VoicePipelineError("voice_busy", "Another voice interaction is active. Please try again after it finishes.")
                activity("thinking")
                language_options = ({"reply_language": getattr(listener, "last_transcription_language", None) or "unknown"}
                                    if getattr(config, "reply_language_mode", "selected") == "match" else {})
                response = handle_user_text(text, build_tool_registry(config.home), home=config.home,
                                            **language_options)
                if config.speech_enabled:
                    activity("speaking")
                    for sentence in speech.sentence_chunks(spoken_response(response, **language_options)):
                        speech.speak_text(sentence, avatar=response.get("avatar"))
                voice_status(config.home, "reply")
        except Exception as exc:
            from ai_os.services.voice_errors import diagnostic
            code, message = diagnostic(exc, phase)
            voice_status(config.home, "error", message, error_code=code)
            if code != "voice_busy":
                publish_state("error", home=config.home)

    listener = AlwaysListeningService(
        run_dir=Path(os.environ.get("AI_OS_VOICE_TMP", str(config.run_dir))),
        transcriber=WhisperCppTranscriber(config.whisper_cli, config.whisper_model,
                                         language="auto" if getattr(config, "reply_language_mode", "selected") == "match" else config.whisper_language,
                                         detect_language=getattr(config, "reply_language_mode", "selected") == "match"),
        on_transcript=transcript, wake_word_threshold=config.wake_word_threshold,
        command_seconds=config.voice_command_seconds, wake_word_model=config.wake_word_model,
        silence_seconds=config.voice_silence_seconds,
        max_utterance_seconds=config.voice_max_utterance_seconds,
        input_target=config.voice_input_target,
        wake_backend=config.wake_backend, require_wake_word=config.wake_word_enabled,
        on_activity=activity, playback_active=lambda: read_state(config.home)["phase"] == "speaking",
        speaker_filter=lambda path: filter_utterance(path, config.home),
        on_error=capture_error,
    )
    try:
        listener.run_forever()
    except Exception as exc:
        from ai_os.services.voice_errors import diagnostic
        code, message = diagnostic(exc, phase)
        voice_status(config.home, "error", message, error_code=code)
        publish_state("error", home=config.home)
        return 1
    finally:
        listener.stop()
        speech.stop()
    return 0


if __name__ == "__main__":
    if sys.argv[1:] != ["--voice"]:
        raise SystemExit("Internal voice worker: use --voice")
    raise SystemExit(voice_worker())
