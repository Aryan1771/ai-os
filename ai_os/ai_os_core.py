from __future__ import annotations

import json
import os
import signal
import sys
import threading
from dataclasses import asdict
from typing import Any, Callable

import requests

from ai_os.config import load_config
from ai_os.logging_utils import configure_logging
from ai_os.security.consent_broker import ConsentRequest, ConsentDecision, request_cli_consent
from ai_os.services.listener import AlwaysListeningService
from ai_os.services.external_api import validate_external_url
from ai_os.services.stt import WhisperCppTranscriber
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
    tool_names = ", ".join(sorted(registered_tools or build_tool_registry()))
    return f"""You are the local AI-OS daemon.
Return ordinary helpful text unless a tool is needed.
When using a tool, return exactly one JSON object:
{{"tool": "tool_name", "arguments": {{"key": "value"}}}}
You may call only these registered tools: {tool_names}.
Never invent a tool name or use an unregistered tool.
Use get_hardware_stats for hardware requests.
Never request destructive commands unless the user clearly asked.
Hyprland/Wayland UI automation is disabled until the user enables Phase 5."""


def ask_ollama(user_text: str, registered_tools: set[str] | None = None) -> str:
    config = load_config()
    payload = {
        "model": config.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt(registered_tools)},
            {"role": "user", "content": user_text},
        ],
        "options": {"temperature": 0.2},
    }
    headers: dict[str, str] = {}
    if config.ai_provider == "openai_compatible":
        error = validate_external_url(config.ollama_url, config)
        if error:
            raise ValueError(error)
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
        if not config.ollama_url.startswith("http://127.0.0.1:") and not config.ollama_url.startswith("http://localhost:"):
            raise ValueError("Ollama must use a loopback URL. Use the allowlisted OpenAI-compatible provider mode for remote services.")
        response = requests.post(config.ollama_url, json=payload, timeout=120)
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


def handle_user_text(user_text: str, registry: dict[str, ToolFn] | None = None) -> dict[str, Any]:
    registry = registry or build_tool_registry()
    model_text = ask_ollama(user_text, set(registry))
    tool_call = parse_tool_call(model_text)
    if not tool_call:
        memory_tools.remember_event("assistant_text", {"user": user_text, "assistant": model_text})
        return {"type": "text", "content": model_text}
    result = execute_tool(tool_call["tool"], tool_call.get("arguments", {}), registry)
    return {"type": "tool_result", "tool": tool_call["tool"], "result": result}


def start_voice_services(config: Any, registry: dict[str, ToolFn], logger: Any) -> AlwaysListeningService | None:
    """Start the microphone only after both explicit voice switches are enabled."""
    if not config.always_listening_enabled:
        return None
    if not config.wake_word_enabled:
        logger.warning("Always listening was requested without wake-word gating; microphone remains off.")
        return None

    speech = SpeechQueue(config.piper_model) if config.speech_enabled else None
    if speech:
        threading.Thread(target=speech.run_forever, daemon=True, name="ai-os-speech").start()

    def on_transcript(transcript: str) -> None:
        try:
            publish_avatar_state(transcript, "listening", config.run_dir)
            response = handle_user_text(transcript, registry)
            assistant_text = response.get("content", "")
            if not assistant_text:
                assistant_text = json.dumps(response, default=json_default)
            combined_context = f"{transcript} {assistant_text}"
            publish_avatar_state(combined_context, _avatar_emotion(assistant_text), config.run_dir)
            print(json.dumps({"type": "voice", "transcript": transcript, "response": response}, default=json_default))
            if speech:
                content = response.get("content") if response.get("type") == "text" else "Task completed."
                speech.enqueue(str(content))
        except Exception:
            publish_avatar_state(transcript, "curious", config.run_dir)
            logger.exception("Voice request failed")

    listener = AlwaysListeningService(
        run_dir=config.run_dir,
        transcriber=WhisperCppTranscriber(config.whisper_cli, config.whisper_model),
        on_transcript=on_transcript,
        wake_word_threshold=config.wake_word_threshold,
        command_seconds=config.voice_command_seconds,
    )

    def run_listener() -> None:
        try:
            listener.run_forever()
        except Exception:
            logger.exception("Always-listening service stopped")

    threading.Thread(target=run_listener, daemon=True, name="ai-os-listener").start()
    logger.info("Always-listening service started with local wake-word gating")
    return listener


def publish_avatar_state(text: str, emotion: str, run_dir: Any) -> None:
    lowered = text.lower()
    shape = "core"
    for terms, candidate in (
        (("music", "song", "melody", "sound"), "music"),
        (("love", "heart", "care"), "heart"),
        (("code", "python", "program", "script"), "code"),
        (("idea", "think", "plan"), "idea"),
        (("weather", "cloud", "rain"), "cloud"),
    ):
        if any(term in lowered for term in terms):
            shape = candidate
            break
    run_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / "avatar_state.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"shape": shape, "emotion": emotion}), encoding="utf-8")
    temporary.replace(target)


def _avatar_emotion(text: str) -> str:
    lowered = text.lower()
    for terms, emotion in (
        (("sorry", "unfortunately", "sad", "regret"), "sad"),
        (("?", "wonder", "perhaps", "maybe"), "curious"),
        (("great", "glad", "happy", "done", "completed"), "happy"),
    ):
        if any(term in lowered for term in terms):
            return emotion
    return "calm"


def main() -> int:
    config = load_config()
    logger = configure_logging(config.log_dir)
    logger.info("REGENOS daemon started")
    print("REGENOS ready. Type 'exit' to quit.")

    registry = build_tool_registry()
    listener = start_voice_services(config, registry, logger)
    shutdown = threading.Event()
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


if __name__ == "__main__":
    raise SystemExit(main())
