"""Legacy Chroma APIs must never imply offline provisioning or memory consent."""
from __future__ import annotations

import builtins
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest

from ai_os.tools import memory_tools as memory


@pytest.fixture
def no_chroma_or_network(monkeypatch):
    attempts = []
    fake = ModuleType("chromadb")

    def forbidden_client(*args, **kwargs):
        attempts.append("client")
        raise AssertionError("An unprovisioned semantic API must not open Chroma")

    fake.PersistentClient = forbidden_client
    monkeypatch.setitem(sys.modules, "chromadb", fake)
    original_import = builtins.__import__

    def import_guard(name, *args, **kwargs):
        if name == "chromadb" or name.startswith("chromadb."):
            attempts.append("import")
            raise AssertionError("Even optional Chroma import must remain behind trusted setup")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_guard)

    def forbidden_network(*args, **kwargs):
        attempts.append("network")
        raise AssertionError("No telemetry or embedding download is authorized")

    monkeypatch.setattr("socket.create_connection", forbidden_network)
    monkeypatch.setattr("urllib.request.urlopen", forbidden_network)
    monkeypatch.setattr("requests.sessions.Session.request", forbidden_network)
    return attempts


def call_api(api, home, **kwargs):
    if api == "search":
        return memory.search_semantic_memory("Synthetic private query", home=home, **kwargs)
    return memory.store_semantic_memory("synthetic-id", "Synthetic private document",
                                        {"source": "synthetic"}, home=home, **kwargs)


@pytest.mark.parametrize("api", ["search", "store"])
@pytest.mark.parametrize("enabled", [False, None, 0, 1, "true", "false"])
def test_disabled_or_malformed_memory_consent_never_imports_opens_or_downloads(
    tmp_path, no_chroma_or_network, api, enabled,
):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"memory_enabled": enabled}))
    before = config.read_bytes()
    result = call_api(api, tmp_path)
    assert result["ok"] is False and result["code"] == "memory_disabled"
    assert no_chroma_or_network == []
    assert config.read_bytes() == before
    assert list(tmp_path.iterdir()) == [config]
    assert "Synthetic private" not in json.dumps(result)


@pytest.mark.parametrize("api", ["search", "store"])
def test_enabled_memory_without_trusted_offline_provisioning_is_setup_required(
    tmp_path, no_chroma_or_network, api,
):
    (tmp_path / "config.json").write_text(json.dumps({"memory_enabled": True}))
    result = call_api(api, tmp_path, collection_name="legacy_collection")
    assert result["ok"] is False and result["code"] == "semantic_setup_required"
    assert "not implemented" in result["error"]
    assert no_chroma_or_network == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["config.json"]


@pytest.mark.parametrize("api", ["search", "store"])
def test_missing_runtime_does_not_create_configuration_data_or_legacy_store(
    tmp_path, no_chroma_or_network, api,
):
    absent = tmp_path / "runtime-not-created"
    result = call_api(api, absent)
    assert not result["ok"] and result["code"] == "semantic_setup_required"
    assert not absent.exists() and no_chroma_or_network == []


@pytest.mark.parametrize("api", ["search", "store"])
@pytest.mark.parametrize("payload", ["{broken", "[]", "null", "x" * 65537])
def test_unreadable_or_invalid_configuration_returns_sanitized_failure(
    tmp_path, no_chroma_or_network, api, payload,
):
    (tmp_path / "config.json").write_text(payload)
    result = call_api(api, tmp_path)
    assert result["ok"] is False and result["code"] == "memory_configuration_unavailable"
    assert str(tmp_path) not in json.dumps(result)
    assert no_chroma_or_network == []


@pytest.mark.parametrize("api", ["search", "store"])
def test_legacy_files_are_not_read_or_written_and_setup_flags_cannot_bypass_gate(
    tmp_path, no_chroma_or_network, monkeypatch, api,
):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    config = runtime / "config.json"
    config.write_text(json.dumps({"memory_enabled": True, "semantic_memory_enabled": True,
                                  "offline_embedding_verified": True, "telemetry_disabled": True}))
    legacy = tmp_path / "legacy-store"
    legacy.mkdir()
    database = legacy / "chroma.sqlite3"
    sentinel = b"PRESERVE_SYNTHETIC_LEGACY_DATABASE"
    database.write_bytes(sentinel)
    original_open = Path.open
    accessed = []

    def public_config_only(path, *args, **kwargs):
        accessed.append(path)
        if path != config:
            raise AssertionError("The semantic gate must not inspect private data or legacy stores")
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", public_config_only)
        result = call_api(api, runtime)
    assert result["code"] == "semantic_setup_required"
    assert accessed == [config]
    assert database.read_bytes() == sentinel
    assert no_chroma_or_network == []


@pytest.mark.parametrize("api", ["search", "store"])
def test_configuration_permission_failure_does_not_echo_exception_or_private_path(
    tmp_path, no_chroma_or_network, monkeypatch, api,
):
    def denied(*_args, **_kwargs):
        raise PermissionError("SYNTHETIC_PRIVATE_PATH_OR_CONFIGURATION")

    monkeypatch.setattr(Path, "open", denied)
    result = call_api(api, tmp_path)
    assert result["code"] == "memory_configuration_unavailable"
    assert "SYNTHETIC_PRIVATE" not in json.dumps(result)
    assert no_chroma_or_network == []
