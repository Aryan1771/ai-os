"""Expired model proposals cannot start fresh actions; all effects are synthetic."""

import json
from types import SimpleNamespace

import pytest

from ai_os import ai_os_core as core
from ai_os.settings_store import save_settings


@pytest.fixture
def clock(tmp_path, monkeypatch):
    save_settings({"memory_enabled": False, "hardware_auto_adapt": False},
                  tmp_path, human_confirmed=True)
    now = SimpleNamespace(value=100.0)
    monkeypatch.setattr(core, "time", SimpleNamespace(monotonic=lambda: now.value))
    monkeypatch.setattr(core, "runtime_policy", lambda _home: None)
    monkeypatch.setattr(core.knowledge, "search", lambda *_args: [])
    return now


@pytest.mark.parametrize("session", ["default", "synthetic"])
@pytest.mark.parametrize("elapsed", [120, 121])
def test_initial_model_deadline_is_forwarded_and_stale_action_is_rejected(
    tmp_path, monkeypatch, clock, session, elapsed,
):
    requests = []
    calls = []

    def ask(*_args, **kwargs):
        requests.append(kwargs)
        clock.value += elapsed
        return '{"tool":"synthetic_action","arguments":{}}'

    monkeypatch.setattr(core, "ask_ollama", ask)
    result = core.handle_user_text("Perform the synthetic task", {
        "synthetic_action": lambda: calls.append(True) or {"ok": True},
    }, home=tmp_path, session=session)
    assert requests[0]["deadline"] == 220.0
    assert calls == []
    assert result["code"] == "task_deadline_exceeded"
    assert "no action was run" in result["content"]


def test_expiry_during_working_status_is_rechecked_before_dispatch(
    tmp_path, monkeypatch, clock,
):
    monkeypatch.setattr(core, "ask_ollama", lambda *_args, **_kwargs:
                        '{"tool":"synthetic_action","arguments":{}}')

    def state(phase, *_args, **_kwargs):
        if phase == "working":
            clock.value = 221.0

    monkeypatch.setattr(core, "publish_state", state)
    result = core.handle_user_text("Perform the synthetic task", {
        "synthetic_action": lambda: pytest.fail("Expired dispatch ran"),
    }, home=tmp_path)
    assert result["code"] == "task_deadline_exceeded"


def test_stale_screen_proposal_does_not_enter_separate_screen_model(
    tmp_path, monkeypatch, clock,
):
    def ask(*_args, **_kwargs):
        clock.value = 221.0
        return '{"tool":"describe_screen","arguments":{"question":"Synthetic?"}}'

    monkeypatch.setattr(core, "ask_ollama", ask)
    result = core.handle_user_text("Perform the synthetic task", {
        "describe_screen": lambda **_kwargs: pytest.fail("Expired screen task ran"),
    }, home=tmp_path)
    assert result["code"] == "task_deadline_exceeded"


def test_direct_website_route_checks_deadline_before_launch(tmp_path, monkeypatch, clock):
    monkeypatch.setattr(core.desktop_tools, "launch_intent", lambda _text: None)

    def intent(_text):
        clock.value = 221.0
        return {"url": "https://example.com"}

    monkeypatch.setattr(core.desktop_tools, "website_intent", intent)
    monkeypatch.setattr(core, "ask_ollama", lambda *_args, **_kwargs:
                        pytest.fail("Direct launch requested inference"))
    result = core.handle_user_text("Open the synthetic website", {
        "open_website": lambda **_kwargs: pytest.fail("Expired launch ran"),
    }, home=tmp_path)
    assert result["code"] == "task_deadline_exceeded"


def test_completed_tool_result_survives_expired_followup_proposal(
    tmp_path, monkeypatch, clock,
):
    requests = []
    calls = []

    def ask(*_args, **kwargs):
        requests.append(kwargs)
        if len(requests) == 2:
            clock.value = 221.0
            return '{"tool":"next_action","arguments":{}}'
        return '{"tool":"read_state","arguments":{}}'

    monkeypatch.setattr(core, "ask_ollama", ask)
    result = core.handle_user_text("Perform the synthetic task", {
        "read_state": lambda: calls.append("read") or {"ok": True, "value": 40},
        "next_action": lambda: pytest.fail("Expired followup ran"),
    }, home=tmp_path)
    assert [request["deadline"] for request in requests] == [220.0, 220.0]
    assert calls == ["read"]
    assert result["tool"] == "read_state"
    assert result["result"] == {"ok": True, "value": 40}
    assert "no further action was started" in result["notice"]
    assert "time limit expired" in core.spoken_response(result)
    assert "समय सीमा समाप्त" in core.spoken_response(result, reply_language="hi")


