"""Legacy memory reads honor the active runtime and remote-sharing consent."""
from __future__ import annotations

import json

import pytest

from ai_os import ai_os_core as core
from ai_os.tools import memory_tools
from ai_os.settings_store import save_settings


READS = {
    "get_habits": {},
    "resolve_preference": {"key": "editor"},
    "apply_slang_replacements": {"text": "hiya"},
    "search_recent_events": {"query": "synthetic", "limit": 2},
    "search_semantic_memory": {"query": "synthetic", "limit": 2},
}


def remote_config(home, **settings):
    return save_settings({"ai_provider": "openai_compatible",
                          "ollama_url": "https://api.openai.com/v1/chat/completions",
                          "allow_external_apis": True, "memory_enabled": True,
                          "api_key_env": "REGENOS_TEST_MISSING_API_KEY", **settings},
                         home, human_confirmed=True)


@pytest.fixture
def blocked_legacy(monkeypatch):
    accessed = []
    for name in READS:
        def blocked(*args, _name=name, **kwargs):
            accessed.append((_name, args, kwargs))
            raise AssertionError("Memory permission must be checked before a legacy function reads data")

        monkeypatch.setattr(memory_tools, name, blocked)
    return accessed


@pytest.mark.parametrize("name", READS)
def test_memory_off_blocks_every_legacy_read_before_invocation(tmp_path, blocked_legacy, name):
    save_settings({"memory_enabled": False}, tmp_path, human_confirmed=True)
    registry = core.build_tool_registry(tmp_path)
    result = registry[name](**READS[name])
    assert result["ok"] is False and result["code"] == "memory_disabled"
    assert blocked_legacy == []


@pytest.mark.parametrize("name", READS)
def test_remote_memory_opt_out_blocks_before_any_read(tmp_path, blocked_legacy, name):
    remote_config(tmp_path, memory_allow_remote=False)
    result = core.build_tool_registry(tmp_path)[name](**READS[name])
    assert result["ok"] is False and result["code"] == "memory_remote_disabled"
    assert blocked_legacy == []


@pytest.mark.parametrize("name", READS)
def test_disabling_memory_after_registry_creation_takes_effect_immediately(tmp_path, blocked_legacy, name):
    save_settings({"memory_enabled": True}, tmp_path)
    registry = core.build_tool_registry(tmp_path)
    save_settings({"memory_enabled": False}, tmp_path, human_confirmed=True)
    result = registry[name](**READS[name])
    assert result["code"] == "memory_disabled"
    assert blocked_legacy == []


@pytest.mark.parametrize("name", READS)
def test_remote_opt_in_revocation_after_registry_creation_takes_effect(tmp_path, blocked_legacy, name):
    remote_config(tmp_path, memory_allow_remote=True)
    registry = core.build_tool_registry(tmp_path)
    save_settings({"memory_allow_remote": False}, tmp_path, human_confirmed=True)
    result = registry[name](**READS[name])
    assert result["code"] == "memory_remote_disabled"
    assert blocked_legacy == []


@pytest.fixture
def synthetic_legacy(tmp_path, monkeypatch):
    save_settings({"memory_enabled": True}, tmp_path)
    paths = memory_tools.MemoryPaths(habits=tmp_path / "habit_engine.json",
                                     slang=tmp_path / "slang_vocab.json",
                                     events=tmp_path / "data/events.jsonl")
    paths.habits.write_text(json.dumps({"defaults": {"editor": "synthetic-editor"}}))
    paths.slang.write_text(json.dumps({"replacements": {"hiya": "hello"}, "protected_terms": []}))
    paths.events.parent.mkdir(parents=True, exist_ok=True)
    paths.events.write_text(json.dumps({"kind": "synthetic-event", "payload": {"value": "sentinel"}}) + "\n")
    observed = []

    # Validate paths before any original helper executes; an unbound registry
    # must fail here rather than accidentally opening the developer's real data.
    for name in set(READS) - {"search_semantic_memory"}:
        original = getattr(memory_tools, name)

        def guarded(*args, _name=name, _original=original, **kwargs):
            actual = kwargs.get("paths")
            if actual is None and args and isinstance(args[-1], memory_tools.MemoryPaths):
                actual = args[-1]  # resolve_preference passes its verified path internally.
            assert actual == paths, "Legacy read did not use the selected runtime"
            observed.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(memory_tools, name, guarded)
    return paths, observed


