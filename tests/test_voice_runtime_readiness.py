"""Static voice readiness and visible failures, without microphone/model access."""
from collections import deque
import json
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace

import pytest

from ai_os import runtime_health
from ai_os.services import listener as listener_module
from ai_os.services import wakeword
from ai_os.services.listener import AlwaysListeningService
from ai_os.services.voice_errors import VoicePipelineError, diagnostic
from ai_os.settings_store import save_settings


@pytest.fixture
def wake_assets(tmp_path, monkeypatch):
    package = tmp_path / "openwakeword"
    resources = package / "resources" / "models"
    resources.mkdir(parents=True)
    (package / "__init__.py").touch()

    def find_spec(name):
        if name == "openwakeword":
            return SimpleNamespace(origin=str(package / "__init__.py"))
        if name == "onnxruntime":
            return SimpleNamespace(origin="synthetic-runtime")
        return None

    monkeypatch.setattr(wakeword.importlib.util, "find_spec", find_spec)
    return resources


def test_wake_readiness_identifies_missing_assets_without_import_or_download(wake_assets):
    status = wakeword.WakeWordService().local_configuration()
    assert not status["ready"] and "assets are missing" in status["message"]
    assert list(wake_assets.iterdir()) == []


def test_wake_default_uses_only_present_onnx_models_and_resets(wake_assets, monkeypatch):
    for name in ("melspectrogram", "embedding_model", "hey_jarvis_v0.1"):
        (wake_assets / (name + ".onnx")).touch()
    calls, resets = [], []
    module = ModuleType("openwakeword.model")
    module.Model = lambda **kwargs: (calls.append(kwargs) or SimpleNamespace(reset=lambda: resets.append(True)))
    monkeypatch.setitem(sys.modules, "openwakeword.model", module)
    service = wakeword.WakeWordService()
    assert service.availability()[0]
    assert service.start()[0]
    assert calls == [{"wakeword_models": [str(wake_assets / "hey_jarvis_v0.1.onnx")],
                      "inference_framework": "onnx"}]
    service.reset()
    assert resets == [True]


def test_optional_wake_load_error_is_safe_and_clears_stale_detector(tmp_path, monkeypatch):
    model = tmp_path / "wake.onnx"
    model.touch()
    private = "private local model path and backend debug output"

    def fail(**kwargs):
        raise ImportError(private)

    module = ModuleType("openwakeword.model")
    module.Model = fail
    monkeypatch.setitem(sys.modules, "openwakeword.model", module)
    service = wakeword.WakeWordService(model_path=str(model))
    service._model = object()
    ready, message = service.start()
    assert not ready and private not in message
    assert service._model is None
    with pytest.raises(RuntimeError, match="start"):
        service.detect_frame([1, 2])


def test_selected_tflite_model_does_not_pretend_onnx_runtime_is_compatible(wake_assets):
    model = wake_assets / "custom.tflite"
    model.touch()
    ready, message = wakeword.WakeWordService(model_path=str(model)).availability()
    assert not ready and "runtime" in message


@pytest.fixture
def health_home(tmp_path, monkeypatch):
    save_settings({"reply_language_mode": "match", "speech_enabled": True,
                   "whisper_model": "models/multilingual.bin", "whisper_language": "en"},
                  tmp_path, human_confirmed=True)
    models = tmp_path / "models"
    models.mkdir(exist_ok=True)
    for name in ("multilingual.bin", "en_US-lessac-medium.onnx", "en_US-lessac-medium.onnx.json"):
        (models / name).touch()
    monkeypatch.setattr(runtime_health.shutil, "which", lambda _: "/usr/bin/synthetic-installed-tool")

    def run(argv, **kwargs):
        assert kwargs["shell"] is False and kwargs["timeout"] == 2
        return subprocess.CompletedProcess(argv, 0, "active" if "systemctl" in argv[0] else "Volume: 1.00", "")

    monkeypatch.setattr(runtime_health.subprocess, "run", run)

    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs):
            assert kwargs["allow_redirects"] is False
            return SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"models": [{"name": "qwen2.5:7b-instruct-q4_K_M"}]})

    monkeypatch.setattr(runtime_health.requests, "Session", Session)
    return tmp_path


