import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from ai_os import terminal_task_runner as runner
from ai_os import terminal_tasks as tasks

_REAL_POPEN = subprocess.Popen


def _proposal(tmp_path, command=None):
    return tasks.propose_terminal_command(command or ["echo", "hello"], cwd=str(tmp_path))


def _fake_terminal(monkeypatch):
    calls = []
    monkeypatch.setattr(tasks, "_find_terminal", lambda: ["/usr/bin/xterm", "-e"])
    monkeypatch.setattr(tasks.subprocess, "Popen", lambda argv, **kwargs: calls.append((argv, kwargs)))
    return calls


def test_proposal_contains_exact_resolved_arguments_without_running(monkeypatch, tmp_path):
    monkeypatch.setattr(tasks.subprocess, "Popen", lambda *a, **k: pytest.fail("proposal executed"))
    proposal = _proposal(tmp_path, ["echo", "an argument with spaces"])
    assert proposal["ok"] is False
    assert proposal["approval_required"] == {
        "tool": "run_terminal_command", "arguments": {
            "command": [str(Path("/usr/bin/echo").resolve()), "an argument with spaces"],
            "cwd": str(tmp_path), "timeout_sec": 900,
        },
    }


@pytest.mark.parametrize("command", [
    ["dd", "if=/dev/zero", "of=/dev/nvme0n1"], ["mount", "/tmp/a", "/tmp/b"],
    ["sudo", "mount", "/tmp/a", "/tmp/b"], ["sudo", "sudo", "echo", "hello"],
    ["mkfs.ext4", "/tmp/image"], ["wipefs", "/tmp/image"], ["bootctl", "install"],
    ["sudo", "-S", "echo", "hello"], ["bash", "-c", "echo hello"],
    ["python3", "-c", "print('hello')"], ["env", "echo", "hello"],
    ["find", "/tmp", "-exec", "echo", "{}", ";"],
    ["echo", "/dev/nvme0n1"], ["rm", "-rf", "/"],
])
def test_review_does_not_override_disk_or_indirect_execution_boundary(command, tmp_path):
    with pytest.raises(ValueError):
        _proposal(tmp_path, command)


def test_interactive_sudo_keeps_password_in_terminal_and_has_root_deadline(tmp_path):
    proposal = _proposal(tmp_path, ["sudo", "echo", "hello"])
    spec = proposal["approval_required"]["arguments"]
    assert spec["command"] == ["/usr/bin/sudo", str(Path("/usr/bin/echo").resolve()), "hello"]
    assert runner._bounded_argv(spec) == [
        "/usr/bin/sudo", "/usr/bin/timeout", "--foreground", "--signal=TERM",
        "--kill-after=2s", "900s", *spec["command"][1:],
    ]


@pytest.mark.parametrize("duration", [0, 901, -1, True, "15", float("inf")])
def test_duration_bound_is_not_silently_expanded(tmp_path, duration):
    with pytest.raises(ValueError):
        tasks.propose_terminal_command(["echo"], str(tmp_path), duration)


def test_script_executable_not_treated_as_installed_binary(tmp_path):
    script = tmp_path / "innocent-name"
    script.write_text("#!/bin/sh\necho nope\n")
    script.chmod(0o700)
    with pytest.raises(ValueError, match="Script"):
        _proposal(tmp_path, [str(script)])


def test_executable_alias_cannot_hide_a_shell(tmp_path):
    alias = tmp_path / "ordinary-tool"
    alias.symlink_to("/usr/bin/bash")
    with pytest.raises(ValueError, match="aliases"):
        _proposal(tmp_path, [str(alias), "-c", "echo nope"])


def test_model_cannot_confirm_or_launch(monkeypatch, tmp_path):
    monkeypatch.setattr(tasks, "_find_terminal", lambda: pytest.fail("searched for terminal"))
    for value in (False, "true", 1, None):
        result = tasks.launch_terminal_command({}, home=tmp_path, human_confirmed=value)
        assert result["ok"] is False
    assert not (tmp_path / "run").exists()