def test_model_timeout_at_budget_preserves_result_and_reports_expiry(
    tmp_path, monkeypatch, clock,
):
    requests = []

    def ask(*_args, **kwargs):
        requests.append(kwargs)
        if len(requests) == 2:
            clock.value = 221.0
            raise core.requests.Timeout("Synthetic expired provider preparation")
        return '{"tool":"read_state","arguments":{}}'

    monkeypatch.setattr(core, "ask_ollama", ask)
    result = core.handle_user_text("Perform the synthetic task", {
        "read_state": lambda: {"ok": True, "value": 40},
    }, home=tmp_path)
    assert result["result"] == {"ok": True, "value": 40}
    assert result["code"] == "task_deadline_exceeded"
    assert "no further action was started" in result["notice"]


def test_dispatched_tool_may_finish_after_budget_without_repeating_or_followup(
    tmp_path, monkeypatch, clock,
):
    requests = []

    def ask(*_args, **kwargs):
        requests.append(kwargs)
        return '{"tool":"synthetic_action","arguments":{}}'

    def action():
        clock.value = 221.0
        return {"ok": True, "message": "Synthetic action finished."}

    monkeypatch.setattr(core, "ask_ollama", ask)
    result = core.handle_user_text("Perform the synthetic task", {
        "synthetic_action": action,
    }, home=tmp_path)
    assert len(requests) == 1
    assert result["result"]["ok"] is True
    assert "previous tool result is preserved" in result["notice"]


def test_expired_argument_failure_does_not_start_a_repair_inference(
    tmp_path, monkeypatch, clock,
):
    requests = []

    def ask(*_args, **kwargs):
        requests.append(kwargs)
        return '{"tool":"get_volume","arguments":{"unexpected":true}}'

    def rejected(**_kwargs):
        clock.value = 221.0
        raise ValueError("Synthetic invalid arguments")

    monkeypatch.setattr(core, "ask_ollama", ask)
    result = core.handle_user_text("Check the synthetic volume", {
        "get_volume": rejected,
    }, home=tmp_path)
    assert len(requests) == 1
    assert result["result"]["ok"] is False
    assert result["result"]["code"] == "read_only_arguments_rejected"
    assert "time limit expired" in result["notice"]


def test_already_expired_model_request_stops_before_preparation(
    tmp_path, monkeypatch, clock,
):
    monkeypatch.setattr(core.knowledge, "search", lambda *_args:
                        pytest.fail("Expired request prepared reference data"))
    monkeypatch.setattr(core.requests, "post", lambda *_args, **_kwargs:
                        pytest.fail("Expired request contacted a provider"))
    with pytest.raises(core.requests.Timeout, match="time limit expired"):
        core._ask_model("Synthetic question", set(), tmp_path, deadline=clock.value)


@pytest.mark.parametrize("provider", ["ollama", "openai_compatible"])
def test_expiry_during_preparation_stops_before_provider_post(
    tmp_path, monkeypatch, clock, provider,
):
    if provider == "openai_compatible":
        save_settings({"ai_provider": provider,
                       "ollama_url": "http://127.0.0.1:1234/v1/chat/completions"},
                      tmp_path, human_confirmed=True)

    def reference(*_args):
        clock.value = 221.0
        return []

    monkeypatch.setattr(core.knowledge, "search", reference)
    monkeypatch.setattr(core.requests, "post", lambda *_args, **_kwargs:
                        pytest.fail("Expired prepared request contacted a provider"))
    with pytest.raises(core.requests.Timeout, match="time limit expired"):
        core._ask_model("Synthetic question", set(), tmp_path, deadline=220.0)


def test_model_request_uses_remaining_fractional_timeout_without_extra_second(
    tmp_path, monkeypatch, clock,
):
    clock.value = 219.75
    requests = []

    def post(*_args, **kwargs):
        requests.append(kwargs)
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"message": {"content": "Synthetic reply"}})

    monkeypatch.setattr(core.requests, "post", post)
    assert core._ask_model("Synthetic question", set(), tmp_path, deadline=220.0) == "Synthetic reply"
    assert requests[0]["timeout"] == 0.25
    assert json.loads(json.dumps(requests[0]["json"]))["messages"][-1]["content"] == "Synthetic question"
