import json
import subprocess
import wave

import pytest

from ai_os import ai_os_core as core
from ai_os.config import DEFAULT_CONFIG
from ai_os.conversation_memory import ConversationMemory
from ai_os.hub_bridge import dispatch, schema
from ai_os.settings_store import save_settings
from ai_os.speech_queue import SpeechQueue
from ai_os.tools.system_tools import assess_command


def test_schema_covers_every_setting():
    expected = {
        f"{key}.{nested}" if isinstance(value, dict) else key
        for key, value in DEFAULT_CONFIG.items()
        for nested in (value if isinstance(value, dict) else [None])
    }
    assert {field["key"] for field in schema()} == expected
    assert DEFAULT_CONFIG["theme"] == "graphite"


def test_bridge_settings_validation_and_stale_revision(tmp_path):
    loaded = dispatch({"action": "load"}, tmp_path)
    with pytest.raises(PermissionError):
        dispatch(
            {
                "action": "save",
                "revision": loaded["revision"],
                "changes": {"allow_external_apis": True},
            },
            tmp_path,
        )
    saved = dispatch(
        {"action": "save", "revision": loaded["revision"], "changes": {"piper_length_scale": 1.2}},
        tmp_path,
    )
    assert saved["config"]["piper_length_scale"] == 1.2
    with pytest.raises(ValueError, match="another process"):
        dispatch({"action": "save", "revision": loaded["revision"], "changes": {}}, tmp_path)
    with pytest.raises(ValueError):
        save_settings({"memory_retention_days": 0}, tmp_path)


def test_history_survives_restart_and_clear_preserves_notes(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("My name is Aryan", "Hello Aryan")
    memory.put("Project", "REgenOS uses a portable SSD.")
    reopened = ConversationMemory(tmp_path)
    context = reopened.context("Tell me about REgenOS")
    assert "portable SSD" in context[0]["content"]
    assert context[-2]["content"] == "My name is Aryan"
    reopened.clear_history()
    assert reopened.history() == []
    assert len(reopened.notes()) == 1


def test_note_import_validates_whole_batch(tmp_path):
    with pytest.raises(ValueError):
        dispatch(
            {
                "action": "import_notes",
                "confirmed": True,
                "notes": [{"title": "good", "body": "valid"}, {"title": "bad"}],
            },
            tmp_path,
        )
    assert ConversationMemory(tmp_path).notes() == []
    with pytest.raises(PermissionError):
        dispatch({"action": "clear_history"}, tmp_path)


def test_context_budget_retention_and_sessions(tmp_path):
    memory = ConversationMemory(tmp_path)
    for i in range(20):
        memory.append(str(i) * 1000, "answer" * 1000)
    memory.append("private", "different session", session="separate")
    result = memory.context("question", budget=4000)
    assert sum(len(item["content"]) for item in result) <= 4000
    assert "private" not in json.dumps(result)
    with memory.connect() as db:
        db.execute("UPDATE turns SET created=0")
    assert memory.history() == []


def test_recent_turn_is_not_lost_when_a_note_uses_part_of_the_budget(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.put("Project", "Project context " * 100)
    memory.append("My name is Aryan", "Long response " * 1000)
    messages = memory.context("Project", budget=1024)
    assert any("My name is Aryan" in message["content"] for message in messages)
    assert sum(len(message["content"]) for message in messages) <= 1024


def test_real_bridge_protocol(tmp_path):
    import os
    import sys

    env = os.environ | {"AI_OS_HOME": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-m", "ai_os.hub_bridge"],
        input=json.dumps({"action": "load"}),
        text=True,
        capture_output=True,
        env=env,
        timeout=15,
    )
    assert result.returncode == 0
    response = json.loads(result.stdout)
    assert response["ok"] and response["config"]["theme"] == "graphite"


def test_custom_wake_word_uses_selected_model(tmp_path, monkeypatch):
    import sys
    import types

    from ai_os.services.wakeword import WakeWordService

    model = tmp_path / "wake.onnx"
    model.touch()
    calls = []
    module = types.ModuleType("openwakeword.model")
    module.Model = lambda **kwargs: calls.append(kwargs) or object()
    monkeypatch.setitem(sys.modules, "openwakeword.model", module)
    ready, _ = WakeWordService(0.5, str(model)).start()
    assert ready
    assert calls == [{"wakeword_models": [str(model)], "inference_framework": "onnx"}]


def test_model_receives_history_and_memory_disable_is_respected(tmp_path, monkeypatch):
    memory = ConversationMemory(tmp_path)
    memory.append("My name is Aryan", "Hello Aryan")
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "Your name is Aryan"}}

    def post(*args, **kwargs):
        calls.append(kwargs["json"])
        return Response()

    monkeypatch.setattr(core.requests, "post", post)
    core.handle_user_text("What is my name?", {}, home=tmp_path)
    assert "My name is Aryan" in json.dumps(calls[0]["messages"])
    assert calls[0]["options"]["num_ctx"] == 4096
    save_settings({"memory_enabled": False}, tmp_path, human_confirmed=True)
    count = len(memory.history())
    core.handle_user_text("Another request", {}, home=tmp_path)
    assert len(calls[-1]["messages"]) == 2
    assert len(memory.history()) == count


@pytest.mark.parametrize(
    "command",
    [
        ["awk", 'BEGIN {system("reboot")}'],
        ["sed", "-i", "s/a/b/", "file"],
        ["find", ".", "-delete"],
        ["ip", "link", "set", "lo", "down"],
        ["pacman", "-Q", "--dbpath", "/tmp/db"],
        ["/tmp/uname", "-a"],
        ["nvidia-smi", "-pl", "50"],
        ["rg", "--pre", "evil", "word"],
    ],
)
def test_command_arguments_cannot_bypass_consent(command):
    assert assess_command(command).requires_approval


def test_piper_uses_wav_rate_and_temporary_audio_is_removed(tmp_path, monkeypatch):
    model = tmp_path / "voice.onnx"
    model.touch()
    monkeypatch.setattr("ai_os.speech_queue.shutil.which", lambda name: name)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "piper":
            path = argv[argv.index("--output_file") + 1]
            with wave.open(path, "wb") as wav:
                wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\0\0" * 480)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr("ai_os.speech_queue.subprocess.run", run)
    SpeechQueue(model, length_scale=1.25).speak_text("Hello")
    assert calls[0][-1] == "1.25"
    assert calls[1][0] == "pw-play" and "--rate" not in calls[1]
    from pathlib import Path

    assert not Path(calls[1][1]).exists()


def test_speech_worker_reports_failure_without_dying(monkeypatch):
    events = []
    speech = SpeechQueue(on_activity=lambda *event: events.append(event))

    def fail(_text):
        speech.stop()
        raise RuntimeError("Playback unavailable")

    monkeypatch.setattr(speech, "speak_text", fail)
    speech.enqueue("Hello")
    speech.run_forever()
    assert events[-1][0] == "error"
    assert not speech.is_speaking()
    assert speech.last_error == "Playback unavailable"
