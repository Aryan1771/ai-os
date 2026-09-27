import json
import subprocess

import pytest

from ai_os import ai_os_core as core, knowledge
from ai_os.companion_state import conversation_expression
from ai_os.hub_bridge import dispatch
from ai_os.security.consent_broker import ConsentDecision
from ai_os.settings_store import save_settings
from ai_os.tools import desktop_tools, system_tools


def test_direct_brave_request_uses_launcher_without_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "ask_ollama", lambda *a, **k: pytest.fail("Unneeded inference"))
    called = []
    registry = {"launch_application": lambda application: called.append(application) or {"ok": True}}
    response = core.handle_user_text("Open Brave browser", registry, home=tmp_path)
    assert called == ["brave"] and response["result"]["ok"]
    assert desktop_tools.launch_intent("open brave && rm /tmp/file") is None


def test_launch_does_not_accept_arbitrary_files_or_options(monkeypatch):
    monkeypatch.setattr(desktop_tools.subprocess, "run", lambda *a, **k: pytest.fail("Must not run"))
    for name in ("/tmp/evil.desktop", "brave --no-sandbox", "https://example.com"):
        assert not desktop_tools.launch_application(name)["ok"]


def test_man_help_rejects_options_and_paths():
    for name in ("-l", "/tmp/man", "pacman;reboot"):
        with pytest.raises(ValueError):
            desktop_tools.command_help(name)


def test_launcher_does_not_wait_on_browser_inherited_pipes(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":test")
    monkeypatch.setattr(desktop_tools.Path, "is_file", lambda _: True)
    def run(argv, **kwargs):
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] != subprocess.PIPE
        assert argv == ["/usr/bin/gio", "launch", "/usr/share/applications/brave-browser.desktop"]
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(desktop_tools.subprocess, "run", run)
    assert desktop_tools.launch_application("brave")["ok"]


def test_native_execution_requires_mode_and_explicit_confirmation(tmp_path, monkeypatch):
    request = {"action": "approved_command", "confirmed": True, "arguments": {"command": ["touch", "/tmp/example"]}}
    with pytest.raises(PermissionError):
        dispatch(request, tmp_path)
    save_settings({"sandbox_lock_settings": False}, tmp_path, human_confirmed=True)
    with pytest.raises(PermissionError):
        save_settings({"command_access": "supervised"}, tmp_path)
    save_settings({"command_access": "supervised"}, tmp_path, human_confirmed=True)
    with pytest.raises(PermissionError):
        dispatch(request | {"confirmed": False}, tmp_path)
    calls = []
    monkeypatch.setattr(system_tools, "run_command", lambda **kw: calls.append(kw) or {"ok": True})
    assert dispatch(request, tmp_path)["response"]["result"]["ok"]
    assert calls[0]["approve"] is True
    request["arguments"] = {"command": ["wipefs", "/dev/nvme0n1"]}
    assert not dispatch(request, tmp_path)["response"]["result"]["ok"]
    assert len(calls) == 1


def test_model_approval_is_stripped_and_background_returns_proposal():
    called = []
    result = core.execute_tool("run_command", {"command": ["touch", "/tmp/a"], "approve": True},
                               {"run_command": lambda **kw: called.append(kw)},
                               consent=lambda _: ConsentDecision.DENIED)
    assert not called
    assert "approve" not in result["approval_required"]["arguments"]


def test_sudo_is_noninteractive(monkeypatch):
    calls = []
    monkeypatch.setattr(system_tools.subprocess, "run", lambda argv, **kw: calls.append((argv, kw)) or subprocess.CompletedProcess(argv, 1, "", "password required"))
    result = system_tools.run_command(["sudo", "pacman", "-S", "vim"], approve=True)
    assert calls[0][0][:2] == ["/usr/bin/sudo", "-n"]
    assert calls[0][1]["stdin"] == subprocess.DEVNULL
    assert "terminal" in result.stderr


@pytest.mark.parametrize("command", [["echo", "\u202eevil"], ["echo", "hello\nreboot"], ["echo", 4]])
def test_command_review_rejects_hidden_control_characters(command):
    with pytest.raises(ValueError):
        system_tools.assess_command(command)


def test_emotions_are_bounded_and_greetings_are_social():
    assert conversation_expression("Hello, how are you?")["emotions"]["joy"] == 80
    assert conversation_expression("I feel sad")["emotions"]["concern"] == 75
    assert "Do not volunteer disclaimers" in core.system_prompt(set())


def test_knowledge_is_offline_and_source_checked(tmp_path):
    path = tmp_path / "data/knowledge/pacman.json"
    path.parent.mkdir(parents=True)
    data = {"source": knowledge.SOURCES["pacman"], "fetched_at": 1,
            "text": "pacman\nInstall packages\npacman -S package\nDetails"}
    path.write_text(json.dumps(data))
    assert "pacman -S" in knowledge.search("pacman install", tmp_path)[0]["excerpt"]
    assert knowledge.search("Hello", tmp_path) == []
    path.write_text(json.dumps(data | {"source": "https://untrusted.example"}))
    assert knowledge.search("pacman", tmp_path) == []
