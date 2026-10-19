"""Offscreen native wizard behavior, using fake processes and synthetic vectors."""
import json
import os

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
pytest.importorskip("PySide6")
from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QApplication, QMessageBox

from ai_os import speaker_setup as setup
from ai_os.speaker_identity import model_digest, profile_path


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["speaker-setup-test"])


@pytest.fixture
def ready(tmp_path, monkeypatch):
    model = tmp_path / "speaker.onnx"
    model.write_bytes(b"fake embedding model")
    (tmp_path / "config.json").write_text(json.dumps({"speaker_model":str(model)}))
    monkeypatch.setattr(setup, "backend_available", lambda: True)
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/usr/bin/pw-record")
    return model


def test_missing_model_and_backend_blocks_recording_without_creating_data(app, tmp_path):
    window = setup.SpeakerSetupDialog(tmp_path)
    window.consent.setChecked(True)
    assert not window.record_button.isEnabled()
    assert window.process is None
    assert not profile_path(tmp_path).exists()
    window.reject()


def test_explicit_consent_no_automatic_recording_and_cancel_preserves_profile(app, tmp_path, ready):
    window = setup.SpeakerSetupDialog(tmp_path)
    assert not window.record_button.isEnabled()
    assert window.process is None
    assert window.temporary is None
    window.consent.setChecked(True)
    assert window.record_button.isEnabled()
    assert not window.save_button.isEnabled()
    window.reject()
    assert not profile_path(tmp_path).exists()


def test_cancel_kills_worker_and_removes_private_temporary_audio(app, tmp_path, ready):
    import tempfile
    window = setup.SpeakerSetupDialog(tmp_path)
    window.temporary = tempfile.TemporaryDirectory(prefix="synthetic-speaker-", dir=tmp_path)
    from pathlib import Path
    directory = Path(window.temporary.name)
    (directory / "sample.wav").write_bytes(b"not actual audio")
    class FakeProcess:
        killed = False
        waited = False
        def blockSignals(self, block): assert block
        def kill(self): self.killed = True
        def waitForFinished(self, timeout):
            assert timeout <= 1500
            self.waited = True
        def deleteLater(self): pass
    process = FakeProcess()
    window.process = process
    window.raw.extend(b"private fake data")
    window.reject()
    assert process.killed and process.waited
    assert not directory.exists()
    assert not window.raw
    assert not profile_path(tmp_path).exists()


def test_four_samples_and_held_out_match_required_before_explicit_save(app, tmp_path, ready, monkeypatch):
    window = setup.SpeakerSetupDialog(tmp_path)
    window.consent.setChecked(True)
    sample = [1.0] + [0.0] * 31
    digest = model_digest(ready)
    class FakeProcess:
        def readAllStandardOutput(self): return QByteArray()
        def deleteLater(self): pass
    for i in range(5):
        window.phase = "extract"
        window.process = FakeProcess()
        window.output.extend(json.dumps({"embedding":sample,"model_sha256":digest}).encode())
        window.process_finished(0, None)
        assert not profile_path(tmp_path).exists()
        assert window.save_button.isEnabled() == (i == 4)
    monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
    window.save_profile()
    assert profile_path(tmp_path).exists()
    saved = json.loads((tmp_path / "config.json").read_text())
    assert not saved.get("speaker_recognition_enabled", False)
    assert not list(tmp_path.glob("regenos-speaker-*"))


def test_failed_held_out_sample_retries_without_adding_to_training(app, tmp_path, ready):
    window = setup.SpeakerSetupDialog(tmp_path)
    window.consent.setChecked(True)
    sample = [1.0] + [0.0] * 31
    for _ in range(4):
        window.enrollment.add(sample)
    window.enrollment.digest = model_digest(ready)
    class FakeProcess:
        def readAllStandardOutput(self): return QByteArray()
        def deleteLater(self): pass
    window.phase = "extract"
    window.process = FakeProcess()
    window.output.extend(json.dumps({"embedding":[0.0,1.0]+[0.0]*30,
                                     "model_sha256":model_digest(ready)}).encode())
    window.process_finished(0, None)
    assert len(window.enrollment.samples) == 4
    assert not window.save_button.isEnabled()
    assert window.record_button.isEnabled()
    assert not profile_path(tmp_path).exists()
    window.reject()


def test_model_change_during_enrollment_cannot_be_saved(app, tmp_path, ready):
    window = setup.SpeakerSetupDialog(tmp_path)
    window.consent.setChecked(True)
    for _ in range(4):
        window.enrollment.add([1.0]+[0.0]*31)
    window.enrollment.verify([1.0]+[0.0]*31)
    window.update_controls()
    ready.write_bytes(b"replaced with different model")
    window.save_profile()
    assert not profile_path(tmp_path).exists()
    window.reject()


def test_cancel_stops_real_nonrecording_child_and_cleans_up(app, tmp_path, ready):
    import sys
    from PySide6.QtCore import QProcess
    window = setup.SpeakerSetupDialog(tmp_path)
    child = QProcess(window)
    child.start(sys.executable, ["-c", "import time; time.sleep(30)"])
    assert child.waitForStarted(1500)
    window.process = child
    window.reject()
    assert child.state() == QProcess.ProcessState.NotRunning
    assert window.process is None


def test_capture_requires_click_and_is_private_and_time_bounded(app, tmp_path, ready, monkeypatch):
    from pathlib import Path
    from PySide6.QtCore import QProcess
    launches = []
    class CapturingProcess(QProcess):
        def start(self, program, arguments):
            launches.append((program, arguments))
    monkeypatch.setattr(setup, "QProcess", CapturingProcess)
    window = setup.SpeakerSetupDialog(tmp_path)
    assert not launches
    window.record()
    assert not launches  # explicit consent is mandatory even if method called
    window.consent.setChecked(True)
    window.record()
    assert len(launches) == 1
    assert launches[0][1] == ["--raw", "--format", "s16", "--rate", "16000", "--channels", "1", "-"]
    directory = Path(window.temporary.name)
    assert directory.stat().st_mode & 0o777 == 0o700
    assert window.capture_timer.isActive()
    assert 0 < window.capture_timer.remainingTime() <= 7100
    assert not window.consent.isEnabled()
    window.reject()
    assert not directory.exists()
    assert not window.capture_timer.isActive()
