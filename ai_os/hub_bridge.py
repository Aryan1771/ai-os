"""One-request JSON bridge for the C++ hub over private child-process pipes."""

from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
import sys
import signal
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


@contextlib.contextmanager
def _voice_turn(home: Path):
    """Avoid delayed/interleaved speech from independent native child requests."""
    from ai_os.speech_lease import speech_lease
    from ai_os.services.voice_errors import VoicePipelineError
    with speech_lease(home) as acquired:
        if not acquired:
            raise VoicePipelineError("voice_busy", "Another voice interaction is active. Please try again after it finishes.")
        yield


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
        "voice_command_seconds": "Wait for speech to start (seconds)",
        "voice_silence_seconds": "Finish after silence (seconds)",
        "voice_max_utterance_seconds": "Maximum utterance (seconds)",
    }
    for key, default in DEFAULT_CONFIG.items():
        page = "AI connection"
        if key.startswith("hardware_"):
            page = "Hardware"
        elif key.startswith("avatar_"):
            page = "Companion"
        elif key.startswith(("wake_", "whisper", "piper", "voice_", "speaker_")) or key in {
            "speech_enabled",
            "always_listening_enabled",
            "reply_language_mode",
        }:
            page = "Voice & listening"
        elif key in {"theme", "branding", "cursor_size"}:
            page = "Appearance"
        elif key.startswith("memory_") or key == "reinforced_memory_enabled":
            page = "Memory preferences"
        elif key in {"sandbox_lock_settings", "hyprland_enabled", "command_access"}:
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
            if key in {"whisper_cli", "whisper_model", "piper_model", "wake_word_model", "speaker_model"} or (
                name and name.endswith("_path")
            ):
                field["type"] = "file"
            fields.append(field)
    return fields