def test_local_legacy_reads_use_only_configured_runtime_paths(tmp_path, synthetic_legacy):
    _paths, observed = synthetic_legacy
    registry = core.build_tool_registry(tmp_path)
    assert registry["get_habits"]()["defaults"]["editor"] == "synthetic-editor"
    assert registry["resolve_preference"](key="editor") == "synthetic-editor"
    assert registry["apply_slang_replacements"](text="hiya")["text"] == "hello"
    assert registry["search_recent_events"](query="synthetic")[0]["kind"] == "synthetic-event"
    assert set(observed) == set(READS) - {"search_semantic_memory"}


def test_semantic_read_receives_active_home_and_remains_unprovisioned(tmp_path, monkeypatch):
    save_settings({"memory_enabled": True}, tmp_path)
    original = memory_tools.search_semantic_memory
    observed = []

    def guarded(*args, **kwargs):
        assert kwargs.get("home") == tmp_path
        observed.append(kwargs["home"])
        return original(*args, **kwargs)

    monkeypatch.setattr(memory_tools, "search_semantic_memory", guarded)
    result = core.build_tool_registry(tmp_path)["search_semantic_memory"](query="Synthetic")
    assert result["code"] == "semantic_setup_required" and observed == [tmp_path]


def test_remote_memory_sharing_requires_trusted_saved_opt_in(tmp_path, synthetic_legacy):
    remote_config(tmp_path, memory_allow_remote=False)
    before = (tmp_path / "config.json").read_bytes()
    with pytest.raises(PermissionError):
        save_settings({"memory_allow_remote": True}, tmp_path)
    assert (tmp_path / "config.json").read_bytes() == before
    registry = core.build_tool_registry(tmp_path)
    assert registry["get_habits"]()["code"] == "memory_remote_disabled"
    save_settings({"memory_allow_remote": True}, tmp_path, human_confirmed=True)
    assert registry["get_habits"]()["defaults"]["editor"] == "synthetic-editor"


@pytest.mark.parametrize("provider,url", [
    ("ollama", "http://127.0.0.1:11434/api/chat"),
    ("openai_compatible", "http://localhost:8080/v1/chat/completions"),
    ("openai_compatible", "http://[::1]:8080/v1/chat/completions"),
])
def test_loopback_compatible_models_remain_local_without_remote_memory_grant(
    tmp_path, synthetic_legacy, provider, url,
):
    save_settings({"ai_provider": provider, "ollama_url": url, "memory_enabled": True,
                   "memory_allow_remote": False}, tmp_path, human_confirmed=True)
    result = core.build_tool_registry(tmp_path)["get_habits"]()
    assert result["defaults"]["editor"] == "synthetic-editor"


def test_model_arguments_cannot_grant_remote_memory_consent(tmp_path, blocked_legacy):
    remote_config(tmp_path, memory_allow_remote=False)
    registry = core.build_tool_registry(tmp_path)
    try:
        result = core.execute_tool("get_habits", {"human_confirmed": True, "memory_allow_remote": True},
                                   registry, home=tmp_path)
    except TypeError:
        pass  # Rejecting unsupported model-supplied fields also fails closed.
    else:
        assert result["ok"] is False and result["code"] == "memory_remote_disabled"
    assert blocked_legacy == []


def test_fake_remote_discovery_then_memory_denial_never_transmits_legacy_reference(
    tmp_path, blocked_legacy, monkeypatch,
):
    remote_config(tmp_path, memory_allow_remote=False)
    from ai_os.conversation_memory import ConversationMemory

    ConversationMemory(tmp_path).append("SYNTHETIC_PRIVATE_MEMORY_MARKER", "Never share automatically")
    monkeypatch.setattr(core, "runtime_policy", lambda _home: None)
    monkeypatch.setattr(core.knowledge, "search", lambda *_args, **_kwargs: [])
    payloads = []
    replies = [
        {"tool_calls": [{"function": {"name": "discover_tools", "arguments": '{"query":"get_habits"}'}}]},
        {"tool_calls": [{"function": {"name": "get_habits", "arguments": "{}"}}]},
    ]

    class Response:
        def __init__(self, message):
            self.message = message

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": self.message}]}

    def fake_post(*_args, **kwargs):
        payloads.append(kwargs["json"])
        assert kwargs["allow_redirects"] is False
        return Response(replies.pop(0))

    monkeypatch.setattr(core.requests, "post", fake_post)
    response = core.handle_user_text("Can you recall my habits?", home=tmp_path)
    assert response["type"] == "tool_result" and response["tool"] == "get_habits"
    assert response["result"]["code"] == "memory_remote_disabled"
    assert len(payloads) == 2 and replies == []
    assert "SYNTHETIC_PRIVATE_MEMORY_MARKER" not in json.dumps(payloads)
    assert "memory_remote_disabled" not in json.dumps(payloads)  # denial stops before a third model turn
    assert blocked_legacy == []


