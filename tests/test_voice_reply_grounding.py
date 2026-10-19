"""Synthetic utterance/reply routing; no microphone, model or playback required."""
import json
from types import SimpleNamespace

import pytest

from ai_os import ai_os_core as core
from ai_os.config import load_config
from ai_os.hub_bridge import dispatch
from ai_os.settings_store import save_settings
from ai_os.speech_lease import speech_lease
from ai_os.speech_queue import SpeechQueue


def test_chosen_language_and_current_message_override_old_language(tmp_path, monkeypatch):
    from ai_os.conversation_memory import ConversationMemory
    save_settings({"whisper_language": "en", "hardware_auto_adapt": False},
                  tmp_path, human_confirmed=True)
    ConversationMemory(tmp_path).append("पहले का प्रश्न", "पहले का उत्तर")
    payloads = []
    monkeypatch.setattr(core.requests, "post", lambda *a, **kw: (
        payloads.append(kw["json"]) or SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"message": {"content": "The current answer."}},
        )
    ))
    assert core.ask_ollama("A new English question.", set(), tmp_path) == "The current answer."
    messages = payloads[0]["messages"]
    assert messages[-1] == {"role": "user", "content": "A new English question."}
    assert "Reply in English" in messages[0]["content"]
    assert "takes priority over language in old conversation history" in messages[0]["content"]
    assert "do not answer an old question" in messages[0]["content"]


def test_queued_speech_blocks_listener_before_worker_starts_and_stop_discards_it():
    speech = SpeechQueue()
    speech.enqueue("This reply has not started playing.")
    speech.enqueue("Another queued sentence.")
    assert speech.is_speaking()
    speech.stop()
    assert not speech.is_speaking()
    assert speech._queue.empty() and speech._queue.unfinished_tasks == 0
    speech.enqueue("A stopped queue must not retain this.")
    assert not speech.is_speaking() and speech._queue.empty()


def test_voice_once_speaks_response_to_that_exact_utterance_and_session(tmp_path, monkeypatch):
    save_settings({"speech_enabled": True, "whisper_language": "en"},
                  tmp_path, human_confirmed=True)
    from ai_os.services import voice_input
    recognized = "This is a synthetic current English utterance."
    answer = "This reply belongs to that utterance."
    calls, spoken = [], []
    monkeypatch.setattr(voice_input, "capture_once", lambda config: recognized)

    def handle(text, *, home, session):
        calls.append((text, home, session))
        return {"type": "text", "content": answer, "avatar": {"shape": "heart"}}

    monkeypatch.setattr(core, "handle_user_text", handle)
    monkeypatch.setattr(SpeechQueue, "speak_text", lambda self, text, **kw: spoken.append((text, kw)))
    result = dispatch({"action": "voice_once", "confirmed": True, "session": "synthetic"}, tmp_path)
    assert calls == [(recognized, tmp_path, "synthetic")]
    assert result["recognized_text"] == recognized
    assert result["response"]["content"] == answer
    assert spoken == [(answer, {"avatar": {"shape": "heart"}})]


def test_voice_once_busy_does_not_capture_or_overwrite_other_speech(tmp_path, monkeypatch):
    from ai_os.companion_state import publish_state, read_state
    from ai_os.services import voice_input
    monkeypatch.setattr(voice_input, "capture_once", lambda _: pytest.fail("Busy microphone capture started"))
    publish_state("speaking", home=tmp_path)
    with speech_lease(tmp_path) as acquired:
        assert acquired
        with pytest.raises(RuntimeError, match="Another voice interaction"):
            dispatch({"action": "voice_once", "confirmed": True}, tmp_path)
    assert read_state(tmp_path)["phase"] == "speaking"


def test_speech_disabled_during_processing_stops_one_shot_output(tmp_path, monkeypatch):
    from ai_os.services import voice_input
    save_settings({"speech_enabled": True}, tmp_path, human_confirmed=True)
    monkeypatch.setattr(voice_input, "capture_once", lambda _: "A synthetic question.")

    def handle(*a, **kw):
        save_settings({"speech_enabled": False}, tmp_path, human_confirmed=True)
        return {"type": "text", "content": "A visible answer."}

    monkeypatch.setattr(core, "handle_user_text", handle)
    monkeypatch.setattr(SpeechQueue, "speak_text", lambda *a, **kw: pytest.fail("Speech was disabled"))
    assert dispatch({"action": "voice_once", "confirmed": True}, tmp_path)["response"]["content"] == "A visible answer."


def test_resident_voice_worker_routes_current_utterance_directly(tmp_path, monkeypatch):
    from ai_os import runtime_services
    from ai_os import config as config_module
    from ai_os.services import listener as listener_module
    save_settings({"always_listening_enabled": True, "conversation_listening_enabled": True,
                   "speech_enabled": True, "whisper_language": "en"}, tmp_path, human_confirmed=True)
    config = load_config(tmp_path)
    monkeypatch.setattr(config_module, "load_config", lambda: config)
    recognized = "Please answer this current synthetic utterance."
    calls, spoken, constructor = [], [], []

    def handle(text, registry, *, home):
        calls.append((text, home))
        # The whole inference→reply owns the speech turn, not just each sentence.
        with speech_lease(home) as acquired:
            assert not acquired
        return {"type": "text", "content": "The current answer. Another sentence."}

    class Listener:
        def __init__(self, **kwargs):
            constructor.append(kwargs)
            self.callback = kwargs["on_transcript"]

        def run_forever(self):
            self.callback(recognized)

        def stop(self):
            pass

    monkeypatch.setattr(core, "handle_user_text", handle)
    monkeypatch.setattr(core, "build_tool_registry", lambda home: {})
    monkeypatch.setattr(listener_module, "AlwaysListeningService", Listener)
    monkeypatch.setattr(SpeechQueue, "speak_text", lambda self, text, **kw: spoken.append(text))
    assert runtime_services.voice_worker() == 0
    assert calls == [(recognized, tmp_path)]
    assert spoken == ["The current answer.", "Another sentence."]
    assert constructor[0]["transcriber"].language == "en"
    assert constructor[0]["silence_seconds"] == config.voice_silence_seconds
    assert constructor[0]["max_utterance_seconds"] == config.voice_max_utterance_seconds
    assert json.loads((tmp_path / "run/voice-status.json").read_text())["state"] == "reply"
