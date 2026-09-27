import subprocess

import pytest

from ai_os.tools import system_tools
from ai_os.tools.system_tools import RiskLevel, assess_command


def test_safe_read_command() -> None:
    assessment = assess_command(["uname", "-a"])
    assert assessment.risk == RiskLevel.SAFE
    assert assessment.requires_approval is False


def test_sudo_requires_approval() -> None:
    assessment = assess_command(["sudo", "pacman", "-S", "vim"])
    assert assessment.risk == RiskLevel.DESTRUCTIVE
    assert assessment.requires_approval is True


def test_root_recursive_delete_is_prohibited() -> None:
    assessment = assess_command(["rm", "-rf", "/"])
    assert assessment.risk == RiskLevel.PROHIBITED
    assert assessment.requires_approval is True


def test_pacman_query_is_safe() -> None:
    assessment = assess_command(["pacman", "-Q", "python"])
    assert assessment.risk == RiskLevel.SAFE
    assert assessment.requires_approval is False


def test_builtin_diagnostics_reach_subprocess_without_approval(monkeypatch):
    calls = []

    def run(argv, **kwargs):
        assert kwargs["shell"] is False
        assert 0 < kwargs["timeout"] <= 60
        calls.append(argv)
        output = {
            "/usr/bin/nvidia-smi": "RTX 4060, 8188, 12, 8176, 0, 40, 8.5",
            "/usr/bin/wpctl": "Volume: 0.50 [MUTED]",
            "/usr/bin/brightnessctl": "50" if argv[1] == "get" else "100",
        }[argv[0]]
        return subprocess.CompletedProcess(argv, 0, output, "")

    monkeypatch.setattr(system_tools.subprocess, "run", run)
    assert system_tools.get_nvidia_stats()["memory_total_mb"] == 8188
    assert system_tools.get_volume()["muted"] is True
    assert system_tools.get_brightness()["brightness_percent"] == 50
    assert len(calls) == 4


@pytest.mark.parametrize("command", [
    ["nvidia-smi", "-pm", "1"],
    ["nvidia-smi", "--query-gpu=name", "--format=csv", "--filename=/tmp/output"],
    ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "100%"],
    ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@", "--help"],
    ["brightnessctl", "set", "100%"],
    ["/tmp/brightnessctl", "get"],
])
def test_diagnostic_allowlist_does_not_allow_mutations_or_substitutes(command):
    assert assess_command(command).requires_approval
