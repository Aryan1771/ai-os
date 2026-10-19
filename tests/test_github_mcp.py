import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ai_os import github_mcp as github
from ai_os.config import atomic_json, load_raw_config


@pytest.fixture
def enabled(tmp_path):
    github.configure_github(True, ["Aryan1771/ai-os"], home=tmp_path, human_confirmed=True)
    return tmp_path


def test_setup_requires_human_and_private_exact_repositories(tmp_path):
    with pytest.raises(github.GitHubMcpError, match="human"):
        github.configure_github(True, ["Aryan1771/ai-os"], home=tmp_path)
    with pytest.raises(github.GitHubMcpError):
        github.configure_github(True, ["https://github.com/a/b"], home=tmp_path, human_confirmed=True)
    github.configure_github(True, ["Aryan1771/ai-os"], home=tmp_path, human_confirmed=True)
    assert (tmp_path / "github-mcp.json").stat().st_mode & 0o777 == 0o600
    assert github._config(tmp_path)["enabled"] is True


def test_symlink_and_public_config_are_rejected(enabled, tmp_path):
    path = enabled / "github-mcp.json"
    path.chmod(0o644)
    with pytest.raises(github.GitHubMcpError):
        github._config(enabled)
    target = tmp_path / "elsewhere"
    path.rename(target)
    target.chmod(0o600)
    path.symlink_to(target)
    with pytest.raises(github.GitHubMcpError):
        github.configure_github(True, ["Aryan1771/ai-os"], home=enabled, human_confirmed=True)
    with pytest.raises(github.GitHubMcpError):
        github._config(enabled)


def test_exact_pinned_executable_hash(tmp_path, monkeypatch):
    directory = tmp_path / "tools/github-mcp-server" / f"v{github.VERSION}"
    directory.mkdir(parents=True)
    binary = directory / "github-mcp-server"
    binary.write_bytes(b"a reviewed binary")
    binary.chmod(0o700)
    monkeypatch.setattr(github, "BINARY_SHA256", hashlib.sha256(binary.read_bytes()).hexdigest())
    assert github._binary(tmp_path) == binary
    binary.write_bytes(b"modified")
    with pytest.raises(github.GitHubMcpError, match="checksum"):
        github._binary(tmp_path)
    binary.chmod(0o777)
    with pytest.raises(github.GitHubMcpError, match="owned"):
        github._binary(tmp_path)


def test_status_preserves_approved_scope_when_binary_is_missing_or_tampered(tmp_path):
    github.configure_github(True, ["ExactOwner/ExactRepo"], home=tmp_path, human_confirmed=True)
    status = github.github_status(home=tmp_path)
    assert status["ok"] is False and status["enabled"] is False
    assert status["configured_enabled"] is True
    assert status["repositories"] == ["ExactOwner/ExactRepo"]


@pytest.mark.parametrize("operation", ["delete_file", "issue_write", "create_pull_request", "merge", "get_me"])
def test_no_write_or_arbitrary_account_tool(operation):
    with pytest.raises(github.GitHubMcpError):
        github._arguments(operation, "Aryan1771/ai-os", "README.md")


@pytest.mark.parametrize("path", ["../README.md", "/etc/passwd", "a/../b", ".env", ".env.local", "id_rsa", "account.pem", "foo\\bar", "secrets.json"])
def test_paths_exclude_traversal_and_obvious_secrets(path):
    with pytest.raises(github.GitHubMcpError):
        github._arguments("file", "Aryan1771/ai-os", path)


def test_sensitive_server_configuration_is_not_inherited(monkeypatch):
    for key in ["GITHUB_HOST", "GITHUB_READ_ONLY", "GITHUB_TOOLS", "GITHUB_TOKEN", "GH_TOKEN", "HTTPS_PROXY"]:
        monkeypatch.setenv(key, "must-not-inherit")
    env = github._environment()
    assert not any(key.startswith(("GITHUB_", "GH_")) for key in env)
    assert "HTTPS_PROXY" not in env


