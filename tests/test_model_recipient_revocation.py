"""Prepared private context cannot survive revoked consent or recipient drift."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_os import ai_os_core as core
from ai_os.settings_store import save_settings


REMOTE = "https://api.openai.com/v1/chat/completions"
LOCAL = "http://127.0.0.1:11434/api/chat"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(core, "runtime_policy", lambda *_: None)
    monkeypatch.setattr(core.knowledge, "search", lambda *_: [])

    def record_post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "message": {"content": "Synthetic local response"},
            "choices": [{"message": {"content": "Synthetic compatible response"}}],
        })

    monkeypatch.setattr(core.requests, "post", record_post)
    return tmp_path, calls


def configure(home, *, remote=True, **overrides):
    return save_settings({"ai_provider": "openai_compatible" if remote else "ollama",
                          "ollama_url": REMOTE if remote else LOCAL,
                          "allow_external_apis": remote, "memory_enabled": True,
                          "memory_allow_remote": remote, "hardware_auto_adapt": False,
                          **overrides}, home, human_confirmed=True)


def test_steering_recheck_cannot_treat_old_remote_recipient_as_new_local_target(isolated, monkeypatch):
    home, calls = isolated
    configure(home, memory_enabled=False)

    def change_connection(*_):
        configure(home, remote=False, memory_enabled=False, memory_allow_remote=False)
        return []

    monkeypatch.setattr(core.knowledge, "search", change_connection)
    with pytest.raises(PermissionError):
        core._ask_model("Make it blue", set(), home,
                        interrupted_context="SYNTHETIC_PRIVATE_INTERRUPTED_REFERENCE")
    assert calls == [], "No payload may reach the earlier remote URL after local-only selection"


@pytest.mark.parametrize("change", [{"memory_allow_remote": False}, {"memory_enabled": False}])
def test_prepared_current_history_is_not_posted_after_memory_consent_revocation(isolated, monkeypatch, change):
    home, calls = isolated
    configure(home)
    retrieved = []

    def history_then_revoke(self, *_args, **_kwargs):
        retrieved.append(True)
        save_settings(change, home, human_confirmed=True)
        return [{"role": "user", "content": "SYNTHETIC_PREPARED_PRIVATE_HISTORY"}]

    monkeypatch.setattr(core.ConversationMemory, "context", history_then_revoke)
    with pytest.raises(PermissionError):
        core._ask_model("A current question", set(), home)
    assert retrieved == [True] and calls == []


def test_legacy_trace_cannot_use_new_local_endpoint_to_justify_old_remote_post(isolated, monkeypatch):
    home, calls = isolated
    configure(home, memory_enabled=True)

    def change_connection(*_):
        configure(home, remote=False, memory_allow_remote=False)
        return []

    monkeypatch.setattr(core.knowledge, "search", change_connection)
    trace = [{"call": {"tool": "get_habits", "arguments": {}},
              "result": {"private_preference": "SYNTHETIC_CACHED_LEGACY_REFERENCE"}}]
    with pytest.raises(PermissionError):
        core._ask_model("Recall the result", {"get_habits"}, home, tool_trace=trace)
    assert calls == []


@pytest.mark.parametrize("change", [
    {"ollama_url": "https://api.x.ai/v1/chat/completions"},
    {"ollama_url": LOCAL, "ai_provider": "ollama", "memory_allow_remote": True},
    {"ollama_model": "a-different-synthetic-model"},
    {"api_key_env": "REGENOS_SYNTHETIC_DIFFERENT_API_KEY_VARIABLE"},
])
def test_recipient_or_model_change_cancels_even_without_private_memory(isolated, monkeypatch, change):
    home, calls = isolated
    configure(home, memory_enabled=False)

    def change_recipient(*_):
        save_settings(change, home, human_confirmed=True)
        return []

    monkeypatch.setattr(core.knowledge, "search", change_recipient)
    with pytest.raises(PermissionError):
        core._ask_model("A plain current message without private references", set(), home)
    assert calls == []


def test_provider_change_alone_cancels_same_loopback_recipient(isolated, monkeypatch):
    home, calls = isolated
    configure(home, remote=False, ai_provider="openai_compatible", memory_enabled=False)

    def change_provider(*_):
        save_settings({"ai_provider": "ollama"}, home, human_confirmed=True)
        return []

    monkeypatch.setattr(core.knowledge, "search", change_provider)
    with pytest.raises(PermissionError):
        core._ask_model("A plain current message", set(), home)
    assert calls == []


def test_prepared_app_usage_is_not_posted_after_memory_revocation(isolated, monkeypatch):
    from ai_os.activity_memory import ActivityMemory
    home, calls = isolated
    configure(home, remote=False, activity_memory_enabled=True)
    retrieved = []

    def usage_then_revoke(_self):
        retrieved.append(True)
        save_settings({"memory_enabled": False}, home, human_confirmed=True)
        return [{"application": "synthetic-private-app", "estimated_minutes": 3}]

    monkeypatch.setattr(ActivityMemory, "summary", usage_then_revoke)
    with pytest.raises(PermissionError):
        core._ask_model("A current question", set(), home)
    assert retrieved == [True] and calls == []


def test_prepared_app_usage_is_not_posted_after_separate_activity_consent_revocation(isolated, monkeypatch):
    from ai_os.activity_memory import ActivityMemory
    home, calls = isolated
    configure(home, remote=False, activity_memory_enabled=True)
    retrieved = []

    def usage_then_revoke(_self):
        retrieved.append(True)
        save_settings({"activity_memory_enabled": False}, home, human_confirmed=True)
        return [{"application": "synthetic-private-app", "estimated_minutes": 3}]

    monkeypatch.setattr(ActivityMemory, "summary", usage_then_revoke)
    with pytest.raises(PermissionError, match="App-usage memory consent was revoked"):
        core._ask_model("A current question", set(), home)
    assert retrieved == [True] and calls == []


@pytest.mark.parametrize("source,consent_key", [
    ("ocr", "screen_context_enabled"),
    ("accessibility", "desktop_context_enabled"),
])
def test_prepared_observation_is_not_posted_after_its_specific_consent_revocation(isolated, monkeypatch, source, consent_key):
    home, calls = isolated
    configure(home, remote=False, memory_enabled=False, **{consent_key: True})

    def revoke_observation_consent(*_):
        save_settings({consent_key: False}, home, human_confirmed=True)
        return []

    monkeypatch.setattr(core.knowledge, "search", revoke_observation_consent)
    with pytest.raises(PermissionError, match="Screen or desktop-context consent was revoked"):
        core._ask_model("A current screen question", set(), home,
                        screen_observation={"source": source, "text": "SYNTHETIC_PRIVATE_OBSERVATION"})
    assert calls == []


@pytest.mark.parametrize("source,consent_key,other_key", [
    ("ocr", "screen_context_enabled", "desktop_context_enabled"),
    ("accessibility", "desktop_context_enabled", "screen_context_enabled"),
])
def test_observation_uses_only_its_own_still_enabled_consent(isolated, monkeypatch, source, consent_key, other_key):
    home, calls = isolated
    configure(home, remote=False, memory_enabled=False, **{consent_key: True, other_key: True})

    def revoke_other_observation_consent(*_):
        save_settings({other_key: False}, home, human_confirmed=True)
        return []

    monkeypatch.setattr(core.knowledge, "search", revoke_other_observation_consent)
    assert core._ask_model("A current screen question", set(), home,
                           screen_observation={"source": source, "text": "SYNTHETIC_APPROVED_OBSERVATION"})
    assert len(calls) == 1 and calls[0][0] == LOCAL


def test_unchanged_approved_context_still_reaches_exact_selected_recipient(isolated, monkeypatch):
    home, calls = isolated
    configure(home)
    monkeypatch.setattr(core.ConversationMemory, "context", lambda *_a, **_k: [
        {"role": "user", "content": "SYNTHETIC_APPROVED_HISTORY"},
    ])
    assert core._ask_model("Make it blue", set(), home,
                           interrupted_context="SYNTHETIC_APPROVED_INTERRUPTED_REFERENCE")
    assert len(calls) == 1 and calls[0][0] == REMOTE
    assert calls[0][1]["allow_redirects"] is False
    assert any("SYNTHETIC_APPROVED_HISTORY" in item["content"]
               for item in calls[0][1]["json"]["messages"])
