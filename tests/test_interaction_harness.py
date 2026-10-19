import json
from types import SimpleNamespace

import pytest

from ai_os import ai_os_core as core
from ai_os.config import load_raw_config
from ai_os.settings_store import save_settings
from ai_os.tool_protocol import catalog, normalize_message


def test_native_protocol_normalizes_calls_without_granting_approval():
    message = {"content": "", "tool_calls": [{"function": {
        "name": "open_website", "arguments": {"url": "https://youtube.com"},
    }}]}
    assert json.loads(normalize_message(message, {"open_website"}))["tool"] == "open_website"
    with pytest.raises(ValueError):
        normalize_message(message, {"run_command"})
    with pytest.raises(ValueError):
        normalize_message(message | {"tool_calls": message["tool_calls"] * 2}, {"open_website"})


def test_catalog_hides_internal_permission_parameters():
    tools = catalog(core.build_tool_registry(), {"run_command", "command_help", "switch_workspace"})
    schemas = {tool["function"]["name"]: tool["function"]["parameters"] for tool in tools}
    assert not {"approve", "home", "user_sandbox"} & schemas["run_command"]["properties"].keys()
    assert schemas["run_command"]["properties"]["command"]["type"] == "array"
    assert schemas["command_help"]["properties"]["command"]["type"] == "string"
    assert schemas["switch_workspace"]["properties"]["workspace"]["type"] == "integer"


def test_tool_discovery_expands_schemas_without_filling_normal_context():
    from ai_os.tool_protocol import active_catalog, discover
    registry = core.build_tool_registry()
    initial = active_catalog(registry, set(registry))
    assert len(initial) <= 10
    discovered = discover(registry, "audio volume")
    expanded = active_catalog(registry, set(registry), [{
        "call": {"tool": "discover_tools", "arguments": {"query": "audio volume"}},
        "result": discovered,
    }])
    assert "get_volume" in {item["function"]["name"] for item in expanded}


def test_ordinary_tool_context_leaves_room_for_recent_conversation(tmp_path, monkeypatch):
    from ai_os.conversation_memory import ConversationMemory
    save_settings({"hardware_auto_adapt": False}, tmp_path, human_confirmed=True)
    ConversationMemory(tmp_path).append("My fictional codename is Fern.", "I will remember Fern.")
    captured = []
    monkeypatch.setattr(core.requests, "post", lambda *a, **kw: (
        captured.append(kw["json"]) or SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: {"message": {"content": "Hello"}},
        )
    ))
    core.ask_ollama("Hi again", set(core.build_tool_registry(tmp_path)), tmp_path)
    assert any("Fern" in message.get("content", "") for message in captured[0]["messages"])


def test_tool_result_reaches_next_model_step_and_human_reply(tmp_path, monkeypatch):
    save_settings({"memory_enabled": False}, tmp_path, human_confirmed=True)
    requests = []

    def ask(*args, **kwargs):
        requests.append(kwargs)
        return ('{"tool":"read_state","arguments":{}}' if len(requests) == 1
                else '{"reply":"Your output volume is 40 percent."}')

    monkeypatch.setattr(core, "ask_ollama", ask)
    calls = []
    response = core.handle_user_text("Check my volume", {
        "read_state": lambda: calls.append(True) or {"ok": True, "volume": 40},
    }, home=tmp_path)
    assert response["content"] == "Your output volume is 40 percent."
    assert calls == [True]
    assert requests[1]["tool_trace"][0]["result"]["volume"] == 40


def test_repeated_tool_is_not_executed_twice(tmp_path, monkeypatch):
    save_settings({"memory_enabled": False}, tmp_path, human_confirmed=True)
    monkeypatch.setattr(core, "ask_ollama", lambda *a, **kw: '{"tool":"action","arguments":{}}')
    calls = []
    result = core.handle_user_text("Do this once", {
        "action": lambda: calls.append(True) or {"ok": True},
    }, home=tmp_path)
    assert calls == [True] and "repeated" in result["notice"]


