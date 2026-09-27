from pathlib import Path
from types import SimpleNamespace
import json

import numpy as np
import pytest

from ai_os import ai_os_core as core
from ai_os.tools import ui_tools, desktop_tools
from ai_os.services.wakeword import ReWhisperWakeWord
from ai_os.services.stt import WhisperCppTranscriber
from scripts.apply_system_identity import apply


@pytest.mark.parametrize('text', ['RE', 'R E.', 'Hey R E!', 'ar ee', 'Hello Ary'])
def test_re_name(text):
    assert ReWhisperWakeWord.matches(text)


@pytest.mark.parametrize('text', ['restart computer', 'we are here', 'RE open terminal', 'Jarvis', ''])
def test_re_name_requires_isolated_call(text):
    assert not ReWhisperWakeWord.matches(text)


def test_wake_audio_cleanup_and_cooldown(tmp_path, monkeypatch):
    detector = ReWhisperWakeWord(WhisperCppTranscriber('whisper-cli', tmp_path/'model'), tmp_path)
    calls = []
    def transcribe(path):
        assert path.is_file()
        calls.append(path)
        return SimpleNamespace(ok=True, text='R E')
    monkeypatch.setattr(detector.transcriber, 'transcribe_file', transcribe)
    for _ in range(24):
        assert not detector.detect_frame(np.ones(1280, dtype=np.int16)*1000)
    assert detector.detect_frame(np.ones(1280, dtype=np.int16)*1000)
    assert not calls[0].exists()
    assert not detector.detect_frame(np.ones(1280, dtype=np.int16)*1000)
    assert len(calls) == 1


def test_wake_silence_never_transcribes(tmp_path, monkeypatch):
    detector = ReWhisperWakeWord(WhisperCppTranscriber('whisper-cli', tmp_path/'model'), tmp_path)
    monkeypatch.setattr(detector.transcriber, 'transcribe_file', lambda _: pytest.fail('silence'))
    for _ in range(50):
        assert not detector.detect_frame(np.zeros(1280, dtype=np.int16))


def test_identity_replaces_symlink_without_touching_upstream(tmp_path):
    upstream = tmp_path/'usr/lib/os-release'
    upstream.parent.mkdir(parents=True)
    upstream.write_text('NAME=Arch\n')
    (tmp_path/'etc').mkdir()
    target = tmp_path/'etc/os-release'
    target.symlink_to('../usr/lib/os-release')
    backup = apply(tmp_path, Path(__file__).resolve().parents[1])
    assert upstream.read_text() == 'NAME=Arch\n'
    assert not target.is_symlink()
    assert 'NAME="REgenOS"' in target.read_text()
    assert json.loads((backup/'manifest.json').read_text())['etc/os-release']['symlink'] == '../usr/lib/os-release'


@pytest.mark.parametrize('version,lua', [('0.54.0', False), ('0.56.2', True)])
def test_workspace_versioned_and_bounded(tmp_path, monkeypatch, version, lua):
    monkeypatch.setattr(ui_tools, 'require_hyprland', lambda _: (True, ''))
    calls = []
    def ctl(*args):
        calls.append(args)
        return {'ok': True, 'output': json.dumps({'version': version}) if args[-1] == 'version' else 'ok'}
    monkeypatch.setattr(ui_tools, '_hyprctl', ctl)
    assert ui_tools.switch_workspace(2, tmp_path)['ok']
    assert calls[-1] == ('dispatch', 'hl.dsp.focus({workspace=2})') if lua else calls[-1] == ('dispatch', 'workspace', '2')
    for invalid in ('2);os.execute("reboot")', True, -1, 21):
        with pytest.raises(ValueError):
            ui_tools.switch_workspace(invalid, tmp_path)


def test_hypr_opt_out_and_injection(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_tools, '_hyprctl', lambda *a: pytest.fail('opt out'))
    assert not ui_tools.list_windows(tmp_path)['ok']
    with pytest.raises(ValueError):
        ui_tools.focus_window('0x12;exec reboot', tmp_path)
    with pytest.raises(TypeError):
        core.build_tool_registry(tmp_path)['switch_workspace'](workspace=2, home=Path('/tmp'))


def test_command_discovery_rejects_options():
    for query in ('--help', 'network;reboot', '/tmp/manual'):
        with pytest.raises(ValueError):
            desktop_tools.find_commands(query)


def test_session_installer_is_idempotent_and_preserves_config(tmp_path):
    from scripts.install_user_session import install
    config = tmp_path / '.config/hypr/hyprland.lua'
    config.parent.mkdir(parents=True)
    config.write_text('-- personal configuration\n')
    repo = Path(__file__).resolve().parents[1]
    backup = install(tmp_path, repo)
    assert (backup/'.config/hypr/hyprland.lua').read_text() == '-- personal configuration\n'
    install(tmp_path, repo)
    assert config.read_text().count('require("regenos")') == 1
    assert config.read_text().startswith('-- personal configuration')
    startup = (tmp_path/'.config/autostart/regenos-session.desktop').read_text()
    assert 'NotShowIn=Hyprland;' in startup
    assert str(tmp_path) in startup


def test_session_environment_cleanup_and_start(monkeypatch):
    from ai_os import session_start
    calls = []
    monkeypatch.delenv('HYPRLAND_INSTANCE_SIGNATURE', raising=False)
    monkeypatch.setenv('DISPLAY', ':test')
    monkeypatch.setattr(session_start.subprocess, 'run', lambda args, **kw: calls.append(args))
    monkeypatch.setattr(session_start.os, 'execv', lambda *args: None)
    session_start.main()
    assert 'HYPRLAND_INSTANCE_SIGNATURE' in calls[0]
    assert 'DISPLAY' in calls[1]
    assert calls[-1][-2:] == ['restart', 'ai-os.service']


def test_discovery_falls_back_when_system_index_is_empty(tmp_path, monkeypatch):
    import subprocess
    directory = tmp_path/'man8'
    directory.mkdir()
    (directory/'nmcli.8.gz').touch()
    (directory/'reboot.8.gz').touch()
    monkeypatch.setattr(desktop_tools, 'MAN_ROOT', tmp_path)
    monkeypatch.setattr(desktop_tools.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess([],16,'','no index'))
    result = desktop_tools.find_commands('network')
    assert result['ok'] and 'nmcli' in result['text'] and 'reboot' not in result['text']
