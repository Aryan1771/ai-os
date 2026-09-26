from __future__ import annotations

import json
import os
import signal
import sys
import threading
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests

from ai_os.companion_state import SHAPE_NAMES, publish_state, read_state, visual_metadata
from ai_os.config import AI_OS_HOME, load_config
from ai_os.conversation_memory import ConversationMemory
from ai_os.logging_utils import configure_logging
from ai_os.security.consent_broker import ConsentDecision, ConsentRequest, request_cli_consent
from ai_os.services.listener import AlwaysListeningService
from ai_os.services.stt import WhisperCppTranscriber
from ai_os.settings_store import validate_model_endpoint
from ai_os.speech_queue import SpeechQueue
from ai_os.tools import memory_tools, system_tools, ui_tools

ToolFn = Callable[..., Any]


def build_tool_registry() -> dict[str, ToolFn]:
    return {
        "assess_command": system_tools.assess_command,
        "run_command": system_tools.run_command,
        "list_processes": system_tools.list_processes,
        "terminate_process": system_tools.terminate_process,
        "get_hardware_stats": system_tools.get_hardware_stats,
        "get_volume": system_tools.get_volume,
        "set_volume": system_tools.set_volume,
        "mute_volume": system_tools.mute_volume,
        "get_brightness": system_tools.get_brightness,
        "set_brightness": system_tools.set_brightness,
        "get_habits": memory_tools.get_habits,
        "set_habit": memory_tools.set_habit,
        "set_temporary_override": memory_tools.set_temporary_override,
        "resolve_preference": memory_tools.resolve_preference,
        "apply_slang_replacements": memory_tools.apply_slang_replacements,
        "remember_event": memory_tools.remember_event,
        "search_recent_events": memory_tools.search_recent_events,
        "store_semantic_memory": memory_tools.store_semantic_memory,
        "search_semantic_memory": memory_tools.search_semantic_memory,
        "ui_status": ui_tools.ui_status,
        "list_windows": ui_tools.list_windows,
    }


