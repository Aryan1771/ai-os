import json
from types import SimpleNamespace

import pytest

from ai_os.config import load_raw_config
from ai_os.conversation_memory import ConversationMemory
from ai_os.device_context import DisplayTracker
from ai_os.settings_store import save_settings


def test_reinforcement_requires_opt_in_time_and_three_occurrences(tmp_path, monkeypatch):
    memory = ConversationMemory(tmp_path)
    clock = [1800000000.0]
    monkeypatch.setattr('ai_os.conversation_memory.time.time', lambda: clock[0])
    sentence = 'I prefer quiet mornings.'
    memory.append(sentence, 'A fictional assistant claim is not evidence')
    save_settings({'reinforced_memory_enabled': True}, tmp_path, human_confirmed=True)
    for _ in range(3):
        memory.append(sentence, 'response')
    assert memory.reinforced() == []  # Repeated requests in one window count once.
    for _ in range(2):
        clock[0] += 601
        memory.append(sentence.upper(), 'response')
    assert memory.reinforced()[0]['hits'] == 3
    with memory.connect() as db:
        db.execute('DELETE FROM turns')
    assert 'quiet mornings' in json.dumps(memory.context('quiet mornings')).lower()
    assert memory.reinforced('other') == []
    revision = memory.revision()
    memory.forget('quiet mornings')
    memory.append(sentence, 'late response', expected_revision=revision)
    assert memory.reinforced() == [] and memory.history() == []


def test_reinforced_records_decay_clear_and_filter_secrets(tmp_path, monkeypatch):
    save_settings({'reinforced_memory_enabled': True}, tmp_path, human_confirmed=True)
    memory = ConversationMemory(tmp_path)
    for i in range(3):
        monkeypatch.setattr('ai_os.conversation_memory.time.time', lambda i=i: 1800000000+i*601)
        memory.append('I enjoy building Linux tools', 'response')
        memory.append('password: synthetic-not-a-real-secret', 'response')
    assert len(memory.reinforced()) == 1
    monkeypatch.setattr('ai_os.conversation_memory.time.time', lambda: 1800000000+181*86400)
    assert memory.reinforced() == []
    memory.clear_all()
    with memory.connect() as db:
        assert db.execute('SELECT count(*) FROM reinforced').fetchone()[0] == 0


def test_language_choice_controls_prompt(tmp_path, monkeypatch):
    from ai_os import ai_os_core as core
    save_settings({'whisper_language': 'hi', 'hardware_auto_adapt': False}, tmp_path, human_confirmed=True)
    captured = []
    monkeypatch.setattr(core.requests, 'post', lambda *a, **kw: captured.append(kw['json']) or SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {'message': {'content': 'नमस्ते'}}))
    core.ask_ollama('hello', set(), tmp_path)
    assert 'Reply in Hindi' in captured[0]['messages'][0]['content']
    assert load_raw_config(tmp_path)['whisper_language'] == 'hi'


def display(root, name, mode):
    connector = root / name
    connector.mkdir(parents=True)
    (connector/'status').write_text('connected')
    (connector/'edid').write_bytes(b'')
    (connector/'modes').write_text(mode+'\n')
    return connector


def test_display_baseline_new_capability_and_reconnect(tmp_path):
    root = tmp_path/'drm'
    display(root, 'card0-eDP-1', '1920x1080')
    tracker = DisplayTracker(tmp_path, root)
    assert tracker.poll() == []  # Existing hardware isn't newly attached.
    connector = display(root, 'card0-HDMI-A-1', '3840x2160')
    notice = tracker.poll()[0]
    assert 'new monitor' in notice and 'supports 3840 by 2160' in notice
    assert 'more pixels' in notice
    assert tracker.poll() == []
    (connector/'status').write_text('disconnected')
    tracker.poll()
    (connector/'status').write_text('connected')
    assert 'back' in tracker.poll()[0]
    assert 'HDMI' not in tracker.path.read_text()


def test_non_speech_marker_never_reaches_conversation(tmp_path, monkeypatch):
    from ai_os.services.stt import WhisperCppTranscriber
    model = tmp_path/'model.bin'
    model.touch()
    audio = tmp_path/'sample.wav'
    audio.touch()
    monkeypatch.setattr('ai_os.services.stt.shutil.which', lambda name: name)
    monkeypatch.setattr('ai_os.services.stt.subprocess.run', lambda *a, **k: SimpleNamespace(
        returncode=0, stdout='[BLANK_AUDIO]', stderr=''))
    assert not WhisperCppTranscriber('whisper-cli', model).transcribe_file(audio).ok


def test_cursor_size_validation_and_output(tmp_path):
    from ai_os.cursor_theme import apply_preferences
    apply_preferences(tmp_path, None, size=64)
    assert 'XCURSOR_SIZE=64' in (tmp_path/'environment.d/60-regenos-cursor.conf').read_text()
    with pytest.raises(ValueError):
        apply_preferences(tmp_path, None, size=10000)


def test_speak_once_ends_on_utterance_and_reaps_recorder(tmp_path, monkeypatch):
    from ai_os.config import load_config
    from ai_os.services import voice_input
    stopped = []
    class Listener:
        def __init__(self, **kwargs):
            assert not kwargs['require_wake_word']
        def _read_audio(self, count):
            return b'\x01\x01' * (count//2)
        def has_speech(self, audio):
            return True
        def _capture_and_transcribe(self, preroll, count):
            assert len(preroll) == 3 * count
            return 'A synthetic sentence'
        def stop(self):
            stopped.append(True)
    monkeypatch.setattr(voice_input, 'AlwaysListeningService', Listener)
    monkeypatch.setattr(voice_input.WhisperCppTranscriber, 'availability', lambda _: (True, 'ready'))
    monkeypatch.setattr(voice_input.subprocess, 'Popen', lambda *a, **k: object())
    monkeypatch.setattr(voice_input, 'publish_state', lambda *a, **k: None)
    assert voice_input.capture_once(load_config(tmp_path)) == 'A synthetic sentence'
    assert stopped == [True]
