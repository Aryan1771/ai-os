"""Explicit native speaker enrollment: no recording until the Record button."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout,
)

from ai_os.config import AI_OS_HOME, load_raw_config
from ai_os.speaker_identity import (
    ENROLLMENT_SAMPLES, Enrollment, SpeakerError, backend_available,
    delete_profile, MAX_MODEL_BYTES,
)

PROMPTS = (
    ("Natural voice", "RE, please tell me what is on my schedule today."),
    ("Slightly quieter, still clear", "I would like to open the browser and play some music."),
    ("A little more expressive", "That is interesting! Can you explain what happens next?"),
    ("Your other language, or normal voice", "आज का दिन अच्छा है। मुझे अपने काम की तैयारी करनी है।\n"
     "Or: Today is a good day. I am getting ready for my work."),
    ("Verification — a fresh phrase", "RE, this is my voice. Please help me organize my computer."),
)
CAPTURE_SECONDS = 7
MAX_CAPTURE_BYTES = 16000 * 2 * (CAPTURE_SECONDS + 2)


class SpeakerSetupDialog(QDialog):
    """Embeddings stay in memory until explicit Save; raw recordings are deleted."""
    def __init__(self, home: Path = AI_OS_HOME, parent=None):
        super().__init__(parent)
        self.home = Path(home)
        self.enrollment = None
        self.process = None
        self.phase = "idle"
        self.raw = bytearray()
        self.output = bytearray()
        self.capture_failed = False
        self.temporary = None
        self.audio_path = None
        self.setWindowTitle("REgenOS — local voice enrollment")
        self.resize(680, 580)
        root = QVBoxLayout(self)
        intro = QLabel(
            "Teach the optional conversation filter to recognize your voice using four "
            "short samples and a separate verification sample. Speak in a quiet room. "
            "Use your normal voice; do not shout or strain. Read the phrase or say "
            "something of similar length in either language.\n\n"
            "This is NOT a fingerprint, login, identity proof, or command approval. "
            "A recording or another similar voice may pass. Privileged actions still "
            "need trusted human approval. No anti-replay guarantee.\n\n"
            "Audio is processed locally in a private temporary directory, then deleted. "
            "Only a voice embedding and model hash are saved. Embeddings are sensitive "
            "personal data. Nothing is uploaded or downloaded."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        self.consent = QCheckBox("I agree to record and store a local voice embedding for conversation filtering")
        self.consent.setChecked(False)
        root.addWidget(self.consent)
        self.progress = QProgressBar()
        self.progress.setRange(0, ENROLLMENT_SAMPLES + 1)
        root.addWidget(self.progress)
        self.prompt = QLabel()
        self.prompt.setWordWrap(True)
        self.prompt.setMinimumHeight(90)
        root.addWidget(self.prompt)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        buttons = QHBoxLayout()
        self.record_button = QPushButton("Record 7-second sample")
        self.record_button.clicked.connect(self.record)
        buttons.addWidget(self.record_button)
        self.retry_button = QPushButton("Start over")
        self.retry_button.clicked.connect(self.restart)
        buttons.addWidget(self.retry_button)
        self.save_button = QPushButton("Save voice profile")
        self.save_button.clicked.connect(self.save_profile)
        buttons.addWidget(self.save_button)
        root.addLayout(buttons)
        footer = QHBoxLayout()
        self.delete_button = QPushButton("Delete saved voice profile…")
        self.delete_button.clicked.connect(self.delete_saved_profile)
        footer.addWidget(self.delete_button)
        footer.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)
        root.addLayout(footer)
        self.consent.toggled.connect(self.update_controls)
        self.capture_timer = QTimer(self)
        self.capture_timer.setSingleShot(True)
        self.capture_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.capture_timer.timeout.connect(self.finish_capture)
        self.kill_timer = QTimer(self)
        self.kill_timer.setSingleShot(True)
        self.kill_timer.timeout.connect(self.kill_stuck_capture)
        self.worker_timer = QTimer(self)
        self.worker_timer.setSingleShot(True)
        self.worker_timer.timeout.connect(self.worker_timeout)
        self.restart()

    def restart(self):
        if self.process is not None:
            return
        self.enrollment = None
        self.progress.setValue(0)
        try:
            config = load_raw_config(self.home)
            if not config.get("speaker_model"):
                raise SpeakerError("Choose and save a local speaker embedding ONNX model in Voice settings first.")
            self.model = Path(config["speaker_model"]).expanduser()
            info = self.model.stat()
            if not self.model.is_file() or not 0 < info.st_size <= MAX_MODEL_BYTES:
                raise SpeakerError("Choose a valid local speaker ONNX model smaller than 1 GiB.")
            self.model_signature = self.signature()
            if not backend_available():
                raise SpeakerError("Optional sherpa-onnx / numpy backend is missing. Install it in the existing venv only; no automatic download is performed.")
            if not shutil.which("pw-record"):
                raise SpeakerError("PipeWire pw-record is missing; microphone enrollment cannot start.")
            self.enrollment = Enrollment("0" * 64, float(config.get("speaker_threshold", .75)))
            self.status.setText("Ready. Recording starts only when you press Record.")
        except (SpeakerError, OSError, ValueError, TypeError):
            self.status.setText("Setup unavailable. Choose a valid local speaker ONNX model, optional sherpa-onnx / numpy venv backend, and PipeWire recorder first. No sample has been recorded.")
        self.update_controls()

    def signature(self):
        info = self.model.stat()
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    def update_controls(self, *_):
        count = len(self.enrollment.samples) if self.enrollment else 0
        verified = bool(self.enrollment and self.enrollment.verified)
        self.progress.setValue(5 if verified else count)
        title, phrase = PROMPTS[min(count, 4)]
        self.prompt.setText(f"{min(count + 1, 5)} / 5 — {title}\n\n{phrase}" if not verified
                            else "Verification passed. Choose Save to retain only the private voice embedding.")
        busy = self.process is not None
        self.record_button.setEnabled(bool(self.enrollment and self.consent.isChecked() and not busy and not verified))
        self.retry_button.setEnabled(not busy)
        self.save_button.setEnabled(bool(verified and not busy and self.consent.isChecked()))
        self.delete_button.setEnabled(not busy)
        self.consent.setEnabled(not busy)

    def record(self):
        if not self.record_button.isEnabled():
            return
        self.raw.clear()
        self.capture_failed = False
        self.phase = "capture"
        self.temporary = tempfile.TemporaryDirectory(prefix="regenos-speaker-")
        os.chmod(self.temporary.name, 0o700)
        self.audio_path = Path(self.temporary.name) / "sample.wav"
        process = QProcess(self)
        self.process = process
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        process.readyReadStandardOutput.connect(self.read_process)
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.errorOccurred.connect(self.process_error)
        process.finished.connect(self.process_finished)
        self.status.setText("● Microphone recording — speak now. Recording stops in seven seconds. Cancel stops immediately.")
        process.start(shutil.which("pw-record") or "/usr/bin/pw-record",
                      ["--raw", "--format", "s16", "--rate", "16000", "--channels", "1", "-"])
        self.capture_timer.start(CAPTURE_SECONDS * 1000)
        self.update_controls()

    def read_process(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput())
        target = self.raw if self.phase in ("capture", "capture_stopping") else self.output
        limit = MAX_CAPTURE_BYTES if self.phase in ("capture", "capture_stopping") else 65536
        if len(target) + len(data) > limit:
            self.capture_failed = True
            self.process.kill()
            return
        target.extend(data)

    def finish_capture(self):
        if self.process is not None and self.phase == "capture":
            self.phase = "capture_stopping"
            self.process.terminate()
            self.kill_timer.start(1200)

    def kill_stuck_capture(self):
        if self.process is not None and self.phase == "capture_stopping":
            self.process.kill()

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.status.setText("The recorder or speaker worker could not start. No profile was changed.")
            self.cleanup()
            self.update_controls()

    def process_finished(self, code, _status):
        if self.process is None:
            return
        phase = self.phase
        # Capture bytes queued immediately before the stop signal.
        data = bytes(self.process.readAllStandardOutput())
        if phase in ("capture", "capture_stopping"):
            if len(self.raw) + len(data) <= MAX_CAPTURE_BYTES:
                self.raw.extend(data)
            else:
                self.capture_failed = True
        else:
            self.output.extend(data[:65537])
        old = self.process
        self.process = None
        old.deleteLater()
        self.capture_timer.stop()
        self.kill_timer.stop()
        self.worker_timer.stop()
        if phase in ("capture", "capture_stopping"):
            if phase != "capture_stopping" or self.capture_failed or not 32000 <= len(self.raw) <= MAX_CAPTURE_BYTES:
                self.status.setText("Microphone capture failed or ended too early. Check the input and retry.")
                self.cleanup()
                self.update_controls()
                return
            try:
                fd = os.open(self.audio_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as target:
                    with wave.open(target, "wb") as audio:
                        audio.setnchannels(1)
                        audio.setsampwidth(2)
                        audio.setframerate(16000)
                        audio.writeframes(self.raw[:len(self.raw) // 2 * 2])
                self.raw.clear()
                self.start_extraction()
            except (OSError, wave.Error):
                self.status.setText("The private temporary recording could not be created. Please retry.")
                self.cleanup()
                self.update_controls()
            return
        try:
            if code != 0 or self.capture_failed or len(self.output) > 65536:
                raise SpeakerError("The extraction worker failed.")
            result = json.loads(bytes(self.output))
            embedding = result["embedding"]
            digest = result["model_sha256"]
            if (not isinstance(digest, str) or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)
                    or self.signature() != self.model_signature):
                raise SpeakerError("The model changed during enrollment.")
            if not self.enrollment.samples:
                self.enrollment.digest = digest
            elif self.enrollment.digest != digest:
                raise SpeakerError("The model changed during enrollment.")
            if len(self.enrollment.samples) < ENROLLMENT_SAMPLES:
                self.enrollment.add(embedding)
                self.status.setText("Sample accepted and raw recording deleted. Continue with the next phrase.")
            elif self.enrollment.verify(embedding):
                self.status.setText("Fresh sample matched. Save is now available. Filtering stays off until explicitly enabled in Settings.")
            else:
                self.status.setText("Verification did not match. Retry this fresh phrase or start over; no profile was changed.")
        except (SpeakerError, OSError, ValueError, TypeError, KeyError):
            self.status.setText("Sample could not be verified. Check the local model, backend and microphone, then retry. No profile was changed.")
        finally:
            self.cleanup()
            self.update_controls()

    def start_extraction(self):
        self.phase = "extract"
        self.output.clear()
        process = QProcess(self)
        self.process = process
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("AI_OS_HOME", str(self.home))
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self.read_process)
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.errorOccurred.connect(self.process_error)
        process.finished.connect(self.process_finished)
        self.status.setText("Microphone off. Computing the local speaker embedding…")
        process.start(sys.executable, ["-m", "ai_os.speaker_identity", "--extract",
                                      str(self.model), str(self.audio_path)])
        self.worker_timer.start(30000)
        self.update_controls()

    def worker_timeout(self):
        if self.process is not None:
            self.capture_failed = True
            self.process.kill()

    def save_profile(self):
        if not self.save_button.isEnabled():
            return
        try:
            # Model changes during enrollment must never bind old embeddings to a new model.
            if self.signature() != self.model_signature:
                raise SpeakerError("The model changed during enrollment. Start over.")
            self.enrollment.save(self.home)
            self.cleanup()
            QMessageBox.information(self, "Voice profile saved", "Only the local voice embedding and model hash were saved. Enable speaker filtering separately in Voice settings. This never authorizes commands.")
            self.accept()
        except (SpeakerError, OSError):
            self.status.setText("The profile could not be saved. Check private storage permissions and unchanged model, then retry.")

    def delete_saved_profile(self):
        reply = QMessageBox.question(self, "Delete local voice profile?",
                                     "Delete the saved embedding? If speaker filtering is enabled, all voice requests will be blocked until you enroll again or disable the filter in Settings.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_profile(self.home)
            self.status.setText("Saved voice profile deleted. Filtering has not been silently disabled.")
        except SpeakerError:
            self.status.setText("Could not delete the profile. Check its storage permissions.")

    def cleanup(self):
        self.capture_timer.stop()
        self.kill_timer.stop()
        self.worker_timer.stop()
        if self.process is not None:
            process = self.process
            self.process = None
            process.blockSignals(True)
            process.kill()
            process.waitForFinished(1500)
            process.deleteLater()
        self.raw.clear()
        self.output.clear()
        if self.temporary is not None:
            self.temporary.cleanup()
            self.temporary = None
        self.audio_path = None
        self.phase = "idle"

    def done(self, result):
        self.cleanup()
        super().done(result)

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = SpeakerSetupDialog()
    dialog.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
