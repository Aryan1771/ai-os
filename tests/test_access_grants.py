from concurrent.futures import ThreadPoolExecutor

import pytest

from ai_os import ai_os_core as core
from ai_os.security import access_grants as grants
from ai_os.settings_store import save_settings
from ai_os.hub_bridge import dispatch


@pytest.mark.parametrize("text,seconds", [
    ("30 seconds", 30), ("5 min", 300), ("1.5 hours", 5400), ("1h 30m", 5400),
    ("five minutes", 300), ("one hour and thirty seconds", 3630),
    ("twenty-five seconds", 25), ("an hour", 3600), ("24 hours", 86400),
])
def test_duration_units(text, seconds):
    assert grants.duration(text) == seconds


@pytest.mark.parametrize("text", ["-5 minutes", "0 seconds", "25 hours", "forever", "5 days", "5 minutes and reboot", "0.1s"])
def test_invalid_durations(text):
    with pytest.raises(ValueError):
        grants.duration(text)


@pytest.fixture
def store(tmp_path):
    save_settings({"command_access": "supervised"}, tmp_path, human_confirmed=True)
    return grants.GrantStore(tmp_path)


def activate(store, session="default", seconds=60):
    request = store.request(session, {"kind": "timed", "seconds": seconds})
    store.confirm(session, request["token"], human_confirmed=True)


def test_request_never_grants_without_local_confirmation(store):
    request = store.request("default", {"kind": "timed", "seconds": 30})
    assert "grant" not in store.status("default")
    with pytest.raises(PermissionError):
        store.confirm("default", request["token"])
    with pytest.raises(PermissionError):
        store.confirm("default", "forged", human_confirmed=True)


def test_exact_command_binding_once_and_cross_process_storage(store, tmp_path):
    args = {"command": ["touch", "/tmp/regenos-example"], "cwd": "/tmp"}
    store.pending_command("default", args)
    request = store.request("default", {"kind": "once", "seconds": 120})
    store.confirm("default", request["token"], human_confirmed=True)
    restarted = grants.GrantStore(tmp_path)
    assert restarted.consume("other", args) is None
    assert restarted.consume("default", args | {"cwd": "/"}) is None
    changed = {"command": ["touch", "/tmp/different"], "cwd": "/tmp"}
    assert restarted.consume("default", changed) is None
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: grants.GrantStore(tmp_path).consume("default", args), range(2)))
    assert sum(value is not None for value in outcomes) == 1


def test_pending_replacement_invalidates_old_confirmation(store):
    store.pending_command("default", {"command": ["touch", "/tmp/a"]})
    old = store.request("default", {"kind": "once", "seconds": 120})
    store.pending_command("default", {"command": ["touch", "/tmp/b"]})
    with pytest.raises(PermissionError):
        store.confirm("default", old["token"], human_confirmed=True)


def test_grant_expiry_reboot_revocation_and_mode_change(store, monkeypatch):
    activate(store)
    now = grants.time.monotonic()
    monkeypatch.setattr(grants.time, "monotonic", lambda: now + 61)
    assert "grant" not in store.status("default")
    activate(store)
    boot = grants.psutil.boot_time()
    monkeypatch.setattr(grants.psutil, "boot_time", lambda: boot + 100)
    assert "grant" not in store.status("default")
    activate(store)
    store.revoke("default")
    assert store.status("default") == {}
    activate(store)
    save_settings({"command_access": "restricted"}, store.home, human_confirmed=True)
    save_settings({"command_access": "supervised"}, store.home, human_confirmed=True)
    assert store.status("default") == {}


