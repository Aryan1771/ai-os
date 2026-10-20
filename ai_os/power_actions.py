"""Exact native-reviewed shutdown scheduling. Models can propose, never execute."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess

ACTIONS = {"poweroff", "reboot", "cancel"}
MAX_DELAY_MINUTES = 1440


def power_action(action: str, delay_minutes: int | None = None) -> dict:
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError("Choose poweroff, reboot or cancel")
    if delay_minutes is not None and (
        type(delay_minutes) is not int or not 0 <= delay_minutes <= MAX_DELAY_MINUTES
    ):
        raise ValueError("Delay must be an integer from 0 to 1440 minutes, or omitted to ask")
    if action == "cancel" and delay_minutes not in (None, 0):
        raise ValueError("Cancellation does not accept a delay")
    arguments = {"action": action, "delay_minutes": None if action == "cancel" else delay_minutes}
    return {
        "ok": False,
        "message": "Choose/review the time and confirm this power action in the native dialog. Nothing has been scheduled.",
        "approval_required": {"tool": "power_action", "arguments": arguments},
    }


def command_arguments(action, delay_minutes):
    spec = power_action(action, delay_minutes)["approval_required"]["arguments"]
    if action == "cancel":
        return ["/usr/bin/shutdown", "--no-wall", "-c"]
    if spec["delay_minutes"] is None:
        raise ValueError("Choose the shutdown delay in the native dialog first")
    return [
        "/usr/bin/shutdown",
        "--no-wall",
        "--poweroff" if action == "poweroff" else "--reboot",
        "+" + str(delay_minutes),
    ]


def command_proposal(argv):
    """Route common power argv to the same time/confirmation path, including grants."""
    if not isinstance(argv, list) or not argv:
        return None
    name, args = Path(argv[0]).name, argv[1:]
    if name in {"sudo", "pkexec", "doas"}:
        target = args[1:] if args and args[0] == "-n" else args
        if target and (
            Path(target[0]).name in {"shutdown", "poweroff", "reboot"}
            or Path(target[0]).name == "systemctl"
            and any(a in {"poweroff", "reboot"} for a in target[1:])
        ):
            raise ValueError(
                "Use the native power action; no privilege wrapper or force option is accepted"
            )
        return None
    if name == "systemctl":
        if args in (["poweroff"], ["reboot"]):
            return power_action(args[0], 0)
        if any(arg in {"poweroff", "reboot"} for arg in args):
            raise ValueError(
                "Power force/boot flags are unavailable; use the reviewed native power action"
            )
        return None
    if name in {"poweroff", "reboot"}:
        if args:
            raise ValueError("Power flags are unavailable; use the reviewed native power action")
        return power_action(name, 0)
    if name != "shutdown":
        return None
    if args in (["-c"], ["--no-wall", "-c"]):
        return power_action("cancel")
    action, delay, selected_action = "poweroff", None, None
    for arg in args:
        if arg == "--no-wall":
            continue
        if arg in {"--poweroff", "-P", "-h", "-r", "--reboot"}:
            choice = "reboot" if arg in {"-r", "--reboot"} else "poweroff"
            if selected_action is not None and selected_action != choice:
                raise ValueError("Choose one power action; conflicting flags are unavailable")
            selected_action = action = choice
        elif arg == "now" or re.fullmatch(r"\+\d{1,4}", arg):
            if delay is not None:
                raise ValueError("Choose one delay; multiple times are ambiguous")
            delay = 0 if arg == "now" else int(arg[1:])
        else:
            raise ValueError(
                "Use a relative minute delay in the native power dialog; force and wall-message arguments are unavailable"
            )
    return power_action(action, delay)


def execute_power(action, delay_minutes, *, human_confirmed=False):
    """Native bridge only, never register this executor as a model tool."""
    if human_confirmed is not True:
        raise PermissionError("Exact native human confirmation is required for every power action")
    argv = command_arguments(action, delay_minutes)
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "ok": False,
            "code": "power_request_unavailable",
            "message": "The power request failed or timed out. Check the desktop power menu and scheduled-shutdown status before retrying.",
        }
    if result.returncode:
        return {
            "ok": False,
            "code": "power_request_denied",
            "message": "The system denied the power request or an inhibitor/authentication blocked it. No success is confirmed. Use the desktop power menu if authentication is needed.",
        }
    message = (
        "Scheduled shutdown cancellation was accepted by the system."
        if action == "cancel"
        else f"The system accepted {'power off' if action == 'poweroff' else 'restart'} in {delay_minutes} minute(s). Save your work; chat Stop does not cancel it. Use Cancel scheduled shutdown or shutdown -c to cancel a future schedule."
    )
    return {
        "ok": True,
        "action": action,
        "delay_minutes": delay_minutes,
        "request_accepted": True,
        "completion_verified": False,
        "message": message,
    }