def test_pending_approval_stops_planning(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "ask_ollama", lambda *a, **kw: '{"tool":"run_command","arguments":{"command":["touch","/tmp/re-test"]}}')
    monkeypatch.setattr(core, "request_cli_consent", lambda _: core.ConsentDecision.DENIED)
    result = core.handle_user_text("Create a file", {
        "run_command": lambda **kw: pytest.fail("Denied command executed"),
    }, home=tmp_path)
    assert result["result"]["approval_required"]
    assert "approval" in core.spoken_response(result)


def test_model_selected_desktop_answer_never_returns_to_planner_or_history(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "ask_ollama", lambda *a, **kw: '{"tool":"describe_screen","arguments":{"question":"What is this?"}}')
    monkeypatch.setattr(core, "_remember_turn", lambda *a, **kw: pytest.fail("Screen answer saved"))
    result = core.handle_user_text("Help me understand this", {
        "describe_screen": lambda question: "Visible synthetic application text",
    }, home=tmp_path)
    assert result["content"] == "Visible synthetic application text"


def test_native_tool_message_is_sent_to_ollama(tmp_path, monkeypatch):
    save_settings({"hardware_auto_adapt": False, "memory_enabled": False}, tmp_path, human_confirmed=True)
    captured = []

    def post(*a, **kw):
        captured.append(kw["json"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "message": {"tool_calls": [{"function": {
                "name": "open_website", "arguments": {"url": "https://youtube.com"},
            }}]},
        })

    monkeypatch.setattr(core.requests, "post", post)
    result = core.ask_ollama("Open YouTube", {"open_website"}, tmp_path)
    assert json.loads(result)["tool"] == "open_website"
    assert captured[0]["tools"][0]["function"]["name"] == "open_website"
    assert load_raw_config(tmp_path)["ollama_model"] == "qwen2.5:7b-instruct-q4_K_M"


def test_result_followup_uses_native_tool_role(tmp_path, monkeypatch):
    save_settings({"hardware_auto_adapt": False, "memory_enabled": False}, tmp_path, human_confirmed=True)
    captured = []
    monkeypatch.setattr(core.requests, "post", lambda *a, **kw: (
        captured.append(kw["json"]) or SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: {"message": {"content": "Result understood"}},
        )
    ))
    trace = [{"call": {"tool": "get_volume", "arguments": {}}, "result": {"ok": True, "volume": 40}}]
    assert core.ask_ollama("Volume?", {"get_volume"}, tmp_path, tool_trace=trace) == "Result understood"
    messages = captured[0]["messages"]
    assert messages[-1]["role"] == "tool" and messages[-1]["tool_name"] == "get_volume"


def test_automatic_activity_summary_is_excluded_from_other_provider(tmp_path, monkeypatch):
    from ai_os.activity_memory import ActivityMemory
    save_settings({"hardware_auto_adapt": False, "ai_provider": "openai_compatible",
                   "ollama_url": "http://127.0.0.1:1234/v1/chat/completions",
                   "activity_memory_enabled": True}, tmp_path, human_confirmed=True)
    monkeypatch.setattr(ActivityMemory, "summary", lambda _: pytest.fail("Automatic activity used for another provider"))
    monkeypatch.setattr(core.requests, "post", lambda *a, **kw: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"choices": [{"message": {"content": "Hi"}}]},
    ))
    assert core.ask_ollama("Hello", set(), tmp_path) == "Hi"


def test_accessibility_data_cannot_be_sent_to_another_provider(tmp_path, monkeypatch):
    save_settings({"hardware_auto_adapt": False, "ai_provider": "openai_compatible",
                   "ollama_url": "http://127.0.0.1:1234/v1/chat/completions",
                   "desktop_context_enabled": True}, tmp_path, human_confirmed=True)
    monkeypatch.setattr(core.requests, "post", lambda *a, **kw: pytest.fail("Desktop data sent"))
    with pytest.raises(PermissionError):
        core._ask_model("Explain", set(), tmp_path,
                        screen_observation={"source": "accessibility", "text": "SECRET"})
