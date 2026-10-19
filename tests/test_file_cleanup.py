"""Recoverable cleanup boundaries; gio is mocked so nothing leaves test data."""
import json
from pathlib import Path
import subprocess

import pytest

from ai_os import file_cleanup as cleanup
from ai_os.hub_bridge import dispatch


@pytest.fixture
def data(tmp_path, monkeypatch):
    user = tmp_path / "user"
    user.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: user))
    directory = user / "Downloads" / "scratch"
    directory.mkdir(parents=True)
    runtime = user / ".ai_os"
    (directory / "one.py").write_text("synthetic")
    (directory / "keep.txt").write_text("keep")
    return directory, runtime, user


def _proposal(data):
    directory, runtime, _ = data
    return cleanup.propose_cleanup(str(directory), "*.py", home=runtime)


def _fake_trash(monkeypatch):
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        for filename in argv[3:]:
            Path(filename).rename(Path(filename).with_suffix(".trashed"))
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(cleanup.subprocess, "run", run)
    return calls


def test_first_request_previews_no_execution_and_requires_literal_confirmation(data, monkeypatch):
    monkeypatch.setattr(cleanup.subprocess, "run", lambda *a, **k: pytest.fail("Unapproved trash"))
    result = _proposal(data)
    proposal = result["approval_required"]
    assert not result["ok"] and proposal["tool"] == "cleanup_files"
    assert [item["name"] for item in proposal["preview"]["files"]] == ["one.py"]
    for value in (False, 1, "true", None):
        with pytest.raises(PermissionError):
            cleanup.execute_cleanup(proposal["arguments"]["token"], home=data[1], human_confirmed=value)
    assert (data[0] / "one.py").exists()


def test_approval_uses_trash_exact_argv_no_shell_and_preview_single_use(data, monkeypatch):
    calls = _fake_trash(monkeypatch)
    token = _proposal(data)["approval_required"]["arguments"]["token"]
    result = cleanup.execute_cleanup(token, home=data[1], human_confirmed=True)
    assert result["ok"] and result["count"] == 1
    assert calls[0][0] == ["/usr/bin/gio", "trash", "--", str(data[0] / "one.py")]
    assert calls[0][1]["shell"] is False and calls[0][1]["timeout"] == 30
    assert (data[0] / "keep.txt").exists()
    with pytest.raises(FileNotFoundError):
        cleanup.execute_cleanup(token, home=data[1], human_confirmed=True)


def test_remember_requires_explicit_opt_in_and_same_directory_pattern_identity(data, monkeypatch):
    calls = _fake_trash(monkeypatch)
    token = _proposal(data)["approval_required"]["arguments"]["token"]
    cleanup.execute_cleanup(token, home=data[1], human_confirmed=True, remember=True)
    assert cleanup.list_rules(data[1])[0]["uses"] == 20
    (data[0] / "two.py").write_text("new synthetic")
    result = _proposal(data)
    assert result["ok"] and result["remembered_rule"]
    assert cleanup.list_rules(data[1])[0]["uses"] == 19 and len(calls) == 2
    (data[0] / "other.tmp").touch()
    assert "approval_required" in cleanup.propose_cleanup(str(data[0]), "*.tmp", home=data[1])
    data[0].rename(data[0].with_name("old"))
    data[0].mkdir()
    (data[0] / "new.py").touch()
    assert "approval_required" in _proposal(data)


def test_no_remembered_rule_without_checkbox_and_forget_needs_confirmation(data, monkeypatch):
    _fake_trash(monkeypatch)
    token = _proposal(data)["approval_required"]["arguments"]["token"]
    cleanup.execute_cleanup(token, home=data[1], human_confirmed=True)
    assert not cleanup.list_rules(data[1])
    (data[0] / "one.py").touch()
    token = _proposal(data)["approval_required"]["arguments"]["token"]
    cleanup.execute_cleanup(token, home=data[1], human_confirmed=True, remember=True)
    with pytest.raises(PermissionError):
        cleanup.forget_rules(data[1])
    cleanup.forget_rules(data[1], human_confirmed=True)
    assert not cleanup.list_rules(data[1])


