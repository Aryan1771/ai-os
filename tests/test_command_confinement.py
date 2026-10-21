"""Broad-command bootstrap must resolve trusted code before entering its boundary."""

import importlib.machinery
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_os.tools import system_tools


def shadow_package(directory):
    package = directory / "ai_os"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        'raise RuntimeError("Synthetic shadow package was imported")\n', encoding="utf-8",
    )
    (package / "unprivileged_command.py").write_text(
        'raise RuntimeError("Synthetic shadow helper was imported")\n', encoding="utf-8",
    )
    return package


def test_broad_bootstrap_is_isolated_and_keeps_reviewed_command_cwd(tmp_path, monkeypatch):
    shadow_package(tmp_path)
    # Resolve metadata only: never import or execute the synthetic shadow.
    shadow = importlib.machinery.PathFinder.find_spec("ai_os", [str(tmp_path)])
    assert Path(shadow.origin) == tmp_path / "ai_os/__init__.py"
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "Synthetic confined result", "")

    monkeypatch.setattr(system_tools, "run_bounded", run)
    result = system_tools.run_command(
        ["/usr/bin/ls", "synthetic-entry"], cwd=str(tmp_path),
        timeout_sec=7, approve=True, user_sandbox=True,
    )
    assert result.ok
    assert len(calls) == 1
    argv, options = calls[0]
    assert argv == [sys.executable, "-I", "-m", "ai_os.unprivileged_command",
                    "/usr/bin/ls", "synthetic-entry"]
    assert options["cwd"] == str(tmp_path.resolve())
    assert options["timeout"] == 7


@pytest.mark.parametrize("shadow_source", ["cwd", "pythonpath", "both"])
def test_real_isolated_import_metadata_ignores_cwd_and_interpreter_environment(
    tmp_path, shadow_source,
):
    cwd = tmp_path / "working"
    extra = tmp_path / "environment"
    cwd.mkdir()
    extra.mkdir()
    if shadow_source in {"cwd", "both"}:
        shadow_package(cwd)
    if shadow_source in {"pythonpath", "both"}:
        shadow_package(extra)
    expected = Path(system_tools.__file__).resolve().parents[1] / "unprivileged_command.py"
    # Read only module origins/flags. Do not import the helper, execute a command,
    # enter Bubblewrap, consume a grant or access this owner's runtime settings.
    code = (
        "import importlib.util,json,sys; from pathlib import Path; "
        "spec=importlib.util.find_spec('ai_os.unprivileged_command'); "
        "print(json.dumps({'trusted_helper':Path(spec.origin).resolve()==Path(sys.argv[1]),"
        "'isolated':bool(sys.flags.isolated),'ignored_environment':bool(sys.flags.ignore_environment),"
        "'no_user_site':bool(sys.flags.no_user_site),"
        "'cwd_excluded':'' not in sys.path and str(Path.cwd()) not in sys.path}))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code, str(expected)], cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(extra),
             "PYTHONHOME": str(tmp_path / "nonexistent-python-home"),
             "PYTHONUSERBASE": str(tmp_path / "untrusted-user-site"),
             "PYTHONINSPECT": "1"},
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        shell=False, timeout=10, check=True,
    )
    assert json.loads(result.stdout) == {
        "trusted_helper": True, "isolated": True, "ignored_environment": True,
        "no_user_site": True, "cwd_excluded": True,
    }


def test_missing_installed_helper_fails_without_ordinary_execution_fallback(
    tmp_path, monkeypatch,
):
    calls = []

    def missing(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 1, "", "Synthetic missing installed helper")

    monkeypatch.setattr(system_tools, "run_bounded", missing)
    result = system_tools.run_command(
        ["/usr/bin/ls", "synthetic-entry"], cwd=str(tmp_path),
        approve=True, user_sandbox=True,
    )
    assert result.ok is False and result.returncode == 1
    assert len(calls) == 1
    assert calls[0][0][1:4] == ["-I", "-m", "ai_os.unprivileged_command"]


def test_non_granted_reviewed_execution_does_not_use_broad_wrapper(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(system_tools, "run_bounded", lambda argv, **_kwargs:
                        calls.append(argv) or subprocess.CompletedProcess(argv, 0, "", ""))
    assert system_tools.run_command(
        ["/usr/bin/ls", "synthetic-entry"], cwd=str(tmp_path), approve=True,
    ).ok
    assert calls == [["/usr/bin/ls", "synthetic-entry"]]
