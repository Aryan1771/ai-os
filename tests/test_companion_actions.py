import json

import pytest

from ai_os import reviewed_actions as actions, ai_os_core as core
from ai_os.hub_bridge import dispatch
from ai_os.settings_store import save_settings
from ai_os.speech_queue import emotional_pace


def test_bash_check_never_executes_source_or_environment(tmp_path, monkeypatch):
    marker = tmp_path/'must-not-exist'
    monkeypatch.setenv('BASH_ENV', str(tmp_path/'injected'))
    (tmp_path/'injected').write_text(f'touch {marker}\n')
    assert actions.check_bash(f'touch {marker}\necho "$(touch {marker})"')['ok']
    assert not marker.exists()
    assert not actions.check_bash('if then')['ok']


def test_bash_save_requires_confirmation_and_never_overwrites(tmp_path):
    args = {'name':'example.sh','source':'#!/bin/bash\necho hello\n'}
    with pytest.raises(PermissionError):
        actions.execute('write_bash',args,tmp_path)
    result = actions.execute('write_bash',args,tmp_path,confirmed=True)
    from pathlib import Path
    path = Path(result['path'])
    assert path.read_text() == args['source']
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        actions.execute('write_bash',args,tmp_path,confirmed=True)
    for name in ('../evil.sh','/etc/evil.sh','x.sh;reboot'):
        with pytest.raises(ValueError):
            actions.propose('write_bash',args | {'name':name})


@pytest.mark.parametrize('url',['file:///etc/passwd','http://example.com','https://a:b@example.com','https://example.com:22/'])
def test_research_requires_public_https_shape(url):
    with pytest.raises(ValueError):
        actions.propose('research_page', {'url':url})


def test_public_host_rejects_mixed_private_dns(monkeypatch):
    monkeypatch.setattr(actions.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443)),(2,1,6,'',('127.0.0.1',443))])
    assert not actions.public_host('example.com')


def test_browser_cannot_be_approved_by_model_or_timed_command_grant(tmp_path, monkeypatch):
    monkeypatch.setattr(actions,'browser_action',lambda *a,**k:pytest.fail('Must not browse'))
    proposal = core.execute_tool('ask_chatgpt',{'prompt':'hello','approve':True},core.build_tool_registry(tmp_path),home=tmp_path)
    assert proposal['approval_required']['arguments'] == {'prompt':'hello'}
    with pytest.raises(PermissionError):
        dispatch({'action':'reviewed_action','tool':'ask_chatgpt','arguments':{'prompt':'hello'}},tmp_path)
    with pytest.raises(TypeError):
        core.build_tool_registry(tmp_path)['ask_chatgpt'](prompt='hello',confirmed=True)


def test_proactive_disabled_has_no_inference(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'ask_ollama',lambda *a,**k:pytest.fail('disabled'))
    with pytest.raises(PermissionError):
        dispatch({'action':'proactive_speech'},tmp_path)


def test_proactive_model_tool_request_is_never_executed(tmp_path,monkeypatch):
    save_settings({'proactive_speech_enabled':True,'speech_enabled':True},tmp_path,human_confirmed=True)
    monkeypatch.setattr(core,'ask_ollama',lambda *a,**k:json.dumps({'tool':'run_command','arguments':{'command':['reboot']}}))
    with pytest.raises(ValueError,match='tool'):
        dispatch({'action':'proactive_speech'},tmp_path)


def test_emotional_pace_stays_bounded_and_concern_slows():
    assert emotional_pace(1, {'emotions':{'concern':100,'energy':0}}) > emotional_pace(1, {'emotions':{'energy':100}})
    assert 0.5 <= emotional_pace(2,{'emotions':{'concern':999}}) <= 2


def test_reviewed_browser_disabled_even_with_confirmation(tmp_path):
    with pytest.raises(PermissionError):
        actions.execute('ask_chatgpt',{'prompt':'hello'},tmp_path,confirmed=True)


def test_proactive_can_speak_while_waiting_for_wake_but_not_recording(tmp_path,monkeypatch):
    from ai_os.companion_state import publish_state
    from ai_os.speech_queue import SpeechQueue
    save_settings({'proactive_speech_enabled':True,'speech_enabled':True},tmp_path,human_confirmed=True)
    monkeypatch.setattr(core,'ask_ollama',lambda *a,**k:'{"reply":"Ready if you need help.","avatar":{"emotions":{"calm":90}}}')
    spoken=[]
    monkeypatch.setattr(SpeechQueue,'speak_text',lambda self,text,**kwargs:spoken.append(text))
    publish_state('listening',home=tmp_path)
    with pytest.raises(PermissionError):
        dispatch({'action':'proactive_speech'},tmp_path)
    assert not spoken
    publish_state('armed',home=tmp_path)
    dispatch({'action':'proactive_speech'},tmp_path)
    assert spoken == ['Ready if you need help.']