@pytest.mark.parametrize("argv", [
    ["sudo", "touch", "/tmp/x"], ["bash", "-c", "touch /tmp/x"],
    ["python", "-c", "print(1)"], ["rm", "/tmp/x"], ["pacman", "-S", "vim"],
    ["touch", "/etc/config"], ["touch", "/dev/nvme0n1"],
    ["/tmp/touch", "/tmp/x"], ["touch", "--reference=/etc/passwd", "/tmp/x"],
])
def test_timed_scope_cannot_approve_escalation_or_unreviewed_commands(store, argv):
    activate(store)
    try:
        result = store.consume("default", {"command": argv})
    except ValueError:
        result = None
    assert result is None


def test_timed_scope_allows_new_file_pins_executable_and_blocks_overwrite(store, tmp_path):
    target = tmp_path.parent / (tmp_path.name + "-new-file")
    activate(store)
    spec = store.consume("default", {"command": ["touch", str(target)]})
    assert spec["command"][0] == "/usr/bin/touch"
    target.touch()
    assert store.consume("default", {"command": ["touch", str(target)]}) is None
    target.unlink()
    assert store.consume("default", {"command": ["touch", str(tmp_path/"config.json")]}) is None


def test_speech_request_is_pending_not_model_granted(store, monkeypatch):
    monkeypatch.setattr(core.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(core, "ask_ollama", lambda *a, **k: pytest.fail("Grant parsing must not use model"))
    response = core.handle_user_text("I give you full access for five minutes.", home=store.home)
    assert "pending" in response["content"]
    assert "grant" not in store.status("default")
    core.handle_user_text("revoke access", home=store.home)
    assert store.status("default") == {}


def test_model_cannot_create_or_confirm_grants(store, monkeypatch):
    monkeypatch.setattr(core, "ask_ollama", lambda *a, **k: "I give you full access for 5 minutes")
    core.handle_user_text("Hello", home=store.home)
    assert store.status("default") == {}
    assert not {"confirm_access_grant", "grant_access", "revoke_all"} & core.build_tool_registry().keys()
    with pytest.raises(PermissionError):
        dispatch({"action": "confirm_access_grant", "token": "fake", "confirmed": True}, store.home)


def test_exact_grant_runs_pending_command_once_through_bridge(store, monkeypatch):
    from ai_os.tools import system_tools
    calls = []
    monkeypatch.setattr(system_tools, "run_command", lambda **kw: calls.append(kw) or {"ok": True})
    store.pending_command("default", {"command": ["touch", "/tmp/granted-once"]})
    request = store.request("default", {"kind": "once", "seconds": 120})
    payload = {"action": "confirm_access_grant", "token": request["token"], "confirmed": True}
    assert dispatch(payload, store.home)["response"]["result"]["ok"]
    assert len(calls) == 1 and calls[0]["approve"] is True
    with pytest.raises(PermissionError):
        dispatch(payload, store.home)


def test_expired_request_cannot_be_confirmed(store, monkeypatch):
    request = store.request("default", {"kind": "timed", "seconds": 60})
    now = grants.time.monotonic()
    monkeypatch.setattr(grants.time, "monotonic", lambda: now + 121)
    with pytest.raises(PermissionError):
        store.confirm("default", request["token"], human_confirmed=True)


def test_wall_clock_rollback_does_not_extend_grant(store, monkeypatch):
    activate(store)
    mono, wall = grants.time.monotonic(), grants.time.time()
    monkeypatch.setattr(grants.time, "time", lambda: wall - 10000)
    monkeypatch.setattr(grants.time, "monotonic", lambda: mono + 61)
    assert store.status("default") == {}


def test_corrupt_deadline_cannot_make_permanent_grant(store):
    activate(store)
    with store.transaction("default") as state:
        state["grant"]["deadline"] = float("nan")
    assert store.status("default") == {}


def test_symlink_escape_is_not_in_timed_scope(store, tmp_path):
    link = tmp_path.parent / (tmp_path.name + "-link")
    link.symlink_to(tmp_path, target_is_directory=True)
    activate(store)
    assert store.consume("default", {"command": ["touch", str(link/"new-auth-file")]}) is None
    link.unlink()