def test_changed_or_expired_preview_does_not_execute(data, monkeypatch):
    monkeypatch.setattr(cleanup.subprocess, "run", lambda *a, **k: pytest.fail("Stale preview executed"))
    token = _proposal(data)["approval_required"]["arguments"]["token"]
    (data[0] / "one.py").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        cleanup.execute_cleanup(token, home=data[1], human_confirmed=True)
    token = _proposal(data)["approval_required"]["arguments"]["token"]
    monkeypatch.setattr(cleanup.time, "time", lambda: 1e20)
    with pytest.raises(ValueError, match="expired"):
        cleanup.execute_cleanup(token, home=data[1], human_confirmed=True)


@pytest.mark.parametrize("pattern", ["*", "**/*.py", "../*.py", ".*", "-rf", "x\ny", "*.py;rm"])
def test_broad_or_command_patterns_rejected(data, pattern):
    with pytest.raises(ValueError):
        cleanup.propose_cleanup(str(data[0]), pattern, home=data[1])


def test_system_home_hidden_repo_environment_and_symlink_are_protected(data):
    for directory in (Path("/usr"), data[2], data[1]):
        with pytest.raises((ValueError, FileNotFoundError)):
            cleanup.propose_cleanup(str(directory), "*.py", home=data[1])
    (data[0] / ".git").mkdir()
    with pytest.raises(ValueError, match="repositories"):
        _proposal(data)
    (data[0] / ".git").rmdir()
    (data[0] / "pyvenv.cfg").touch()
    with pytest.raises(ValueError, match="environments"):
        _proposal(data)
    (data[0] / "pyvenv.cfg").unlink()
    (data[0] / "linked.py").symlink_to(data[0] / "one.py")
    with pytest.raises(ValueError, match="symlinks"):
        _proposal(data)


def test_count_cap_and_nonrecursive_matching(data):
    child = data[0] / "subdir"
    child.mkdir()
    (child / "hidden.py").touch()
    assert len(_proposal(data)["approval_required"]["preview"]["files"]) == 1
    for index in range(200):
        (data[0] / f"f{index}.py").touch()
    with pytest.raises(ValueError, match="exceeds"):
        _proposal(data)


def test_rule_expiry_limits_and_token_traversal_fail_closed(data, monkeypatch):
    _fake_trash(monkeypatch)
    token = _proposal(data)["approval_required"]["arguments"]["token"]
    cleanup.execute_cleanup(token, home=data[1], human_confirmed=True, remember=True)
    for index in range(11):
        (data[0] / f"next{index}.py").touch()
    assert "approval_required" in _proposal(data)
    monkeypatch.setattr(cleanup.time, "time", lambda: 1e20)
    assert not cleanup.list_rules(data[1])
    with pytest.raises(ValueError):
        cleanup.read_preview("../../secrets", data[1])


def test_storage_permissions_and_bridge_cannot_approve_itself(data, monkeypatch):
    proposal = _proposal(data)
    token = proposal["approval_required"]["arguments"]["token"]
    store = data[1] / "run/private/cleanup"
    assert store.stat().st_mode & 0o777 == 0o700
    assert (store / (token + ".json")).stat().st_mode & 0o777 == 0o600
    request = {"action": "approved_cleanup", "token": token, "remember": True}
    with pytest.raises(PermissionError):
        dispatch(request, data[1])
    stored = json.loads((store / (token + ".json")).read_text())
    assert "files" in stored["spec"] and "synthetic" not in json.dumps(stored)


def test_model_cannot_cleanup_from_an_unrelated_current_message(data, monkeypatch):
    from ai_os import ai_os_core as core
    monkeypatch.setattr(core, "ask_ollama", lambda *a, **k: json.dumps({"tool": "cleanup_files", "arguments": {"directory": str(data[0]), "pattern": "*.py"}}))
    response = core.handle_user_text("Tell me a joke", {"cleanup_files": lambda **k: pytest.fail("Unrequested cleanup")}, home=data[1])
    assert not response["result"]["ok"]
    assert (data[0] / "one.py").exists()
