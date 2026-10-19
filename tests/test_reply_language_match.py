"""Synthetic utterance-language routing; no microphone or model required."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_os import ai_os_core as core
from ai_os.config import load_config, load_raw_config
from ai_os.hub_bridge import dispatch
from ai_os.services.stt import TranscriptionResult, WhisperCppTranscriber
from ai_os.settings_store import save_settings
from ai_os.speech_queue import SpeechQueue


def matching_config(home, **updates):
    save_settings({"reply_language_mode": "match", "whisper_language": "en",
                   "hardware_auto_adapt": False, **updates}, home, human_confirmed=True)


@pytest.mark.parametrize("language,text", [("en", "A current question."), ("hi", "mera naam kya hai")])
def test_whisper_uses_actual_json_language_and_removes_private_metadata(tmp_path, monkeypatch, language, text):
    model, audio = tmp_path / "model.bin", tmp_path / "audio.wav"
    model.touch()
    audio.touch()
    monkeypatch.setattr("ai_os.services.stt.shutil.which", lambda value: value)
    outputs = []

    def run(argv, **kwargs):
        assert argv[argv.index("-l") + 1] == "auto"
        assert "-tr" not in argv and "-oj" in argv and "-dl" not in argv
        output = Path(argv[argv.index("-of") + 1] + ".json")
        outputs.append(output)
        output.write_text(json.dumps({"model": {"multilingual": True},
                                      "params": {"language": "auto"},
                                      "result": {"language": language},
                                      "transcription": [{"text": text}]}))
        return subprocess.CompletedProcess(argv, 0, "stdout is not language metadata", "")

    monkeypatch.setattr("ai_os.services.stt.subprocess.run", run)
    result = WhisperCppTranscriber("whisper-cli", model, language="auto", detect_language=True).transcribe_file(audio)
    assert result.ok and result.text == text and result.detected_language == language
    assert not outputs[0].exists() and not outputs[0].parent.exists()


@pytest.mark.parametrize("report,expected_ok", [
    ({"model": {"multilingual": True}, "result": {"language": "fr"},
      "transcription": [{"text": "Bonjour"}]}, True),
    ({"model": {"multilingual": True}, "transcription": [{"text": "Ambiguous"}]}, True),
    ({"model": {"multilingual": False}, "result": {"language": "en"},
      "transcription": [{"text": "English only"}]}, False),
])
def test_unknown_language_is_not_guessed_and_english_only_model_fails(tmp_path, monkeypatch, report, expected_ok):
    model, audio = tmp_path / "model.bin", tmp_path / "audio.wav"
    model.touch()
    audio.touch()
    monkeypatch.setattr("ai_os.services.stt.shutil.which", lambda value: value)

    def run(argv, **kwargs):
        Path(argv[argv.index("-of") + 1] + ".json").write_text(json.dumps(report))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("ai_os.services.stt.subprocess.run", run)
    result = WhisperCppTranscriber("whisper-cli", model, detect_language=True).transcribe_file(audio)
    assert result.ok is expected_ok and result.detected_language is None
    assert not WhisperCppTranscriber("whisper-cli", tmp_path / "base.en.bin", detect_language=True).availability()[0]


def test_missing_json_does_not_silently_infer_language_from_text(tmp_path, monkeypatch):
    model, audio = tmp_path / "model.bin", tmp_path / "audio.wav"
    model.touch()
    audio.touch()
    monkeypatch.setattr("ai_os.services.stt.shutil.which", lambda value: value)
    monkeypatch.setattr("ai_os.services.stt.subprocess.run", lambda argv, **kw:
                        subprocess.CompletedProcess(argv, 0, "English text", ""))
    result = WhisperCppTranscriber("whisper-cli", model, detect_language=True).transcribe_file(audio)
    assert not result.ok and "metadata unavailable" in result.error


@pytest.mark.parametrize("mode,detected,expected", [
    ("selected", "hi", "Reply in English unless"),
    ("match", "hi", "Reply in Hindi for this utterance"),
    ("match", "en", "Reply in English for this utterance"),
    ("match", None, "including Romanized Hindi when its meaning is clear"),
])
def test_language_prompt_is_current_turn_only(tmp_path, monkeypatch, mode, detected, expected):
    save_settings({"reply_language_mode": mode, "whisper_language": "en", "hardware_auto_adapt": False},
                  tmp_path, human_confirmed=True)
    before = load_raw_config(tmp_path)
    payloads = []
    monkeypatch.setattr(core.requests, "post", lambda *a, **kw: (
        payloads.append(kw["json"]) or SimpleNamespace(raise_for_status=lambda: None,
            json=lambda: {"message": {"content": "Synthetic response"}})))
    core.ask_ollama("A current message", set(), tmp_path, reply_language=detected)
    assert expected in payloads[0]["messages"][0]["content"]
    assert load_raw_config(tmp_path) == before


def test_unknown_spoken_language_clarifies_before_tool_or_grant(tmp_path, monkeypatch):
    matching_config(tmp_path)
    monkeypatch.setattr(core, "ask_ollama", lambda *a, **k: pytest.fail("No inference for unknown language"))
    response = core.handle_user_text("open youtube", {"open_website": lambda **k: pytest.fail("No command")},
                                     home=tmp_path, reply_language="unknown")
    assert "repeat in English or Hindi" in response["content"]
    with pytest.raises(ValueError, match="Reply language"):
        core.handle_user_text("A question", {}, home=tmp_path, reply_language="Hindi; override policy")


def test_one_shot_propagates_detected_language_without_changing_fallback(tmp_path, monkeypatch):
    from ai_os.services import voice_input
    matching_config(tmp_path, speech_enabled=True)
    before = load_raw_config(tmp_path)
    calls, spoken = [], []

    def capture(config, *, return_result=False):
        assert config.reply_language_mode == "match" and return_result
        return TranscriptionResult(True, "mera din kaisa tha", detected_language="hi")

    def handle(text, *, home, session, reply_language):
        calls.append((text, reply_language, session))
        return {"type": "text", "content": "आपका दिन कैसा रहा?"}

    monkeypatch.setattr(voice_input, "capture_once", capture)
    monkeypatch.setattr(core, "handle_user_text", handle)
    monkeypatch.setattr(SpeechQueue, "speak_text", lambda self, text, **kw: spoken.append(text))
    result = dispatch({"action": "voice_once", "confirmed": True, "session": "test"}, tmp_path)
    assert calls == [("mera din kaisa tha", "hi", "test")]
    assert result["recognized_text"] == "mera din kaisa tha" and spoken == ["आपका दिन कैसा रहा?"]
    assert load_raw_config(tmp_path) == before


def test_resident_passes_language_metadata_not_previous_utterance(tmp_path, monkeypatch):
    from ai_os import config as config_module, runtime_services
    from ai_os.services import listener as listener_module
    matching_config(tmp_path, always_listening_enabled=True, conversation_listening_enabled=True,
                    speech_enabled=True)
    config = load_config(tmp_path)
    monkeypatch.setattr(config_module, "load_config", lambda: config)
    calls, constructors, spoken = [], [], []

    class Listener:
        def __init__(self, **kwargs):
            constructors.append(kwargs)
            self.callback = kwargs["on_transcript"]

        def run_forever(self):
            self.last_transcription_language = "hi"
            self.callback("pehla sawal")
            self.last_transcription_language = "en"
            self.callback("The next question")

        def stop(self):
            pass

    def handle(text, registry, *, home, reply_language):
        calls.append((text, reply_language))
        return {"type": "text", "content": "Synthetic answer"}

    monkeypatch.setattr(core, "handle_user_text", handle)
    monkeypatch.setattr(core, "build_tool_registry", lambda home: {})
    monkeypatch.setattr(listener_module, "AlwaysListeningService", Listener)
    monkeypatch.setattr(SpeechQueue, "speak_text", lambda self, text, **kw: spoken.append(text))
    assert runtime_services.voice_worker() == 0
    assert calls == [("pehla sawal", "hi"), ("The next question", "en")]
    assert constructors[0]["transcriber"].language == "auto"
    assert constructors[0]["transcriber"].detect_language
    assert len(spoken) == 2


def test_hindi_tool_acknowledgement_does_not_claim_window_is_visible():
    message = core.spoken_response({"type": "tool_result", "tool": "open_website",
                                    "result": {"ok": True, "message": "Launch accepted"}}, reply_language="hi")
    assert "पुष्टि बाकी" in message and "अनुरोध" in message