def test_auth_error_never_exposes_token_or_stderr(monkeypatch):
    secret = "gho_" + "x" * 40
    monkeypatch.setattr(github.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, secret.encode(), b"private error"))
    with pytest.raises(github.GitHubMcpError) as error:
        github._token()
    assert secret not in str(error.value)
    assert "private error" not in str(error.value)


def test_disabled_repository_and_remote_fail_before_authentication(tmp_path, enabled, monkeypatch):
    monkeypatch.setattr(github, "_token", lambda: pytest.fail("must not retrieve credentials"))
    assert github.github_read("branches", home=tmp_path / "off")["ok"] is False
    assert github.github_read("branches", "Other/private", home=enabled)["ok"] is False
    raw = load_raw_config(enabled)
    raw["ai_provider"] = "openai_compatible"
    atomic_json(enabled / "config.json", raw)
    assert github.github_read("branches", home=enabled)["ok"] is False
    raw["ai_provider"] = "ollama"
    raw["ollama_url"] = "https://remote-model.invalid/api/chat"
    atomic_json(enabled / "config.json", raw)
    assert github.github_read("branches", home=enabled)["ok"] is False


def test_invalid_model_argument_types_fail_before_account_access(enabled, monkeypatch):
    monkeypatch.setattr(github, "_config", lambda *a: pytest.fail("Malformed input reached account preferences"))
    monkeypatch.setattr(github, "_token", lambda: pytest.fail("Malformed input retrieved credentials"))
    for field in ("operation", "repository", "path"):
        for invalid in (None, [], {}, 0, True, 42.5):
            arguments = {"operation": "file", "repository": "Aryan1771/ai-os", "path": "README.md"}
            arguments[field] = invalid
            result = github.github_read(**arguments, home=enabled)
            assert result["ok"] is False
            assert "must be strings" in result["message"]


def test_embedded_file_content_read_only_and_redacted(enabled, monkeypatch):
    calls = []

    class FakeSession:
        def __init__(self, home):
            assert home == enabled

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def send(self, value):
            calls.append(value)

        def request(self, method, params):
            calls.append((method, params))
            if method == "tools/list":
                return {"tools": [{"name": "get_file_contents", "annotations": {"readOnlyHint": True}}]}
            if method == "tools/call":
                return {"content": [{"type": "text", "text": "file ready"},
                                    {"type": "resource", "resource": {"uri": "https://do-not-fetch.invalid", "text": "# File\ntoken=" + "gho_" + "x" * 40}}]}
            return {}

    monkeypatch.setattr(github, "_Session", FakeSession)
    result = github.github_read("file", home=enabled)
    assert result["ok"] is True
    assert result["untrusted_reference"] is True
    assert "# File" in result["content"]
    assert "gho_" not in result["content"]
    assert calls[-1] == ("tools/call", {"name": "get_file_contents", "arguments": {"owner": "Aryan1771", "repo": "ai-os", "path": "README.md"}})


def test_tool_without_read_only_annotation_is_never_called(enabled, monkeypatch):
    class FakeSession:
        def __init__(self, home):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def send(self, value):
            pass

        def request(self, method, params):
            assert method != "tools/call"
            return {"tools": [{"name": "list_branches", "annotations": {"readOnlyHint": False}}]}

    monkeypatch.setattr(github, "_Session", FakeSession)
    assert github.github_read("branches", home=enabled)["ok"] is False


