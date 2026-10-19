"""Speaker setup regressions using synthetic vectors, never microphone recordings."""
import json
import os

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
pytest.importorskip("PySide6")
from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QApplication

from ai_os import speaker_setup as setup
from ai_os.speaker_identity import model_digest, profile_path


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["speaker-verification-regression"])


@pytest.fixture
def wizard(tmp_path, monkeypatch, app):
    model = tmp_path / "speaker.onnx"
    model.write_bytes(b"synthetic model identity; no inference")
    (tmp_path / "config.json").write_text(json.dumps({"speaker_model": str(model)}))
    monkeypatch.setattr(setup, "backend_available", lambda: True)
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/usr/bin/pw-record")
    window = setup.SpeakerSetupDialog(tmp_path)
    window.consent.setChecked(True)
    yield window, model
    window.reject()


def _complete(window, model, embedding, *, code=0, payload=None):
    class FakeProcess:
        def readAllStandardOutput(self):
            return QByteArray()

        def deleteLater(self):
            pass

    result = payload if payload is not None else {
        "embedding": embedding,
        "model_sha256": model_digest(model),
    }
    window.phase = "extract"
    window.process = FakeProcess()
    window.output.extend(json.dumps(result).encode())
    window.process_finished(code, None)


def _vector(index=0):
    return [1.0 if i == index else 0.0 for i in range(512)]


def test_real_model_dimension_accepts_four_samples_and_separate_fifth(wizard, tmp_path):
    window, model = wizard
    for count in range(5):
        _complete(window, model, _vector())
        assert len(window.enrollment.samples) == min(count + 1, 4)
        assert window.enrollment.verified == (count == 4)
        assert window.save_button.isEnabled() == (count == 4)
        assert not profile_path(tmp_path).exists()


def test_inconsistent_training_sample_reports_voice_difference_and_keeps_previous(wizard):
    window, model = wizard
    _complete(window, model, _vector())
    _complete(window, model, _vector(1))
    assert len(window.enrollment.samples) == 1
    assert not window.enrollment.verified
    assert "differs" in window.status.text().lower()
    assert "backend" not in window.status.text().lower()
    assert window.record_button.isEnabled()
    assert not window.save_button.isEnabled()


def test_fifth_nonmatch_is_retryable_without_backend_blame(wizard):
    window, model = wizard
    for _ in range(4):
        _complete(window, model, _vector())
    _complete(window, model, _vector(1))
    assert len(window.enrollment.samples) == 4
    assert not window.enrollment.verified
    assert "did not match" in window.status.text().lower()
    assert "backend" not in window.status.text().lower()
    assert window.record_button.isEnabled()
    _complete(window, model, _vector())
    assert window.enrollment.verified
    assert window.save_button.isEnabled()


def test_changed_model_reports_identity_problem_and_never_saves(wizard, tmp_path):
    window, model = wizard
    _complete(window, model, _vector())
    model.write_bytes(b"different synthetic model")
    _complete(window, model, _vector())
    assert len(window.enrollment.samples) == 1
    assert "model changed" in window.status.text().lower()
    assert not window.save_button.isEnabled()
    assert not profile_path(tmp_path).exists()


def test_malformed_worker_payload_never_echoes_private_text(wizard, tmp_path):
    window, model = wizard
    private = "private transcript or private filesystem path"
    _complete(window, model, None, payload={"error": private})
    assert not window.enrollment.samples
    assert private not in window.status.text()
    assert not window.save_button.isEnabled()
    assert not profile_path(tmp_path).exists()


def test_worker_clipping_reason_is_actionable_without_leaking_output(wizard):
    window, model = wizard
    _complete(window, model, _vector())
    _complete(window, model, None, code=1, payload={"code": "audio_clipping", "error": "private native log"})
    assert "clipping" in window.status.text()
    assert "private native log" not in window.status.text()
    assert len(window.enrollment.samples) == 1
    assert "1 / 4" in window.accepted_status.text()


def test_extract_worker_emits_only_allowlisted_safe_error(monkeypatch, capsys):
    from ai_os import speaker_identity as identity
    import sys
    monkeypatch.setattr(sys, "argv", ["speaker_identity", "--extract", "unused", "unused"])
    def fail(*args):
        raise identity.SpeakerError(identity.EXTRACTION_ERRORS["audio_clipping"])
    monkeypatch.setattr(identity, "encoder_for", fail)
    assert identity.main() == 1
    assert json.loads(capsys.readouterr().out)["code"] == "audio_clipping"
    def private_fail(*args):
        raise OSError("secret private paths or raw log")
    monkeypatch.setattr(identity, "encoder_for", private_fail)
    assert identity.main() == 1
    output = capsys.readouterr().out
    assert "secret private" not in output and json.loads(output)["code"] == "extraction_failed"
