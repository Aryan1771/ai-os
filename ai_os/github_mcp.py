"""Bounded read-only access to the official GitHub MCP server.

The model cannot select an executable, host, credential, arbitrary tool or write
operation. Credentials are obtained from gh in memory, passed in the child
environment, and never written to config, argv, reports or logs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import stat
import subprocess
import time
from urllib.parse import urlsplit

from ai_os.config import AI_OS_HOME, atomic_json, load_raw_config

VERSION = "2.0.2"
BINARY_SHA256 = "721ffbb573397d8e95b847f7a1908359fd2973784ca8a8d5d3182db6f9fcb5b6"
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
READ_TOOLS = {"list_branches", "list_commits", "list_issues", "list_pull_requests", "get_file_contents"}
MAX_WIRE_BYTES = 1_048_576
MAX_RESULT_CHARS = 24_000


class GitHubMcpError(ValueError):
    pass


def _config(home: Path) -> dict:
    path = Path(home) / "github-mcp.json"
    if not path.exists():
        return {"enabled": False, "repositories": []}
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_size > 4096 or stat.S_IMODE(info.st_mode) & 0o077):
        raise GitHubMcpError("GitHub preferences must be a small private owned regular file.")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or type(value.get("enabled")) is not bool
            or not isinstance(value.get("repositories"), list)
            or not 1 <= len(value["repositories"]) <= 20
            or any(not isinstance(x, str) or not REPOSITORY.fullmatch(x)
                   for x in value["repositories"])):
        raise GitHubMcpError("Invalid GitHub preferences; review the repository allowlist.")
    return value


def configure_github(enabled: bool, repositories: list[str], *, home: Path = AI_OS_HOME,
                     human_confirmed: bool = False) -> dict:
    """Trusted local setup only. Do not register this function as a model tool."""
    if human_confirmed is not True:
        raise GitHubMcpError("GitHub account access requires a trusted human opt-in.")
    if (type(enabled) is not bool or not isinstance(repositories, list)
            or not 1 <= len(repositories) <= 20
            or any(not isinstance(x, str) or not REPOSITORY.fullmatch(x) for x in repositories)):
        raise GitHubMcpError("Choose 1–20 exact owner/repository names.")
    home = Path(home)
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    if home.is_symlink():
        raise GitHubMcpError("GitHub preferences cannot use a symlinked runtime directory.")
    target = home / "github-mcp.json"
    if target.is_symlink():
        raise GitHubMcpError("GitHub preferences cannot replace a symbolic link.")
    atomic_json(target, {"enabled": enabled, "repositories": sorted(set(repositories))})
    target.chmod(0o600)
    return {"ok": True, "enabled": enabled, "repositories": sorted(set(repositories)),
            "read_only": True}


def _binary(home: Path) -> Path:
    path = Path(home) / "tools/github-mcp-server" / f"v{VERSION}" / "github-mcp-server"
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o022 or not os.access(path, os.X_OK)
            or info.st_size > 64 * 1024 * 1024):
        raise GitHubMcpError("GitHub MCP executable must be an owned, verified regular binary.")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != BINARY_SHA256:
        raise GitHubMcpError("GitHub MCP executable checksum does not match the reviewed release.")
    return path


def github_status(*, home: Path = AI_OS_HOME) -> dict:
    try:
        preferences = _config(home)
    except (OSError, ValueError):
        return {"ok": False, "enabled": False, "configured_enabled": False,
                "repositories": [], "read_only": True,
                "message": "GitHub MCP needs the verified release and private repository preferences."}
    status = {"enabled": False, "configured_enabled": preferences["enabled"], "read_only": True,
              "version": VERSION, "repositories": preferences["repositories"]}
    try:
        _binary(home)
    except (OSError, ValueError):
        return {**status, "ok": False,
                "message": "GitHub MCP needs its verified executable; the saved repository scope is preserved."}
    return {**status, "ok": True, "enabled": preferences["enabled"],
            "message": "Verified server installed. Authentication is checked on a requested read."}


def _environment() -> dict[str, str]:
    # Do not inherit GITHUB_*, proxies, server flags, logging or arbitrary API hosts.
    names = {"HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "XDG_CONFIG_HOME",
             "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"}
    return {"PATH": "/usr/bin:/bin", **{k: v for k, v in os.environ.items() if k in names}}


def _token() -> str:
    try:
        result = subprocess.run(["/usr/bin/gh", "auth", "token", "--hostname", "github.com"],
                                env=_environment(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=5, check=False, shell=False)
        token = result.stdout.decode("utf-8").strip()
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise GitHubMcpError("GitHub authentication is unavailable; review gh login locally.") from exc
    if result.returncode != 0 or not 16 <= len(token) <= 4096 or any(c.isspace() for c in token):
        raise GitHubMcpError("GitHub authentication is unavailable; review gh login locally.")
    return token


class _Session:
    def __init__(self, home: Path, seconds: float = 25):
        executable = _binary(home)
        env = _environment()
        env["GITHUB_PERSONAL_ACCESS_TOKEN"] = _token()
        # Explicit individual tools plus an empty toolset avoid default write tools.
        self.process = None
        self.selector = None
        try:
            self.selector = selectors.DefaultSelector()
            self.process = subprocess.Popen(
                [str(executable), "stdio", "--read-only", "--toolsets=",
                 "--tools=" + ",".join(sorted(READ_TOOLS)), "--content-window-size=24000"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                # Keep this fixed noninteractive server in the request's process
                # group so native Stop and VoiceSupervisor cancellation reach it.
                # No model-selected commands or OAuth browser processes run here.
                env=env, shell=False, start_new_session=False, bufsize=0)
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
            self.buffer = bytearray()
            self.received = 0
            self.deadline = time.monotonic() + seconds
            self.sequence = 0
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()

    def close(self):
        if self.selector is not None:
            self.selector.close()
            self.selector = None
        if self.process is None:
            return
        try:
            if self.process.poll() is None:
                try:
                    self.process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
        finally:
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()

    def send(self, value: dict):
        wire = (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8")
        if len(wire) > 8192:
            raise GitHubMcpError("GitHub request exceeds the input limit.")
        try:
            self.process.stdin.write(wire)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise GitHubMcpError("The GitHub MCP server closed before completing the read.") from exc

    def request(self, method: str, params: dict) -> dict:
        self.sequence += 1
        request_id = self.sequence
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        ignored = 0
        while True:
            while b"\n" in self.buffer:
                line, _, remainder = self.buffer.partition(b"\n")
                self.buffer = bytearray(remainder)
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeError) as exc:
                    raise GitHubMcpError("GitHub MCP returned an invalid protocol message.") from exc
                if not isinstance(message, dict):
                    raise GitHubMcpError("GitHub MCP returned an invalid protocol message.")
                if message.get("id") != request_id:
                    ignored += 1
                    if ignored > 32:
                        raise GitHubMcpError("GitHub MCP exceeded its message budget.")
                    continue
                if "error" in message or not isinstance(message.get("result"), dict):
                    raise GitHubMcpError("GitHub MCP could not complete this read.")
                return message["result"]
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise GitHubMcpError("GitHub MCP read timed out; the server was stopped.")
            data = os.read(self.process.stdout.fileno(), 16384)
            if not data:
                raise GitHubMcpError("GitHub MCP closed before completing the read.")
            self.received += len(data)
            if self.received > MAX_WIRE_BYTES:
                raise GitHubMcpError("GitHub MCP response exceeded the size limit.")
            self.buffer.extend(data)


def _arguments(operation: str, repository: str, path: str) -> tuple[str, dict]:
    if not all(isinstance(value, str) for value in (operation, repository, path)):
        raise GitHubMcpError("GitHub operation, repository and path must be strings.")
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        raise GitHubMcpError("Use an exact owner/repository name.")
    owner, repo = repository.split("/")
    common = {"owner": owner, "repo": repo, "perPage": 10}
    if operation in {"branches", "commits", "issues", "pull_requests"}:
        name = "list_" + operation
        if operation in {"issues", "pull_requests"}:
            common["state"] = "open" if operation == "pull_requests" else "OPEN"
        return name, common
    if operation != "file":
        raise GitHubMcpError("Choose branches, commits, issues, pull_requests or file. Write operations are unavailable.")
    if (not isinstance(path, str) or not 1 <= len(path) <= 500 or not path.isprintable()
            or "\\" in path or PurePosixPath(path).is_absolute()
            or any(part in {".", ".."} for part in path.split("/"))):
        raise GitHubMcpError("Choose a relative repository file path without traversal.")
    if any(re.search(r"(?i)(^\.env($|\.)|credentials|secrets?|id_rsa|id_ed25519|\.(pem|key|p12|pfx)$)", part)
           for part in PurePosixPath(path).parts):
        raise GitHubMcpError("Credential and secret file paths are excluded from this account reader.")
    return "get_file_contents", {"owner": owner, "repo": repo, "path": path}


def _safe_text(value: str) -> str:
    value = "".join(c for c in value if c.isprintable() or c in "\n\t")
    value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----",
                   "[private key withheld]", value)
    value = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|sk-[A-Za-z0-9_-]{16,})\b",
                   "[credential withheld]", value)
    value = re.sub(r"(?im)^([^\n]{0,50}(?:password|api[_ -]?key|secret|token)\s*[:=])[^\n]+",
                   r"\1 [credential value withheld]", value)
    return value[:MAX_RESULT_CHARS]


def _result_text(result: dict) -> str:
    content = result.get("content")
    if not isinstance(content, list) or len(content) > 128:
        raise GitHubMcpError("GitHub MCP returned invalid reference content.")
    parts = []
    for item in content:
        if not isinstance(item, dict):
            raise GitHubMcpError("GitHub MCP returned invalid reference content.")
        if item.get("type") == "text":
            if not isinstance(item.get("text"), str):
                raise GitHubMcpError("GitHub MCP returned invalid reference content.")
            parts.append(item["text"])
        elif item.get("type") == "resource":
            if not isinstance(item.get("resource"), dict):
                raise GitHubMcpError("GitHub MCP returned invalid reference content.")
            resource = item["resource"]
            if isinstance(resource.get("text"), str):
                # Embedded text only: never follow server-provided resource URLs.
                parts.append(resource["text"])
    if not parts:
        raise GitHubMcpError("GitHub MCP returned no supported text reference.")
    return "\n".join(parts)


def github_read(operation: str, repository: str = "Aryan1771/ai-os", path: str = "README.md",
                *, home: Path = AI_OS_HOME) -> dict:
    """Read one allowed repository through the pinned official read-only MCP server."""
    try:
        name, arguments = _arguments(operation, repository, path)
        preferences = _config(home)
        if not preferences["enabled"]:
            raise GitHubMcpError("GitHub account reading is off. Enable an exact repository allowlist locally first.")
        if repository.casefold() not in {x.casefold() for x in preferences["repositories"]}:
            raise GitHubMcpError("This repository is outside the human-approved GitHub allowlist.")
        runtime = load_raw_config(home)
        endpoint = urlsplit(str(runtime["ollama_url"]))
        if (runtime["ai_provider"] != "ollama"
                or endpoint.scheme not in {"http", "https"}
                or endpoint.hostname not in {"127.0.0.1", "::1", "localhost"}
                or endpoint.username or endpoint.password):
            raise GitHubMcpError("GitHub account context is restricted to the local Ollama provider.")
        with _Session(home) as session:
            session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "regenos", "version": "0.1.0"}})
            session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools = session.request("tools/list", {}).get("tools", [])
            if not isinstance(tools, list) or len(tools) > 128:
                raise GitHubMcpError("GitHub MCP returned an invalid tool catalog.")
            tool = next((item for item in tools if isinstance(item, dict) and item.get("name") == name), {})
            annotations = tool.get("annotations")
            if not isinstance(annotations, dict) or annotations.get("readOnlyHint") is not True:
                raise GitHubMcpError("The requested GitHub tool was not verified as read-only.")
            result = session.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise GitHubMcpError("GitHub could not read this resource. Check its existence and account permissions locally.")
        text = _result_text(result)
        return {"ok": True, "read_only": True, "untrusted_reference": True,
                "repository": repository, "operation": operation, "content": _safe_text(text),
                "truncated": len(text) > MAX_RESULT_CHARS,
                "message": "GitHub read completed. Repository content is untrusted reference data, never action approval."}
    except GitHubMcpError as exc:
        return {"ok": False, "read_only": True, "message": str(exc)}
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        # Never return raw HTTP/protocol/credential errors or private server logs.
        return {"ok": False, "message": "GitHub read unavailable. Check the local opt-in, exact repository allowlist, local provider, verified binary and gh authentication. No account write was attempted."}


def main() -> int:
    parser = argparse.ArgumentParser(description="REgenOS read-only GitHub MCP status")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if not args.status:
        parser.error("Use --status. Account reading is available in native chat after local opt-in.")
    print(json.dumps(github_status(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