def test_malformed_server_catalog_and_content_fail_closed(enabled, monkeypatch):
    current, calls = {}, []

    class FakeSession:
        def __init__(self, home):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def send(self, value):
            pass

        def request(self, method, params):
            calls.append(method)
            if method == "tools/list":
                return {"tools": current["tools"]}
            if method == "tools/call":
                return {"content": current["content"]}
            return {}

    monkeypatch.setattr(github, "_Session", FakeSession)
    for malformed in (None, [], "invalid", False):
        current["tools"] = [{"name": "list_branches", "annotations": malformed}]
        calls.clear()
        assert github.github_read("branches", home=enabled)["ok"] is False
        assert "tools/call" not in calls
    for malformed in (None, {}, "invalid"):
        current["tools"] = malformed
        calls.clear()
        assert github.github_read("branches", home=enabled)["ok"] is False
        assert "tools/call" not in calls
    current["tools"] = [{"name": "list_branches", "annotations": {"readOnlyHint": True}}]
    for malformed in (None, {}, "invalid", [], [None], [{"type": "text", "text": []}],
                      [{"type": "resource", "resource": None}]):
        current["content"] = malformed
        assert github.github_read("branches", home=enabled)["ok"] is False


def test_result_removes_private_keys_and_is_bounded():
    text = "before\n-----BEGIN PRIVATE KEY-----\nprivate material\n-----END PRIVATE KEY-----\nafter\n" + "x" * 30000
    result = github._safe_text(text)
    assert "private material" not in result
    assert "after" in result
    assert len(result) == github.MAX_RESULT_CHARS


def _fake_process(monkeypatch, script):
    original = subprocess.Popen
    children, arguments = [], []
    monkeypatch.setattr(github, "_binary", lambda home: Path("/reviewed/github-mcp-server"))
    monkeypatch.setattr(github, "_token", lambda: "private-test-token-only")

    def create(argv, **kwargs):
        arguments.append((argv, kwargs))
        child = original([sys.executable, "-c", script], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(github.subprocess, "Popen", create)
    return children, arguments


def test_protocol_and_process_configuration_are_fixed(tmp_path, monkeypatch):
    script = "import json,sys\nfor line in sys.stdin:\n m=json.loads(line)\n if 'id' in m: print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':{'ok':True}}),flush=True)"
    children, arguments = _fake_process(monkeypatch, script)
    with github._Session(tmp_path) as session:
        assert session.request("initialize", {}) == {"ok": True}
        assert os.getpgid(session.process.pid) == os.getpgrp()
    argv, kwargs = arguments[0]
    assert "--read-only" in argv
    assert kwargs["shell"] is False
    assert kwargs["stderr"] == subprocess.DEVNULL
    assert "private-test-token-only" not in repr(argv)
    assert children[0].poll() is not None


def test_constructor_failure_stops_child_and_closes_selector(tmp_path, monkeypatch):
    children, _ = _fake_process(monkeypatch, "import time; time.sleep(30)")
    closed = []

    class FailedSelector:
        def register(self, *args):
            raise RuntimeError("registration failed")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(github.selectors, "DefaultSelector", FailedSelector)
    with pytest.raises(RuntimeError, match="registration failed"):
        github._Session(tmp_path)
    assert children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed
    assert closed == [True]


def test_interrupted_request_unwinds_child_cleanup(tmp_path, monkeypatch):
    children, _ = _fake_process(monkeypatch, "import time; time.sleep(30)")
    with pytest.raises(SystemExit):
        with github._Session(tmp_path):
            # hub_bridge's SIGTERM handler raises SystemExit to unwind Stop/Steer.
            raise SystemExit(130)
    assert children[0].poll() is not None


def test_protocol_timeout_reaps_child(tmp_path, monkeypatch):
    children, _ = _fake_process(monkeypatch, "import time; time.sleep(30)")
    with pytest.raises(github.GitHubMcpError, match="timed out"):
        with github._Session(tmp_path, seconds=0.05) as session:
            session.request("initialize", {})
    assert children[0].poll() is not None


def test_oversize_response_stops_and_reaps_child(tmp_path, monkeypatch):
    monkeypatch.setattr(github, "MAX_WIRE_BYTES", 300)
    script = "import sys,time; sys.stdin.readline(); print('x'*500,flush=True); time.sleep(30)"
    children, _ = _fake_process(monkeypatch, script)
    with pytest.raises(github.GitHubMcpError, match="size limit"):
        with github._Session(tmp_path) as session:
            session.request("initialize", {})
    assert children[0].poll() is not None
