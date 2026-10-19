import json
from types import SimpleNamespace

import pytest

from ai_os import desktop_context
from ai_os.activity_memory import ActivityMemory
from ai_os.config import load_raw_config
from ai_os.runtime_services import voice_mode, device_notice
from ai_os.settings_store import save_settings


def test_context_defaults_off_and_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop_context.subprocess, "run", lambda *a, **kw: pytest.fail("Unexpected observation"))
    assert not desktop_context.read_desktop(tmp_path)["ok"]
    with pytest.raises(PermissionError):
        save_settings({"desktop_context_enabled": True}, tmp_path)


def test_accessibility_permission_revocation_discards_late_result(tmp_path, monkeypatch):
    save_settings({"desktop_context_enabled": True}, tmp_path, human_confirmed=True)

    def capture(command, **kwargs):
        assert command[:2] == ["/usr/bin/python", "-I"]
        assert kwargs["timeout"] == 4 and kwargs["shell"] is False
        save_settings({"desktop_context_enabled": False}, tmp_path, human_confirmed=True)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True, "text": "PRIVATE"}))

    monkeypatch.setattr(desktop_context.subprocess, "run", capture)
    result = desktop_context.read_desktop(tmp_path)
    assert not result["ok"] and "PRIVATE" not in json.dumps(result)


def test_app_usage_requires_opt_in_and_memory_and_can_be_cleared(tmp_path):
    memory = ActivityMemory(tmp_path)
    memory.record("Editor")
    assert not memory.path.exists()
    save_settings({"activity_memory_enabled": True}, tmp_path, human_confirmed=True)
    memory.record("Editor", 15)
    memory.record("Editor", 15)
    assert memory.summary() == [{"application": "Editor", "approximate_minutes": 0.5}]
    save_settings({"memory_enabled": False}, tmp_path, human_confirmed=True)
    memory.record("Browser", 15)
    assert len(memory.summary()) == 1
    memory.clear()
    assert memory.summary() == []


def test_voice_modes_are_explicit_and_device_notices_ignore_device_content(tmp_path):
    config = load_raw_config(tmp_path)
    assert voice_mode(config) == "off"
    config["always_listening_enabled"] = True
    assert voice_mode(config) == "needs_activation_choice"
    config["conversation_listening_enabled"] = True
    assert voice_mode(config) == "conversation"
    config["wake_word_enabled"] = True
    assert voice_mode(config) == "wake"
    assert device_notice("add", "usb", "usb_device") == "USB device connected."
    assert device_notice("add", "usb", "evil device label") is None


def test_accessibility_probe_skips_editable_and_password_subtrees(monkeypatch):
    import sys
    from ai_os import desktop_probe

    class Node:
        def __init__(self, name, children=(), role="label", editable=False):
            self.name, self.children, self.role, self.editable = name, children, role, editable

        def get_name(self):
            if self.editable or self.role == "password":
                pytest.fail("Private editable/password label accessed")
            return self.name

        def get_child_count(self):
            return len(self.children)

        def get_child_at_index(self, index):
            return self.children[index]

        def get_state_set(self):
            return SimpleNamespace(contains=lambda state: self.editable if state == 3 else True)

        def get_role(self):
            return self.role

        def get_interfaces(self):
            return ["org.a11y.atspi.EditableText"] if self.editable else []

        def get_text_iface(self):
            return None

    window = Node("Test window", [Node("Public label"), Node("SECRET", role="password"),
                                  Node("Draft text", editable=True)])
    desktop = Node("Desktop", [Node("Editor", [window])])
    atspi = SimpleNamespace(set_timeout=lambda *args: None, get_desktop=lambda _: desktop,
                            StateType=SimpleNamespace(ACTIVE=1, SHOWING=2, EDITABLE=3),
                            Role=SimpleNamespace(PASSWORD_TEXT="password"))
    monkeypatch.setitem(sys.modules, "gi", SimpleNamespace(require_version=lambda *a: None))
    monkeypatch.setitem(sys.modules, "gi.repository", SimpleNamespace(Atspi=atspi, Gio=object()))
    monkeypatch.setattr(desktop_probe, "unlocked", lambda _: True)
    result = desktop_probe.snapshot()
    assert result["ok"] and "Public label" in result["text"]
    assert "SECRET" not in result["text"] and "Draft" not in result["text"]


def test_voice_supervisor_requires_opt_in_and_reaps_owned_audio_on_disable(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from ai_os import runtime_services
    supervisor = runtime_services.VoiceSupervisor(tmp_path)
    process = Mock(pid=9999999)
    process.poll.return_value = None
    calls = []
    monkeypatch.setattr(runtime_services.subprocess, "Popen", lambda *a, **kw: calls.append(kw) or process)
    monkeypatch.setattr(runtime_services.os, "killpg", lambda *a: None)
    supervisor.tick()
    assert not calls
    save_settings({"always_listening_enabled": True}, tmp_path, human_confirmed=True)
    supervisor.tick()
    assert not calls
    save_settings({"conversation_listening_enabled": True}, tmp_path, human_confirmed=True)
    supervisor.tick()
    assert calls[0]["start_new_session"] is True
    from pathlib import Path
    temporary = Path(calls[0]["env"]["AI_OS_VOICE_TMP"])
    (temporary / "synthetic.wav").touch()
    save_settings({"always_listening_enabled": False}, tmp_path, human_confirmed=True)
    supervisor.tick()
    assert supervisor.process is None and not temporary.exists()


def test_one_shot_capture_cannot_be_started_by_unconfirmed_bridge_request(tmp_path, monkeypatch):
    from ai_os.services import voice_input
    from ai_os.hub_bridge import dispatch
    monkeypatch.setattr(voice_input, "capture_once", lambda _: pytest.fail("Microphone opened"))
    with pytest.raises(PermissionError):
        dispatch({"action": "voice_once"}, tmp_path)
