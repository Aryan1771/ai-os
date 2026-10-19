"""Voice settings migration and native request budgets, without microphone I/O."""

import json
import os
from pathlib import Path

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
pytest.importorskip("PySide6")
from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import QApplication

from ai_os.config import atomic_json, load_config, load_raw_config
from ai_os.conversation_widget import ConversationWidget
from ai_os.native_settings import SettingsWindow
from ai_os.settings_store import save_settings


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["regenos-voice-settings-test"])


class InertProcess:
    """Record the Qt child protocol without starting a backend or audio process."""

    def __init__(self, home):
        self.environment = QProcessEnvironment()
        self.environment.insert("AI_OS_HOME", str(home))
        self.requests = []
        self.launches = []

    def state(self):
        return QProcess.ProcessState.NotRunning

    def processEnvironment(self):
        return QProcessEnvironment(self.environment)

    def setProcessEnvironment(self, environment):
        self.environment = QProcessEnvironment(environment)

    def start(self, program, arguments):
        self.launches.append((program, arguments))

    def write(self, payload):
        self.requests.append(json.loads(payload))
        return len(payload)

    def closeWriteChannel(self):
        pass

    def blockSignals(self, _block):
        pass

    def deleteLater(self):
        pass

    def readAllStandardOutput(self):
        return b'{"ok": true, "response": {"type": "text", "content": "Synthetic response"}}'

    def readAllStandardError(self):
        return b""


@pytest.fixture
def conversation(app, tmp_path):
    widget = ConversationWidget(tmp_path)
    widget.process = InertProcess(tmp_path)
    yield widget
    widget.cancel()
    widget.grant_timer.stop()
    widget.close()


def test_old_configuration_gets_endpoint_defaults_without_enabling_listening(tmp_path):
    atomic_json(tmp_path / "config.json", {"whisper_language": "hi", "voice_command_seconds": 8})
    loaded = load_config(tmp_path)
    assert loaded.voice_silence_seconds == 5
    assert loaded.voice_max_utterance_seconds == 120
    assert loaded.voice_command_seconds == 8
    assert loaded.whisper_language == "hi"
    assert not loaded.always_listening_enabled
    assert not loaded.speech_enabled


@pytest.mark.parametrize("silence,maximum,expected", [(0, 0, (1, 10)), (50, 500, (10, 120))])
def test_hand_edited_numeric_configuration_has_bounded_runtime_values(tmp_path, silence, maximum, expected):
    atomic_json(tmp_path / "config.json", {
        "voice_silence_seconds": silence, "voice_max_utterance_seconds": maximum,
    })
    loaded = load_config(tmp_path)
    assert (loaded.voice_silence_seconds, loaded.voice_max_utterance_seconds) == expected


@pytest.mark.parametrize("key,value", [
    ("voice_silence_seconds", 0), ("voice_silence_seconds", 11),
    ("voice_silence_seconds", 2.5), ("voice_silence_seconds", True),
    ("voice_max_utterance_seconds", 9), ("voice_max_utterance_seconds", 121),
    ("voice_max_utterance_seconds", float("nan")),
])
def test_settings_reject_invalid_endpoint_values_without_saving(tmp_path, key, value):
    before = load_raw_config(tmp_path)
    with pytest.raises(ValueError):
        save_settings({key: value}, tmp_path)
    assert load_raw_config(tmp_path) == before


def test_native_voice_controls_persist_endpoint_preferences(app, tmp_path):
    window = SettingsWindow(tmp_path, launch_companion=False)
    try:
        window.fields["voice_silence_seconds"].setValue(7)
        window.fields["voice_max_utterance_seconds"].setValue(90)
        assert window.save()
        loaded = load_config(tmp_path)
        assert (loaded.voice_silence_seconds, loaded.voice_max_utterance_seconds) == (7, 90)
        assert not loaded.always_listening_enabled
    finally:
        window.poll.stop()
        window.access_poll.stop()
        window.conversation.grant_timer.stop()
        window.saved = window.collect()
        window.close()


def test_long_voice_request_has_budget_for_capture_transcription_reply_and_playback(conversation):
    save_settings({"voice_command_seconds": 30, "voice_max_utterance_seconds": 120}, conversation.home)
    conversation.speak_once()
    assert conversation.process.requests[-1]["action"] == "voice_once"
    assert conversation.timer.isActive()
    assert conversation.timer.interval() == (30 + 120 + 120 + 120 + 90) * 1000
    assert conversation.timer.remainingTime() > (30 + 120 + 120 + 120) * 1000
    assert conversation.timer.interval() <= 600_000
    temporary_path = Path(conversation.process.environment.value("AI_OS_VOICE_TMP"))
    assert temporary_path.is_dir()
    conversation.finished(0, QProcess.ExitStatus.NormalExit)
    assert not temporary_path.exists()


def test_typed_message_after_voice_completion_restores_normal_timeout(conversation):
    conversation.speak_once()
    assert conversation.timer.interval() > 150_000
    conversation.finished(0, QProcess.ExitStatus.NormalExit)
    conversation.input.setPlainText("A synthetic typed request")
    conversation.send()
    assert conversation.process.requests[-1]["action"] == "chat"
    assert conversation.timer.interval() == 150_000
    assert conversation.timer.isActive()
    assert not conversation.process.environment.contains("AI_OS_VOICE_TMP")
