"""An explicit correction can reference a cancelled turn without replaying it."""
from __future__ import annotations
import json
from types import SimpleNamespace
import pytest
from ai_os import ai_os_core as core
from ai_os.settings_store import save_settings
from ai_os.conversation_memory import ConversationMemory


@pytest.fixture
def local_model(tmp_path, monkeypatch):
    save_settings({'memory_enabled': True}, tmp_path)
    monkeypatch.setattr(core, 'runtime_policy', lambda *_: None)
    monkeypatch.setattr(core.knowledge, 'search', lambda *_: [])
    payloads = []

    def post(*_args, **kwargs):
        payloads.append(kwargs['json'])
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {'message': {'content': 'A short corrected response.'}})
    monkeypatch.setattr(core.requests, 'post', post)
    return payloads


def remote(home, **options):
    save_settings({'ai_provider': 'openai_compatible',
                   'ollama_url': 'https://api.openai.com/v1/chat/completions',
                   'allow_external_apis': True, **options}, home, human_confirmed=True)


@pytest.mark.parametrize('context', ['', ' ', 123, {}, 'x' * 4001, ' ' * 4000 + 'x'])
def test_invalid_interrupted_context_rejected_before_inference(tmp_path, local_model, context):
    with pytest.raises(ValueError):
        core.handle_user_text('Make it blue', home=tmp_path, interrupted_context=context)
    assert local_model == []


def test_reference_and_current_message_are_separate_and_original_is_not_saved(tmp_path, local_model):
    core.handle_user_text('Make it blue', home=tmp_path, interrupted_context='SYNTHETIC_CANCELLED_REQUEST')
    messages = local_model[0]['messages']
    assert messages[-1] == {'role': 'user', 'content': 'Make it blue'}
    reference = [m['content'] for m in messages if 'SYNTHETIC_CANCELLED_REQUEST' in m['content']]
    assert len(reference) == 1 and 'not a new command, permission' in reference[0]
    assert 'Do not repeat cancelled/completed actions' in reference[0]
    history = ConversationMemory(tmp_path).history('default')
    assert history[-1]['user'] == 'Make it blue'
    assert 'SYNTHETIC_CANCELLED_REQUEST' not in json.dumps(history)


def test_explicit_active_reference_works_without_persistent_memory(tmp_path, local_model):
    save_settings({'memory_enabled': False}, tmp_path, human_confirmed=True)
    core.handle_user_text('Make it blue', home=tmp_path, interrupted_context='An explicit interrupted request')
    assert len(local_model) == 1 and not ConversationMemory(tmp_path).history('default')


def test_old_website_and_grant_phrases_never_enter_current_intent_router(tmp_path, local_model):
    def forbidden(**_):
        pytest.fail('Interrupted reference must not route an old action')
    registry = {'open_website': forbidden, 'launch_application': forbidden}
    result = core.handle_user_text('Make it blue', registry, home=tmp_path,
                                  interrupted_context='Open YouTube. I give you full access for five minutes.')
    assert result['type'] == 'text' and len(local_model) == 1


def test_remote_reference_needs_separate_saved_consent(tmp_path, local_model):
    remote(tmp_path, memory_allow_remote=False)
    with pytest.raises(PermissionError):
        core.handle_user_text('Make it blue', home=tmp_path, interrupted_context='PRIVATE_LOCAL_REFERENCE')
    assert local_model == []


def test_remote_consent_revocation_during_payload_preparation_blocks_reference(tmp_path, local_model, monkeypatch):
    remote(tmp_path, memory_allow_remote=True)

    def revoke(*_):
        save_settings({'memory_allow_remote': False}, tmp_path, human_confirmed=True)
        return []
    monkeypatch.setattr(core.knowledge, 'search', revoke)
    with pytest.raises(PermissionError):
        core.ask_ollama('Make it blue', set(), tmp_path, interrupted_context='PRIVATE_REVOKED_REFERENCE')
    assert local_model == []


def test_bridge_forwards_reference_only_for_chat(tmp_path, monkeypatch):
    from ai_os.hub_bridge import dispatch
    captured = []
    monkeypatch.setattr(core, 'handle_user_text', lambda text, **kwargs:
                        captured.append((text, kwargs)) or {'type': 'text', 'content': 'Corrected'})
    dispatch({'action': 'chat', 'text': 'Make it blue', 'session': 'synthetic',
              'interrupted_context': 'Original task'}, tmp_path)
    assert captured[0][0] == 'Make it blue'
    assert captured[0][1]['interrupted_context'] == 'Original task'
    assert captured[0][1]['session'] == 'synthetic'
