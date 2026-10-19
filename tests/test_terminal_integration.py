"""Native review and model proposal boundaries; never launch a real terminal."""
import json
import os
from pathlib import Path

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
pytest.importorskip("PySide6")
from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import QApplication, QMessageBox

from ai_os import ai_os_core as core, terminal_tasks
from ai_os.conversation_widget import ConversationWidget
from ai_os.hub_bridge import dispatch
from ai_os.settings_store import save_settings
from ai_os.tool_protocol import catalog, discover


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["terminal-review-test"])


class InertProcess:
    def __init__(self):
        self.requests = []
    def state(self):
        return QProcess.ProcessState.NotRunning
    def start(self, *args):
        pass
    def write(self, raw):
        self.requests.append(json.loads(raw))
    def closeWriteChannel(self):
        pass
    def processEnvironment(self):
        return QProcessEnvironment()


@pytest.fixture
def widget(app, tmp_path):
    window = ConversationWidget(tmp_path)
    window.process = InertProcess()
    yield window
    window.grant_timer.stop()
    window.timer.stop()
    window.close()


def proposal(home):
    return terminal_tasks.propose_terminal_command(["echo", "synthetic words with spaces"], str(home))["approval_required"]


def test_model_tool_is_proposal_only_with_no_launch_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_tasks, "launch_terminal_command", lambda *a, **k: pytest.fail("Model launched terminal"))
    registry = core.build_tool_registry(tmp_path)
    assert "launch_terminal_command" not in registry
    response = core.execute_tool("run_terminal_command", {
        "command": ["echo", "synthetic"], "cwd": str(tmp_path), "approve": True,
    }, registry, home=tmp_path, consent=lambda _: pytest.fail("Proposal asked for background consent"))
    assert response["ok"] is False
    assert response["approval_required"]["tool"] == "run_terminal_command"
    assert not (tmp_path / "run/private/terminal_tasks").exists()
    with pytest.raises(TypeError):
        core.execute_tool("run_terminal_command", {"command": ["echo"], "human_confirmed": True}, registry, home=tmp_path)


def test_tool_is_discoverable_and_command_schema_is_array(tmp_path):
    registry = core.build_tool_registry(tmp_path)
    assert "run_terminal_command" in str(discover(registry, "terminal"))
    tools = catalog(registry, {"run_terminal_command", "terminal_task_status"})
    assert len(tools) == 2
    function = next(t["function"] for t in tools if t["function"]["name"] == "run_terminal_command")
    assert function["parameters"]["properties"]["command"] == {"type": "array", "items": {"type": "string"}}
    assert "human_confirmed" not in function["parameters"]["properties"]


def test_terminal_bridge_requires_mode_and_literal_human_confirmation(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(terminal_tasks, "launch_terminal_command", lambda *a, **k: calls.append((a, k)) or {"ok": True})
    request = {"action": "approved_terminal_command", "arguments": proposal(tmp_path)["arguments"], "confirmed": True}
    with pytest.raises(PermissionError):
        dispatch(request, tmp_path)
    save_settings({"command_access": "supervised"}, tmp_path, human_confirmed=True)
    for value in (False, "true", 1, None):
        with pytest.raises(PermissionError):
            dispatch(request | {"confirmed": value}, tmp_path)
    assert not calls
    assert dispatch(request, tmp_path)["response"]["tool"] == "run_terminal_command"
    assert calls == [((request["arguments"],), {"home": tmp_path, "human_confirmed": True})]


def test_native_no_is_default_and_denial_never_launches(widget, monkeypatch):
    save_settings({"command_access": "supervised"}, widget.home, human_confirmed=True)
    def reject(box):
        assert box.defaultButton() == box.button(QMessageBox.StandardButton.No)
        assert str(Path("/usr/bin/echo").resolve()) in box.text()
        assert str(widget.home) in box.text()
        assert "900 seconds" in box.text()
        assert "sudo password" in box.text()
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(QMessageBox, "exec", reject)
    assert not widget.approve_terminal_command(proposal(widget.home))
    assert not widget.process.requests


def test_native_approval_sends_only_exact_reviewed_arguments(widget, monkeypatch):
    save_settings({"command_access": "supervised"}, widget.home, human_confirmed=True)
    monkeypatch.setattr(QMessageBox, "exec", lambda _: QMessageBox.StandardButton.Yes)
    request = proposal(widget.home)
    assert widget.approve_terminal_command(request)
    assert widget.process.requests == [{
        "action": "approved_terminal_command", "arguments": request["arguments"], "confirmed": True,
    }]
    assert widget.timer.isActive()


def test_native_review_cannot_be_used_in_restricted_mode_or_for_disk_command(widget, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda _: pytest.fail("Unsafe review shown"))
    assert not widget.approve_terminal_command(proposal(widget.home))
    save_settings({"command_access": "supervised"}, widget.home, human_confirmed=True)
    assert not widget.approve_terminal_command({"tool": "run_terminal_command", "arguments": {"command": ["sudo", "mount", "/tmp/a", "/tmp/b"]}})
    assert not widget.process.requests