def json_default(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if hasattr(value, "value"):
        return value.value
    return str(value)


def system_prompt(registered_tools: set[str] | None = None) -> str:
    tool_names = ", ".join(
        sorted(registered_tools if registered_tools is not None else build_tool_registry())
    )
    return f"""You are the local REgenOS assistant.
For a text reply, prefer a JSON object with a reply string and optional avatar metadata:
{{"reply": "Your spoken answer", "avatar": {{"shape": "core", "emotions": {{"joy": 50}}}}}}
Plain text is also accepted. Avatar emotions are simulated presentation values from 0 to 100:
joy, curiosity, focus, calm, concern, energy. They never authorize actions.
Choose an avatar shape from: {", ".join(SHAPE_NAMES)}.
For a subject outside those shapes, you may add avatar.pixels: an array of 4 to 24
equal-length strings, each 4 to 24 characters. Draw a recognizable low-resolution silhouette.
Only use '.' for empty, '#' for body, '+' for accent, '*' for warm highlight, 'o' for dark eyes.
Avatar metadata contains only presentation data. Do not reveal hidden reasoning.
When using a tool, return exactly one JSON object:
{{"tool": "tool_name", "arguments": {{"key": "value"}}}}
You may call only these registered tools: {tool_names}.
Never invent a tool name or use an unregistered tool.
Use get_hardware_stats for hardware requests.
Never request destructive commands unless the user clearly asked.
Hyprland/Wayland UI automation is disabled until the user enables Phase 5."""


def ask_ollama(
    user_text: str, registered_tools: set[str] | None = None, home: Path = AI_OS_HOME
) -> str:
    config = load_config(home)
    context = (
        ConversationMemory(home).context(
            user_text,
            days=config.memory_retention_days,
            budget=min(8000, config.model_context_tokens),
        )
        if config.memory_enabled
        else []
    )
    payload = {
        "model": config.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt(registered_tools)},
            *context,
            {"role": "user", "content": user_text},
        ],
        "options": {"temperature": 0.2, "num_ctx": config.model_context_tokens},
    }
    headers: dict[str, str] = {}
    validate_model_endpoint(asdict(config))
    if config.ai_provider == "openai_compatible":
        api_key = os.environ.get(config.api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload.pop("options", None)
        payload["temperature"] = 0.2
        response = requests.post(
            config.ollama_url,
            json=payload,
            headers=headers,
            timeout=120,
            allow_redirects=False,
        )
    elif config.ai_provider == "ollama":
        response = requests.post(
            config.ollama_url, json=payload, timeout=120, allow_redirects=False
        )
    else:
        raise ValueError(f"Unsupported AI provider: {config.ai_provider}")
    response.raise_for_status()
    result = response.json()
    if config.ai_provider == "ollama":
        return str(result["message"]["content"])
    return str(result["choices"][0]["message"]["content"])


def parse_tool_call(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if (
        isinstance(parsed, dict)
        and isinstance(parsed.get("tool"), str)
        and isinstance(parsed.get("arguments"), dict)
    ):
        return parsed
    return None


def execute_tool(tool_name: str, arguments: dict[str, Any], registry: dict[str, ToolFn]) -> Any:
    if tool_name not in registry:
        return {"ok": False, "error": f"Unknown tool: {tool_name}"}

    arguments = dict(arguments)
    # An LLM cannot grant itself approval by putting approve=true in its arguments.
    arguments.pop("approve", None)
    if tool_name == "terminate_process":
        decision = request_cli_consent(
            ConsentRequest(
                action="terminate process",
                risk="moderate",
                reason=f"Stop process {arguments.get('pid')}",
            )
        )
        if decision is not ConsentDecision.APPROVED:
            return {"ok": False, "error": "User denied process termination."}
        arguments["approve"] = True
    if tool_name == "run_command":
        assessment = system_tools.assess_command(arguments.get("command", []))
        if assessment.requires_approval:
            decision = request_cli_consent(
                ConsentRequest(
                    action="run command",
                    risk=assessment.risk.value,
                    reason=assessment.reason,
                    command=assessment.command,
                )
            )
            if decision is not ConsentDecision.APPROVED:
                return {"ok": False, "error": "User denied command."}
            arguments["approve"] = True

    return registry[tool_name](**arguments)


def handle_user_text(
    user_text: str, registry: dict[str, ToolFn] | None = None, *, home: Path = AI_OS_HOME
) -> dict[str, Any]:
    if not isinstance(user_text, str) or not user_text.strip() or len(user_text) > 8000:
        raise ValueError("Messages must contain 1-8000 characters.")
    registry = registry if registry is not None else build_tool_registry()
    publish_state("thinking", user_text, home=home)
    try:
        model_text = ask_ollama(user_text, set(registry), home)
        tool_call = parse_tool_call(model_text)
        if tool_call:
            publish_state("working", tool_call["tool"], home=home)
            result = execute_tool(tool_call["tool"], tool_call["arguments"], registry)
            failed = (
                result.get("ok") is False
                if isinstance(result, dict)
                else getattr(result, "ok", True) is False
            )
            publish_state("error" if failed else "reply", tool_call["tool"], home=home)
            response = {"type": "tool_result", "tool": tool_call["tool"], "result": result}
            _remember_turn(home, user_text, json.dumps(response, default=json_default))
            return response
        text, avatar = parse_visual_reply(model_text)
        _remember_turn(home, user_text, text)
        publish_state("reply", text, home=home, avatar=avatar)
        return {"type": "text", "content": text, "avatar": avatar}
    except Exception:
        publish_state("error", home=home)
        raise


def _remember_turn(home: Path, user: str, reply: str) -> None:
    config = load_config(home)
    if config.memory_enabled:
        ConversationMemory(home).append(user, reply, days=config.memory_retention_days)


def parse_visual_reply(model_text: str) -> tuple[str, dict]:
    try:
        data = json.loads(model_text)
        if isinstance(data, dict) and isinstance(data.get("reply"), str):
            return data["reply"], visual_metadata(data.get("avatar"))
    except (ValueError, TypeError):
        pass
    return model_text, {}


def spoken_response(response: dict) -> str:
    if response["type"] == "text":
        return response["content"]
    result = response["result"]
    ok = result.get("ok", True) if isinstance(result, dict) else getattr(result, "ok", True)
    return "Task completed." if ok else "I could not complete that action. Please check the result."


def start_voice_services(
    config: Any, registry: dict[str, ToolFn], logger: Any
) -> AlwaysListeningService | None:
    """Start the microphone only after both explicit voice switches are enabled."""
    if not config.always_listening_enabled:
        return None
    if not config.wake_word_enabled:
        logger.warning(
            "Always listening was requested without wake-word gating; microphone remains off."
        )
        return None

    speech = (
        SpeechQueue(
            config.piper_model,
            length_scale=config.piper_length_scale,
            on_activity=lambda phase, text, avatar: publish_state(
                phase, text, home=config.home, avatar=avatar
            ),
        )
        if config.speech_enabled
        else None
    )
    if speech:
        threading.Thread(target=speech.run_forever, daemon=True, name="ai-os-speech").start()

    def on_transcript(transcript: str) -> None:
        try:
            response = handle_user_text(transcript, registry, home=config.home)
            print(
                json.dumps(
                    {"type": "voice", "transcript": transcript, "response": response},
                    default=json_default,
                )
            )
            if speech:
                speech.enqueue(spoken_response(response), avatar=response.get("avatar"))
        except Exception:
            publish_state("error", home=config.home)
            logger.exception("Voice request failed")

    listener = AlwaysListeningService(
        run_dir=config.run_dir,
        transcriber=WhisperCppTranscriber(config.whisper_cli, config.whisper_model),
        on_transcript=on_transcript,
        wake_word_threshold=config.wake_word_threshold,
        command_seconds=config.voice_command_seconds,
        wake_word_model=config.wake_word_model,
        on_activity=lambda phase: publish_state(phase, home=config.home),
        playback_active=lambda: (
            bool(speech and speech.is_speaking()) or read_state(config.home)["phase"] == "speaking"
        ),
    )

    def run_listener() -> None:
        try:
            listener.run_forever()
        except Exception:
            publish_state("error", home=config.home)
            logger.exception("Always-listening service stopped")

    threading.Thread(target=run_listener, daemon=True, name="ai-os-listener").start()
    logger.info("Always-listening service started with local wake-word gating")
    return listener


def main() -> int:
    config = load_config()
    logger = configure_logging(config.log_dir)
    logger.info("REgenOS daemon started")
    print("REgenOS ready. Type 'exit' to quit.")

    registry = build_tool_registry()
    listener = start_voice_services(config, registry, logger)
    shutdown = threading.Event()
    if not sys.stdin.isatty():
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, lambda _signal, _frame: shutdown.set())
    try:
        if not sys.stdin.isatty():
            logger.info("Running as a background service")
            while not shutdown.wait(1):
                pass
            return 0
        while True:
            try:
                user_text = input("ai-os> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if user_text.lower() in {"exit", "quit"}:
                return 0
            if not user_text:
                continue
            try:
                response = handle_user_text(user_text, registry)
                print(json.dumps(response, indent=2, default=json_default))
            except Exception as exc:
                logger.exception("Request failed")
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
    finally:
        if listener:
            listener.stop()
        publish_state("idle", home=config.home)


if __name__ == "__main__":
    raise SystemExit(main())
