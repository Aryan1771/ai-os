import json
from pathlib import Path
import subprocess
import sys
import time

import psutil

import pytest
import requests

from ai_os.command_runner import run_bounded
from ai_os.tools.filesystem_tools import list_directory
from ai_os.services.voice_errors import diagnostic, VoicePipelineError


def test_directory_inspection_bounded_and_does_not_follow_links(tmp_path):
    (tmp_path/'folder').mkdir()
    (tmp_path/'secret-link').symlink_to('/etc/shadow')
    result = list_directory(str(tmp_path), 2)
    assert result['ok']
    assert {e['kind'] for e in result['entries']} == {'directory', 'symlink'}
    assert 'shadow' not in json.dumps(result)
    assert list_directory(str(tmp_path), 1)['truncated']
    assert not list_directory(str(tmp_path/'missing'))['ok']
    with pytest.raises(ValueError):
        list_directory(str(tmp_path), 100000)


def test_generic_command_runner_noninteractive_cwd_and_output(tmp_path):
    result = run_bounded([sys.executable, '-c', 'import os,sys; print(os.getcwd()); print(sys.stdin.read())'],
                         cwd=str(tmp_path), timeout=2)
    assert result.returncode == 0 and result.stdout.strip() == str(tmp_path)
    assert result.stderr == ''


def test_excessive_output_is_stopped_without_unbounded_capture(tmp_path):
    result = run_bounded([sys.executable, '-c', 'import os; [os.write(1,b"x"*4096) for _ in range(1000)]'],
                         cwd=str(tmp_path), timeout=2)
    assert result.returncode != 0 and 'output exceeded' in result.stderr
    assert len(result.stdout.encode()) <= 65536


def test_timeout_terminates_command_group(tmp_path):
    script = ('import subprocess,sys,time; '
              'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); '
              'print(child.pid,flush=True); time.sleep(30)')
    with pytest.raises(subprocess.TimeoutExpired) as failure:
        run_bounded([sys.executable, '-c', script], cwd=str(tmp_path), timeout=0.5)
    child_pid = int(failure.value.stdout.strip())
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        try:
            if psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE:
                return
        except psutil.NoSuchProcess:
            return
        time.sleep(0.01)
    pytest.fail("Command descendant survived timeout cleanup")


def test_broad_grant_allows_readonly_system_directory_cwd():
    from ai_os.unprivileged_command import bubblewrap_argv
    argv = bubblewrap_argv(['/usr/bin/pwd'], Path.home(), Path('/usr'))
    assert argv[argv.index('--chdir')+1] == '/usr'
    assert argv[argv.index('--ro-bind')+1:argv.index('--ro-bind')+3] == ['/', '/']
    assert '--dev' in argv and '--cap-drop' in argv


def test_voice_error_codes_do_not_echo_private_exception_text():
    for exc, phase, expected in [
        (requests.ConnectionError('private conversation'), 'thinking', 'model_connection'),
        (requests.Timeout('private conversation'), 'thinking', 'model_timeout'),
        (subprocess.CalledProcessError(1, ['private command']), 'speaking', 'speech_failed'),
        (ValueError('private transcript'), 'thinking', 'reasoning_failed'),
    ]:
        code, message = diagnostic(exc, phase)
        assert code == expected and 'private' not in message
    assert diagnostic(VoicePipelineError('transcription_failed', 'Transcription failed'), 'transcribing')[0] == 'transcription_failed'


def test_runner_cwd_expands_home_and_os_failure_is_a_result(tmp_path, monkeypatch):
    from ai_os.tools import system_tools
    monkeypatch.setattr(system_tools, 'run_bounded', lambda argv, **kwargs: (
        (_ for _ in ()).throw(PermissionError('blocked test directory'))))
    result = system_tools.run_command(['pwd'], cwd=str(tmp_path))
    assert not result.ok and 'blocked test directory' in result.stderr