def dispatch(request: dict, home: Path = AI_OS_HOME) -> dict:
    action = request.get("action")
    config = load_raw_config(home)
    if action == "approved_cleanup":
        from ai_os.file_cleanup import execute_cleanup
        result = execute_cleanup(request.get("token"), home=home,
                                 human_confirmed=request.get("confirmed") is True,
                                 remember=request.get("remember") is True)
        return {"response": {"type": "tool_result", "tool": "cleanup_files", "result": result}}
    if action == "approved_research":
        from ai_os.research_reports import run_research, open_article_results
        result = run_research(request.get("topic"), home=home,
                              mode=request.get("mode", "articles"),
                              human_confirmed=request.get("confirmed") is True)
        if result.get("ok") is True and result.get("mode") == "articles":
            launch = open_article_results(result, human_confirmed=request.get("confirmed") is True)
            result = result | {"ok": launch.get("ok", False), "search_ok": True,
                               "opened": launch.get("opened", []), "message": launch.get("message", "Article launch was unavailable.")}
        return {"response": {"type": "tool_result", "tool": "research_topic", "result": result}}
    if action == "approved_power":
        from ai_os.power_actions import execute_power
        result = execute_power(request.get("power_action"), request.get("delay_minutes"),
                               human_confirmed=request.get("confirmed") is True)
        return {"response": {"type": "tool_result", "tool": "power_action", "result": result}}
    if action == "reviewed_action":
        from ai_os.reviewed_actions import execute
        result = execute(request.get("tool"), request.get("arguments"), home, confirmed=request.get("confirmed") is True)
        return {"response": {"type": "tool_result", "tool": request.get("tool"), "result": result}}
    if action in {"screen_comment", "screen_describe"}:
        from ai_os.ai_os_core import ask_screen, parse_visual_reply
        from ai_os.screen_context import read_observation, same_scene
        from ai_os.companion_state import read_state, publish_state
        from ai_os.speech_queue import SpeechQueue
        automatic = action == "screen_comment"
        observation = read_observation(home)
        if not observation or (automatic and not config["screen_commentary_enabled"]):
            return {"comment": ""}
        if read_state(home)["phase"] not in {"idle", "armed", "reply"}:
            return {"comment": ""}
        prompt = ("Offer one useful, calm comment about the visible work, at most 25 words. "
                  "If there is nothing useful to add, reply with an empty string. "
                  "Never read private details, identifiers or secrets aloud. Do not assume the user caused a change.") if automatic else "Briefly describe what is on my screen and offer relevant help. Do not expose secrets or private identifiers."
        answer = ask_screen(prompt, home)
        latest = load_raw_config(home)
        current = read_observation(home)
        if (not current or not same_scene(current["text"], observation["text"])
                or (automatic and not latest["screen_commentary_enabled"])
                or read_state(home)["phase"] not in {"idle", "armed", "reply"}):
            return {"comment": ""}
        text, avatar = parse_visual_reply(answer)
        text = text.strip().strip('"')[:400]
        if text and automatic and latest["screen_commentary_speech"] and latest["speech_enabled"]:
            voice = load_config(home)
            from ai_os.speech_lease import speech_lease
            with speech_lease(home) as acquired:
                # Commentary is optional: discard it when a user turn wins.
                if not acquired or read_state(home)["phase"] not in {"idle", "armed", "reply"}:
                    return {"comment": ""}
                publish_state("speaking", home=home, avatar=avatar)
                try:
                    SpeechQueue(voice.piper_model, hindi_model=voice.piper_hindi_model,
                                length_scale=voice.piper_length_scale,
                                emotion_enabled=latest["speech_emotion_enabled"]).speak_text(text, avatar=avatar)
                finally:
                    publish_state("idle", home=home)
        return {"comment": text}
    if action == "proactive_speech":
        from ai_os.ai_os_core import ask_ollama, parse_visual_reply, parse_tool_call
        from ai_os.companion_state import publish_state, read_state
        from ai_os.speech_queue import SpeechQueue
        if not config["speech_enabled"] or not config["proactive_speech_enabled"]:
            raise PermissionError("Proactive speech is disabled")
        if config["ai_provider"] != "ollama" or read_state(home)["phase"] not in {"idle", "armed"}:
            raise PermissionError("Proactive speech requires idle state and local Ollama")
        # Text-only generation: no tool execution or autonomous actions.
        answer = ask_ollama("Offer one brief optional check-in, at most 25 words, relevant to our context. Do not read private details, code, commands or saved secrets aloud. Avoid interrupting with urgent claims. You cannot use tools for this check-in.", set(), home)
        if parse_tool_call(answer):
            raise ValueError("Proactive tool requests are not allowed")
        text, avatar = parse_visual_reply(answer)
        latest = load_raw_config(home)
        if not latest["proactive_speech_enabled"] or not latest["speech_enabled"] or read_state(home)["phase"] not in {"idle", "armed"}:
            return {"message": "Check-in cancelled"}
        text = text[:300]
        voice = load_config(home)
        from ai_os.speech_lease import speech_lease
        with speech_lease(home) as acquired:
            if not acquired or read_state(home)["phase"] not in {"idle", "armed"}:
                return {"message": "Check-in cancelled"}
            publish_state("speaking", home=home, avatar=avatar)
            try:
                SpeechQueue(voice.piper_model, hindi_model=voice.piper_hindi_model,
                            length_scale=voice.piper_length_scale,
                            emotion_enabled=latest["speech_emotion_enabled"]).speak_text(text, avatar=avatar)
            finally:
                publish_state("idle", home=home)
        return {"message": "Proactive check-in completed"}
    if action == "confirm_access_grant":
        from ai_os.security.access_grants import GrantStore, SCOPE, USER_SCOPE
        from ai_os.ai_os_core import execute_tool, build_tool_registry, json_default
        if config["command_access"] != "supervised" or request.get("confirmed") is not True:
            raise PermissionError("Local confirmation and full command access are required")
        session = request.get("session", "default")
        grant = GrantStore(home).confirm(session, request.get("token"), human_confirmed=True)
        if grant["kind"] == "once":
            result = execute_tool("run_command", grant["spec"], build_tool_registry(home), home=home, session=session)
            return {"response": {"type": "tool_result", "tool": "run_command",
                                 "result": json.loads(json.dumps(result, default=json_default))}}
        return {"response": {"type": "text", "content": "Temporary access is active. Say 'revoke access' or use Revoke access to stop. " + (USER_SCOPE if grant["kind"] == "user" else SCOPE)}}
    if action == "approved_terminal_command":
        from ai_os.terminal_tasks import launch_terminal_command
        if config["command_access"] != "supervised" or request.get("confirmed") is not True:
            raise PermissionError("Enable full command access and review this exact command locally.")
        result = launch_terminal_command(request.get("arguments"), home=home, human_confirmed=True)
        return {"response": {"type": "tool_result", "tool": "run_terminal_command", "result": result}}
    if action == "approved_command":
        from ai_os.ai_os_core import build_tool_registry, execute_tool, json_default
        from ai_os.security.consent_broker import ConsentDecision

        if config["command_access"] != "supervised" or request.get("confirmed") is not True:
            raise PermissionError("Enable full command access and confirm the exact command locally.")
        # This bridge action is never a registered model tool. The native UI sends
        # it only after showing the command; same-user IPC is not OS isolation.
        arguments = request.get("arguments")
        if not isinstance(arguments, dict) or set(arguments) - {"command", "cwd", "timeout_sec"}:
            raise ValueError("Invalid command proposal")
        from ai_os.security.access_grants import GrantStore
        GrantStore(home).clear_pending(request.get("session", "default"))
        result = execute_tool("run_command", arguments, build_tool_registry(),
                              consent=lambda _: ConsentDecision.APPROVED)
        return {"response": {"type": "tool_result", "tool": "run_command",
                             "result": json.loads(json.dumps(result, default=json_default))}}
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
    if action == "voice_once":
        from ai_os.services.voice_input import capture_once
        from ai_os.ai_os_core import handle_user_text, json_default, spoken_response
        from ai_os.companion_state import publish_state
        from ai_os.speech_queue import SpeechQueue
        if request.get("confirmed") is not True:
            raise PermissionError("Click Speak once to authorize a bounded microphone capture")
        if config["always_listening_enabled"]:
            raise PermissionError("Disable continuous listening before using Speak once to avoid duplicate requests")
        voice = load_config(home)
        with _voice_turn(home):
            try:
                language_options = {}
                if getattr(voice, "reply_language_mode", "selected") == "match":
                    recognized = capture_once(voice, return_result=True)
                    text = recognized.text
                    language_options["reply_language"] = recognized.detected_language or "unknown"
                else:
                    text = capture_once(voice)
                response = handle_user_text(text, home=home, session=request.get("session", "default"),
                                            **language_options)
                # Respect speech-off changes made while recognition/model work ran.
                current = load_raw_config(home)
                if current["speech_enabled"]:
                    publish_state("speaking", home=home, avatar=response.get("avatar"))
                    speech = SpeechQueue(voice.piper_model, hindi_model=voice.piper_hindi_model,
                                         length_scale=voice.piper_length_scale,
                                         emotion_enabled=current["speech_emotion_enabled"])
                    for sentence in speech.sentence_chunks(spoken_response(response, **language_options)):
                        speech.speak_text(sentence, avatar=response.get("avatar"))
                return {"recognized_text": text, "response": json.loads(json.dumps(response, default=json_default))}
            finally:
                publish_state("idle", home=home)
    if action == "chat":
        from ai_os.ai_os_core import handle_user_text, json_default

        result = handle_user_text(request.get("text"), home=home, session=request.get("session", "default"),
                                  **({"interrupted_context": request["interrupted_context"]}
                                     if "interrupted_context" in request else {}))
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
        with _voice_turn(home):
            publish_state("speaking", home=home)
            try:
                SpeechQueue(voice.piper_model, length_scale=voice.piper_length_scale, hindi_model=voice.piper_hindi_model, emotion_enabled=config["speech_emotion_enabled"]).speak_text(text, avatar=request.get("avatar"))
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
    # A native Stop/Steer must unwind bounded tool cleanup, including subprocesses
    # that use a separate process group. SIGKILL alone cannot run their finally.
    def interrupted(_signum, _frame):
        raise SystemExit(130)
    if sys.platform == "linux":
        signal.signal(signal.SIGTERM, interrupted)
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