@pytest.mark.parametrize("sharing", ["memory_disabled", "memory_remote_disabled"])
def test_replayed_memory_trace_is_blocked_before_inference_after_revocation(tmp_path, monkeypatch, sharing):
    remote_config(tmp_path, memory_enabled=sharing != "memory_disabled", memory_allow_remote=False)
    monkeypatch.setattr(core, "runtime_policy", lambda _home: None)
    calls = []

    def forbidden_post(*args, **kwargs):
        calls.append(kwargs)
        raise AssertionError("Revoked legacy reference must not enter model inference")

    monkeypatch.setattr(core.requests, "post", forbidden_post)
    trace = [{"call": {"tool": "get_habits", "arguments": {}},
              "result": {"private_note": "SYNTHETIC_CACHED_PRIVATE_RESULT"}}]
    with pytest.raises((PermissionError, ValueError, RuntimeError)):
        core.ask_ollama("A current question", {"get_habits"}, tmp_path, tool_trace=trace)
    assert calls == []


def test_revocation_between_legacy_read_and_followup_does_not_send_cached_private_result(tmp_path, monkeypatch):
    remote_config(tmp_path, memory_allow_remote=True)
    monkeypatch.setattr(core, "runtime_policy", lambda _home: None)
    monkeypatch.setattr(core.knowledge, "search", lambda *_args, **_kwargs: [])
    reads = []

    def read_then_revoke(*args, **kwargs):
        assert kwargs.get("paths").habits == tmp_path / "habit_engine.json"
        reads.append(True)
        save_settings({"memory_allow_remote": False}, tmp_path, human_confirmed=True)
        return {"defaults": {"private_preference": "SYNTHETIC_READ_THEN_REVOKED_RESULT"}}

    monkeypatch.setattr(memory_tools, "get_habits", read_then_revoke)
    payloads = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"tool_calls": [{"function": {
                "name": "get_habits", "arguments": "{}",
            }}]}}]}

    def one_post_only(*args, **kwargs):
        payloads.append(kwargs["json"])
        assert len(payloads) == 1, "Consent revocation must stop the follow-up model call"
        return Response()

    monkeypatch.setattr(core.requests, "post", one_post_only)
    registry = {"get_habits": core.build_tool_registry(tmp_path)["get_habits"]}
    try:
        core.handle_user_text("Recall my habits", registry=registry, home=tmp_path)
    except (PermissionError, ValueError, RuntimeError):
        pass  # A public refusal also preserves the boundary after revocation.
    assert reads == [True] and len(payloads) == 1
    assert "SYNTHETIC_READ_THEN_REVOKED_RESULT" not in json.dumps(payloads)


def test_trace_permission_is_rechecked_immediately_before_network_post(tmp_path, monkeypatch):
    remote_config(tmp_path, memory_allow_remote=True)
    monkeypatch.setattr(core, "runtime_policy", lambda _home: None)
    calls = []

    def revoke_during_payload_preparation(*args, **kwargs):
        save_settings({"memory_allow_remote": False}, tmp_path, human_confirmed=True)
        return []

    monkeypatch.setattr(core.knowledge, "search", revoke_during_payload_preparation)

    def forbidden_post(*args, **kwargs):
        calls.append(kwargs)
        raise AssertionError("A cached permission must not authorize the final network post")

    monkeypatch.setattr(core.requests, "post", forbidden_post)
    trace = [{"call": {"tool": "get_habits", "arguments": {}},
              "result": {"private_note": "SYNTHETIC_BEFORE_POST_REVOCATION"}}]
    with pytest.raises((PermissionError, ValueError, RuntimeError)):
        core.ask_ollama("A current question", {"get_habits"}, tmp_path, tool_trace=trace)
    assert calls == []
