from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable

import requests

from ai_os.config import load_config
from ai_os.logging_utils import configure_logging
from ai_os.security.consent_broker import ConsentRequest, ConsentDecision, request_cli_consent
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
        "ui_status": ui_tools.ui_status,
        "list_windows": ui_tools.list_windows,
    }


def json_default(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if hasattr(value, "value"):
        return value.value
    return str(value)


def system_prompt() -> str:
    return """You are the local AI-OS daemon.
Return ordinary helpful text unless a tool is needed.
When using a tool, return exactly one JSON object:
{"tool": "tool_name", "arguments": {"key": "value"}}
Never request destructive commands unless the user clearly asked.
Hyprland/Wayland UI automation is disabled until the user enables Phase 5."""


def ask_ollama(user_text: str) -> str:
    config = load_config()
    payload = {
        "model": config.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_text},
        ],
        "options": {"temperature": 0.2},
    }
    response = requests.post(config.ollama_url, json=payload, timeout=120)
    response.raise_for_status()
    return str(response.json()["message"]["content"])


def parse_tool_call(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict) and "tool" in parsed and "arguments" in parsed:
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
    model_text = ask_ollama(user_text)
    tool_call = parse_tool_call(model_text)
    if not tool_call:
        memory_tools.remember_event("assistant_text", {"user": user_text, "assistant": model_text})
        return {"type": "text", "content": model_text}
    result = execute_tool(tool_call["tool"], tool_call.get("arguments", {}), registry)
    return {"type": "tool_result", "tool": tool_call["tool"], "result": result}


def main() -> int:
    config = load_config()
    logger = configure_logging(config.log_dir)
    logger.info("AI-OS daemon started")
    print("AI-OS daemon ready. Type 'exit' to quit.")

    registry = build_tool_registry()
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


if __name__ == "__main__":
    raise SystemExit(main())