def test_terminal_launch_keeps_argv_out_of_status_and_output_logs(monkeypatch, tmp_path):
    calls = _fake_terminal(monkeypatch)
    arguments = _proposal(tmp_path, ["echo", "private-request"])["approval_required"]["arguments"]
    result = tasks.launch_terminal_command(arguments, home=tmp_path, human_confirmed=True)
    assert result["status"] == "queued" and "not confirmed" in result["message"]
    directory = tmp_path / "run/private/terminal_tasks"
    assert directory.stat().st_mode & 0o777 == 0o700
    job = directory / (result["job_id"] + ".json")
    assert job.stat().st_mode & 0o777 == 0o600
    assert json.loads(job.read_text())["command"] == arguments["command"]
    assert "private-request" not in json.dumps(tasks.terminal_task_status(result["job_id"], home=tmp_path))
    argv, kwargs = calls[0]
    assert argv[-3:] == [str(tmp_path), "--job", result["job_id"]]
    assert kwargs == {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                      "stderr": subprocess.DEVNULL, "shell": False, "start_new_session": True}


def test_terminal_launch_failure_removes_private_spec(monkeypatch, tmp_path):
    _fake_terminal(monkeypatch)
    def unavailable(*args, **kwargs):
        raise OSError("private details should not appear")
    monkeypatch.setattr(tasks.subprocess, "Popen", unavailable)
    arguments = _proposal(tmp_path)["approval_required"]["arguments"]
    result = tasks.launch_terminal_command(arguments, home=tmp_path, human_confirmed=True)
    assert result["ok"] is False
    assert "private details" not in json.dumps(result)
    assert not (tmp_path / "run/private/terminal_tasks" / (result["job_id"] + ".json")).exists()
    assert tasks.terminal_task_status(result["job_id"], home=tmp_path)["status"] == "launch_failed"


def test_symlink_storage_or_status_is_rejected(tmp_path):
    directory = tasks._task_directory(tmp_path, create=True)
    job_id = "a" * 32
    target = tmp_path / "private"
    target.write_text("{}")
    (directory / (job_id + ".status.json")).symlink_to(target)
    with pytest.raises(OSError):
        tasks.terminal_task_status(job_id, home=tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    (tmp_path / "run/private/terminal_tasks").rename(tmp_path / "saved")
    (tmp_path / "run/private/terminal_tasks").symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError):
        tasks._task_directory(tmp_path, create=False)


def test_job_id_cannot_escape_private_directory(tmp_path):
    tasks._task_directory(tmp_path, create=True)
    with pytest.raises(ValueError):
        tasks.terminal_task_status("../../private", home=tmp_path)


def test_metadata_fifo_cannot_block_status_reader(tmp_path):
    directory = tasks._task_directory(tmp_path, create=True)
    job_id = "b" * 32
    os.mkfifo(directory / (job_id + ".status.json"), 0o600)
    with pytest.raises(ValueError, match="Unsafe"):
        tasks.terminal_task_status(job_id, home=tmp_path)


