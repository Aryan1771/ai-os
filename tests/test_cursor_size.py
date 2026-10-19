import json
from types import SimpleNamespace

import pytest

from ai_os import cursor_size


def test_cursor_apply_verifies_readback_and_preserves_original(tmp_path, monkeypatch):
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs['shell'] is False
        return SimpleNamespace(returncode=0, stdout='32' if len(calls) == 1 else '48')
    monkeypatch.setattr(cursor_size.subprocess, 'run', run)
    assert cursor_size.apply(48, tmp_path) == 48
    assert calls[1][-2:] == ['cursor-size', '48']
    backup = tmp_path/'backups/cursor-size.json'
    assert json.loads(backup.read_text())['previous'] == 32
    assert cursor_size.apply(48, tmp_path) == 48
    assert json.loads(backup.read_text())['previous'] == 32


def test_successful_exit_without_setting_change_is_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(cursor_size.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='32'))
    with pytest.raises(RuntimeError, match='still reports 32'):
        cursor_size.apply(48, tmp_path)
    assert not (tmp_path/'config.json').exists()
