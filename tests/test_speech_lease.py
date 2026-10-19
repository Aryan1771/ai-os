"""Real file-lock coordination with synthetic processes and temporary paths."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ai_os.speech_lease import speech_lease

pytest.importorskip("fcntl")


def test_same_process_nested_and_threaded_speech_cannot_overlap(tmp_path):
    def contender():
        with speech_lease(tmp_path) as acquired:
            return acquired

    with speech_lease(tmp_path) as acquired:
        assert acquired
        assert contender() is False
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(contender).result(timeout=2) is False
    assert contender() is True


def test_exception_releases_speech_ownership(tmp_path):
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with speech_lease(tmp_path) as acquired:
            assert acquired
            raise RuntimeError("synthetic failure")
    with speech_lease(tmp_path) as acquired:
        assert acquired
    assert (tmp_path / "run/speech.lock").stat().st_mode & 0o777 == 0o600


def test_independent_process_cannot_steal_an_active_lease(tmp_path):
    script = (
        "import sys; from pathlib import Path; from ai_os.speech_lease import speech_lease\n"
        "with speech_lease(Path(sys.argv[1])) as acquired:\n"
        " print('owned' if acquired else 'busy')\n"
    )
    command = [sys.executable, "-c", script, str(tmp_path)]
    options = {"cwd": Path(__file__).resolve().parents[1], "capture_output": True,
               "text": True, "check": True, "timeout": 10}
    with speech_lease(tmp_path) as acquired:
        assert acquired
        assert subprocess.run(command, **options).stdout.strip() == "busy"
    assert subprocess.run(command, **options).stdout.strip() == "owned"


def test_process_exit_releases_lease_without_cleanup_handler(tmp_path):
    script = (
        "import os, sys; from pathlib import Path; from ai_os.speech_lease import speech_lease\n"
        "with speech_lease(Path(sys.argv[1])) as acquired:\n"
        " print('owned' if acquired else 'busy', flush=True)\n"
        " os._exit(0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        check=True, timeout=10,
    )
    assert result.stdout.strip() == "owned"
    with speech_lease(tmp_path) as acquired:
        assert acquired