def test_matching_mode_reports_missing_hindi_assets_instead_of_ready(health_home):
    result = runtime_health.report(health_home)
    assert result["ok"]  # The inspection completed, distinct from readiness.
    assert result["transcriber_ready"]
    assert result["hindi_voice_required"] and not result["hindi_voice_model_present"]
    assert not result["voice_ready"] and not result["voice_assets_ready"]
    assert "hindi_voice_assets_missing" in result["voice_blockers"]
    assert result["voice_acceptance"].endswith("not_tested")


def test_unknown_or_private_status_text_is_never_reported(health_home):
    private = "private transcript and command arguments"
    (health_home / "run").mkdir(exist_ok=True)
    (health_home / "run/voice-status.json").write_text(json.dumps({
        "state": "error", "updated": time.time(), "last_error_code": "speech_failed", "last_error": private,
    }))
    result = runtime_health.report(health_home)
    assert result["last_voice_error_code"] == "speech_failed"
    assert "speech failed" in result["last_voice_error"].lower()
    assert private not in json.dumps(result)
    code, message = diagnostic(VoicePipelineError("speaker_rejected", private), "listening")
    assert code == "speaker_rejected" and private not in message


def test_resident_speaker_rejection_is_visible_rate_limited_and_keeps_listening(tmp_path, monkeypatch):
    voice = (2000).to_bytes(2, "little", signed=True) * 1280
    errors, captures, phases = [], [], []
    clock = [0.0]
    service = AlwaysListeningService(run_dir=tmp_path, transcriber=SimpleNamespace(),
                                    on_transcript=lambda _: pytest.fail("Rejected audio must not become a request"),
                                    require_wake_word=False, on_error=errors.append, on_activity=phases.append)
    frames = deque([voice] * 120)

    def read(_size):
        clock[0] += .08
        if not frames:
            service._stop.set()
            return voice
        return frames.popleft()

    def capture(*args):
        captures.append(True)
        service.last_capture_error = VoicePipelineError("speaker_rejected", "untrusted private reason")
        return ""

    monkeypatch.setattr(service, "availability", lambda: (True, "synthetic"))
    monkeypatch.setattr(service, "_read_audio", read)
    monkeypatch.setattr(service, "_capture_and_transcribe", capture)
    monkeypatch.setattr(service, "_discard_backlog", lambda: None)
    monkeypatch.setattr(listener_module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(listener_module.subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(stdout=object(), poll=lambda: 0))
    service.run_forever()
    assert len(captures) > 2 and len(errors) == 1
    assert phases.count("armed") > 2


def test_worker_rejection_persists_public_error_without_speaking(tmp_path, monkeypatch):
    from ai_os import config as config_module, runtime_services
    from ai_os.speech_queue import SpeechQueue

    save_settings({"always_listening_enabled": True, "conversation_listening_enabled": True},
                  tmp_path, human_confirmed=True)
    config = config_module.load_config(tmp_path)
    monkeypatch.setattr(config_module, "load_config", lambda: config)
    private = "private identity backend details"

    class SyntheticListener:
        def __init__(self, **kwargs):
            self.on_error = kwargs["on_error"]

        def run_forever(self):
            self.on_error(VoicePipelineError("speaker_unavailable", private))

        def stop(self):
            pass

    monkeypatch.setattr(listener_module, "AlwaysListeningService", SyntheticListener)
    monkeypatch.setattr(SpeechQueue, "speak_text", lambda *args, **kwargs: pytest.fail("No unsolicited error speech"))
    assert runtime_services.voice_worker() == 0
    status = json.loads((tmp_path / "run/voice-status.json").read_text())
    assert status["last_error_code"] == "speaker_unavailable"
    assert "verification unavailable" in status["last_error"]
    assert private not in json.dumps(status)
