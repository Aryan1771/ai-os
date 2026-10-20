"""All power commands are mocked: never schedule/cancel/shut down the host."""

from types import SimpleNamespace
import pytest
from ai_os import power_actions as power
from ai_os import ai_os_core as core
from ai_os.config import load_raw_config


@pytest.mark.parametrize(
    "action,delay", [("poweroff", None), ("poweroff", 0), ("reboot", 5), ("cancel", None)]
)
def test_proposal_never_executes_and_has_exact_native_scope(monkeypatch, action, delay):
    monkeypatch.setattr(power.subprocess, "run", lambda *_a, **_k: pytest.fail("Proposal executed"))
    result = power.power_action(action, delay)
    assert result["ok"] is False
    assert result["approval_required"]["tool"] == "power_action"


@pytest.mark.parametrize(
    "action,delay",
    [
        ("poweroff", True),
        ("reboot", -1),
        ("reboot", 1441),
        ("reboot", 2.5),
        ("cancel", 5),
        ({}, 0),
        ("halt", 0),
    ],
)
def test_invalid_arguments_rejected(action, delay):
    with pytest.raises(ValueError):
        power.power_action(action, delay)


@pytest.mark.parametrize("approval", [False, None, 1, "yes"])
def test_executor_requires_exact_trusted_confirmation(monkeypatch, approval):
    monkeypatch.setattr(
        power.subprocess, "run", lambda *_a, **_k: pytest.fail("Unapproved execution")
    )
    with pytest.raises(PermissionError):
        power.execute_power("poweroff", 5, human_confirmed=approval)


@pytest.mark.parametrize(
    "action,delay,expected",
    [
        ("poweroff", 5, ["/usr/bin/shutdown", "--no-wall", "--poweroff", "+5"]),
        ("reboot", 0, ["/usr/bin/shutdown", "--no-wall", "--reboot", "+0"]),
        ("cancel", None, ["/usr/bin/shutdown", "--no-wall", "-c"]),
    ],
)
def test_reviewed_executor_uses_fixed_argv_and_reports_acceptance_only(
    monkeypatch, action, delay, expected
):
    calls = []
    monkeypatch.setattr(
        power.subprocess,
        "run",
        lambda argv, **kw: calls.append((argv, kw)) or SimpleNamespace(returncode=0),
    )
    result = power.execute_power(action, delay, human_confirmed=True)
    assert calls[0][0] == expected and calls[0][1]["shell"] is False
    assert calls[0][1]["timeout"] == 10
    assert result["ok"] and result["request_accepted"] and not result["completion_verified"]


def test_denied_os_request_is_not_success_or_raw_error(monkeypatch):
    monkeypatch.setattr(power.subprocess, "run", lambda *_a, **_k: SimpleNamespace(returncode=1))
    result = power.execute_power("poweroff", 5, human_confirmed=True)
    assert not result["ok"] and result["code"] == "power_request_denied"


@pytest.mark.parametrize(
    "argv,action,delay",
    [
        (["shutdown"], "poweroff", None),
        (["shutdown", "-h", "+5"], "poweroff", 5),
        (["/usr/bin/shutdown", "-r", "now"], "reboot", 0),
        (["systemctl", "poweroff"], "poweroff", 0),
        (["shutdown", "-c"], "cancel", None),
        (["reboot"], "reboot", 0),
    ],
)
def test_common_commands_route_to_native_review(argv, action, delay):
    args = power.command_proposal(argv)["approval_required"]["arguments"]
    assert args == {"action": action, "delay_minutes": delay}


@pytest.mark.parametrize(
    "argv",
    [
        ["shutdown", "--force"],
        ["systemctl", "--force", "poweroff"],
        ["poweroff", "--force"],
        ["sudo", "shutdown", "now"],
        ["sudo", "-n", "systemctl", "poweroff"],
        ["shutdown", "-r", "-P", "+5"],
        ["shutdown", "+5", "+0"],
        ["shutdown", "-h", "12:00"],
    ],
)
def test_force_privilege_and_ambiguous_time_not_silently_reinterpreted(argv):
    with pytest.raises(ValueError):
        power.command_proposal(argv)


def test_command_grants_do_not_silently_execute_power(tmp_path, monkeypatch):
    load_raw_config(tmp_path)
    monkeypatch.setattr(
        core.GrantStore, "consume", lambda *_a, **_k: pytest.fail("Power consumed a broad grant")
    )
    result = core.execute_tool(
        "run_command",
        {"command": ["shutdown", "-h", "+5"], "approve": True},
        {"run_command": lambda **_: pytest.fail("Generic power execution")},
        home=tmp_path,
    )
    assert result["approval_required"]["tool"] == "power_action"
    from ai_os.pending_review import read

    assert read(tmp_path, "default")["tool"] == "power_action"


def test_native_time_picker_and_confirmation_bind_exact_action(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from ai_os.conversation_widget import ConversationWidget
    from ai_os import conversation_widget as ui

    app = QApplication.instance() or QApplication([])
    widget = ConversationWidget(tmp_path)
    submitted = []
    monkeypatch.setattr(ui.QInputDialog, "getInt", lambda *_a, **_k: (7, True))
    monkeypatch.setattr(QMessageBox, "exec", lambda box: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(
        widget, "_start_reviewed_request", lambda request, *_: submitted.append(request)
    )
    assert widget.approve_power(power.power_action("poweroff")["approval_required"])
    assert submitted == [
        {
            "action": "approved_power",
            "power_action": "poweroff",
            "delay_minutes": 7,
            "confirmed": True,
        }
    ]
    widget.close()
    app.processEvents()


def test_native_default_no_and_cancelled_time_start_nothing(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from ai_os.conversation_widget import ConversationWidget
    from ai_os import conversation_widget as ui

    app = QApplication.instance() or QApplication([])
    widget = ConversationWidget(tmp_path)
    monkeypatch.setattr(
        widget, "_start_reviewed_request", lambda *_a, **_k: pytest.fail("Denied power started")
    )
    monkeypatch.setattr(ui.QInputDialog, "getInt", lambda *_a, **_k: (0, False))
    assert not widget.approve_power(power.power_action("poweroff")["approval_required"])

    def deny(box):
        assert box.defaultButton() == box.button(QMessageBox.StandardButton.No)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "exec", deny)
    assert not widget.approve_power(power.power_action("poweroff", 0)["approval_required"])
    widget.close()
    app.processEvents()