def test_visible_runner_claim_is_single_use_and_deletes_exact_command(monkeypatch, tmp_path):
    _fake_terminal(monkeypatch)
    arguments = _proposal(tmp_path)["approval_required"]["arguments"]
    launched = tasks.launch_terminal_command(arguments, home=tmp_path, human_confirmed=True)
    monkeypatch.setattr(runner.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    calls = []
    def execute(spec):
        calls.append(spec)
        return {"status": "completed", "returncode": 0, "duration_sec": 0.1, "updated_at": 1.0}
    monkeypatch.setattr(runner, "_execute", execute)
    assert runner.run_job(tmp_path, launched["job_id"]) == 0
    assert runner.run_job(tmp_path, launched["job_id"]) == 2
    assert calls == [arguments]
    directory = tasks._task_directory(tmp_path, create=False)
    assert not (directory / (launched["job_id"] + ".json")).exists()
    assert tasks.terminal_task_status(launched["job_id"], home=tmp_path)["returncode"] == 0


def test_runner_without_terminal_fails_closed(monkeypatch, tmp_path):
    _fake_terminal(monkeypatch)
    arguments = _proposal(tmp_path)["approval_required"]["arguments"]
    launched = tasks.launch_terminal_command(arguments, home=tmp_path, human_confirmed=True)
    monkeypatch.setattr(runner.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(runner, "_execute", lambda spec: pytest.fail("nonterminal execution"))
    assert runner.run_job(tmp_path, launched["job_id"]) == 1
    assert tasks.terminal_task_status(launched["job_id"], home=tmp_path)["status"] == "failed"


def test_worker_timeout_kills_process_group_without_capturing_input(monkeypatch):
    calls = []
    class Process:
        pid = 12345
        returncode = None
        def wait(self, timeout):
            calls.append(("wait", timeout))
            if timeout == 7:
                raise subprocess.TimeoutExpired(["echo"], timeout)
            self.returncode = -9
            return -9
        def poll(self):
            return self.returncode
    def popen(argv, **kwargs):
        assert kwargs == {"cwd": "/tmp", "shell": False, "process_group": 0}
        return Process()
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    monkeypatch.setattr(runner.sys, "stdin", SimpleNamespace(fileno=lambda: 0))
    monkeypatch.setattr(runner.os, "tcgetpgrp", lambda fd: 999)
    monkeypatch.setattr(runner.os, "tcsetpgrp", lambda fd, group: calls.append(("foreground", group)))
    monkeypatch.setattr(runner.os, "killpg", lambda pid, sig: calls.append(("signal", pid, sig)))
    monkeypatch.setattr(runner.signal, "signal", lambda *args: None)
    result = runner._execute({"command": ["/usr/bin/echo"], "cwd": "/tmp", "timeout_sec": 7})
    assert result["status"] == "timed_out" and result["returncode"] is None
    assert ("signal", 12345, runner.signal.SIGKILL) in calls
    assert calls[-1] == ("foreground", 999)


def test_privileged_group_cleanup_denial_does_not_claim_containment(monkeypatch):
    class Process:
        pid = 12345
        def wait(self, timeout):
            raise subprocess.TimeoutExpired(["synthetic-command"], timeout)
    def denied(pid, sig):
        raise PermissionError("synthetic root-owned descendant")
    monkeypatch.setattr(runner.os, "killpg", denied)
    assert runner._stop_process_group(Process()) is False


def test_exit_zero_with_unconfirmed_cleanup_is_not_reported_completed(monkeypatch):
    process = SimpleNamespace(pid=12345, wait=lambda timeout: 0, poll=lambda: 0)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(runner.sys, "stdin", SimpleNamespace(fileno=lambda: 0))
    monkeypatch.setattr(runner.os, "tcgetpgrp", lambda fd: 999)
    monkeypatch.setattr(runner.os, "tcsetpgrp", lambda fd, group: None)
    monkeypatch.setattr(runner.os, "killpg", lambda pid, sig: None)
    monkeypatch.setattr(runner.signal, "signal", lambda *args: None)
    monkeypatch.setattr(runner, "_stop_process_group", lambda process: False)
    result = runner._execute({"command": ["/usr/bin/echo"], "cwd": "/tmp", "timeout_sec": 7})
    assert result["returncode"] == 0 and result["status"] == "cleanup_unconfirmed"


def test_registry_only_proposes_and_hides_native_launcher(monkeypatch, tmp_path):
    from ai_os.ai_os_core import build_tool_registry, execute_tool
    from ai_os.tool_protocol import catalog
    monkeypatch.setattr(tasks.subprocess, "Popen", lambda *a, **k: pytest.fail("model launched terminal"))
    registry = build_tool_registry(tmp_path)
    result = execute_tool("run_terminal_command", {"command": ["echo", "hello"], "cwd": str(tmp_path)}, registry, home=tmp_path)
    assert result["approval_required"]["tool"] == "run_terminal_command"
    assert "launch_terminal_command" not in registry and "approved_terminal_command" not in registry
    schema = catalog(registry, {"run_terminal_command"})[0]["function"]["parameters"]
    assert set(schema["properties"]) == {"command", "cwd", "timeout_sec"}
    assert schema["properties"]["command"] == {"type": "array", "items": {"type": "string"}}
    assert schema["additionalProperties"] is False


def test_native_bridge_requires_supervised_mode_and_exact_confirmation(monkeypatch, tmp_path):
    from ai_os import hub_bridge
    calls = []
    monkeypatch.setattr(tasks, "launch_terminal_command", lambda arguments, **kwargs: calls.append((arguments, kwargs)) or {"ok": True, "status": "queued"})
    request = {"action": "approved_terminal_command", "arguments": {"command": ["echo", "hello"]}}
    monkeypatch.setattr(hub_bridge, "load_raw_config", lambda home: {"command_access": "supervised"})
    for confirmation in (None, False, "true", 1):
        with pytest.raises(PermissionError):
            hub_bridge.dispatch(request | {"confirmed": confirmation}, tmp_path)
    monkeypatch.setattr(hub_bridge, "load_raw_config", lambda home: {"command_access": "restricted"})
    with pytest.raises(PermissionError):
        hub_bridge.dispatch(request | {"confirmed": True}, tmp_path)
    assert calls == []
    monkeypatch.setattr(hub_bridge, "load_raw_config", lambda home: {"command_access": "supervised"})
    result = hub_bridge.dispatch(request | {"confirmed": True}, tmp_path)
    assert calls == [(request["arguments"], {"home": tmp_path, "human_confirmed": True})]
    assert result["response"]["result"]["status"] == "queued"


def _run_private_pty(home, job_id):
    """Real temporary pseudo-terminal, never a visible GUI or sudo command."""
    import pty
    descriptor, slave = pty.openpty()
    # Establish the controlling terminal only after exec in a fresh Python
    # process; forkpty directly in the Qt-threaded test runner is unsafe.
    bootstrap = ("import fcntl,os,sys,termios; "
                 "fcntl.ioctl(0,termios.TIOCSCTTY,0); "
                 "os.execv(sys.executable,[sys.executable,'-m','ai_os.terminal_task_runner',"
                 "'--home',sys.argv[1],'--job',sys.argv[2]])")
    process = _REAL_POPEN([sys.executable, "-c", bootstrap, str(home), job_id],
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    collected = bytearray()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([descriptor], [], [], 0.1)[0]:
                try:
                    collected.extend(os.read(descriptor, 4096))
                except OSError:
                    pass
                assert len(collected) < 65536
            returned = process.poll()
            if returned is not None:
                return returned, collected.decode(errors="replace")
        pytest.fail("Private terminal worker exceeded its smoke-check deadline")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=3)
        os.close(descriptor)


def test_real_private_pty_runs_harmless_echo_without_output_in_status(monkeypatch, tmp_path):
    _fake_terminal(monkeypatch)
    spec = _proposal(tmp_path, ["echo", "synthetic-only"])["approval_required"]["arguments"]
    launched = tasks.launch_terminal_command(spec, home=tmp_path, human_confirmed=True)
    returncode, output = _run_private_pty(tmp_path, launched["job_id"])
    assert returncode == 0 and "synthetic-only" in output
    status = tasks.terminal_task_status(launched["job_id"], home=tmp_path)
    assert status["status"] == "completed" and status["returncode"] == 0
    assert "synthetic-only" not in json.dumps(status)


def test_real_private_pty_stops_harmless_sleep_at_deadline(monkeypatch, tmp_path):
    _fake_terminal(monkeypatch)
    spec = tasks.propose_terminal_command(["sleep", "30"], str(tmp_path), 1)["approval_required"]["arguments"]
    launched = tasks.launch_terminal_command(spec, home=tmp_path, human_confirmed=True)
    returncode, output = _run_private_pty(tmp_path, launched["job_id"])
    assert returncode == 1
    status = tasks.terminal_task_status(launched["job_id"], home=tmp_path)
    assert status["status"] == "timed_out"
    assert status["duration_sec"] < 4
