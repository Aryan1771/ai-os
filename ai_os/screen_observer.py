"""Native Wayland/X11 screen reader, launched and owned by the companion.

Frames -> bounded Tesseract stdin -> expiring in-memory observation. The portal
owns monitor selection. This never reads the microphone or stores captured data.
"""
from __future__ import annotations

import json
import os
import signal
import shutil
import sys
import time

from PySide6.QtCore import QBuffer, QIODevice, QProcess, QProcessEnvironment, QTimer, Qt
from PySide6.QtDBus import QDBus, QDBusConnection, QDBusMessage
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ai_os.config import AI_OS_HOME, load_raw_config
from ai_os.native_widgets import LocalInstance
from ai_os.screen_context import Observation, socket_path, same_scene
from ai_os.settings_store import save_settings


def desktop_state():
    """GNOME session only for now. Unknown lock state fails closed; no keylogging."""
    bus = QDBusConnection.sessionBus()
    lock = QDBusMessage.createMethodCall("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver",
                                        "org.gnome.ScreenSaver", "GetActive")
    reply = bus.call(lock, QDBus.CallMode.Block, 250)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage or reply.arguments() != [False]:
        return False, False
    idle = QDBusMessage.createMethodCall("org.gnome.Mutter.IdleMonitor", "/org/gnome/Mutter/IdleMonitor/Core",
                                        "org.gnome.Mutter.IdleMonitor", "GetIdletime")
    reply = bus.call(idle, QDBus.CallMode.Block, 250)
    args = reply.arguments()
    active = reply.type() != QDBusMessage.MessageType.ErrorMessage and args and type(args[0]) is int and args[0] < 120_000
    return True, bool(active)


def stop_process(process):
    if process.state() == QProcess.ProcessState.NotRunning:
        return
    pid = process.processId()
    if sys.platform == "linux" and pid > 0:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    process.terminate()
    if not process.waitForFinished(500):
        if sys.platform == "linux" and pid > 0:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.kill()
        process.waitForFinished(500)


class ScreenObserver(QWidget):
    def __init__(self, home=AI_OS_HOME):
        super().__init__(None, Qt.WindowType.WindowStaysOnTopHint)
        self.home = home
        self.observation = Observation()
        self.capture = self.session = self.sink = None
        self.capture_ready = False
        self.lock_safe = False
        self.active_user = False
        self.last_frame = 0.0
        self.last_comment = ""
        self.next_comment = time.monotonic() + 30
        self.shutting_down = False
        self.ocr_valid = False
        self.setWindowTitle("RE · Screen awareness")
        self.setMinimumWidth(340)
        self.setMaximumWidth(500)
        layout = QVBoxLayout(self)
        self.status = QLabel("Screen sharing paused")
        self.status.setWordWrap(True)
        self.comment = QLabel("")
        self.comment.setWordWrap(True)
        self.comment.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        layout.addWidget(self.comment)
        controls = QHBoxLayout()
        resume = QPushButton("Resume / select screen")
        resume.clicked.connect(self.start_capture)
        pause = QPushButton("Pause")
        pause.clicked.connect(self.pause)
        describe = QPushButton("Ask RE")
        describe.clicked.connect(lambda: self.request_comment(automatic=False))
        for button in (resume, pause, describe):
            controls.addWidget(button)
        layout.addLayout(controls)
        self.ocr = self.process()
        self.ocr.finished.connect(self.ocr_finished)
        self.ocr.errorOccurred.connect(lambda _error: self.ocr_failed())
        self.ocr_timeout = QTimer(self)
        self.ocr_timeout.setSingleShot(True)
        self.ocr_timeout.timeout.connect(self.ocr_failed)
        self.commenter = self.process()
        self.commenter.finished.connect(self.comment_finished)
        self.comment_timeout = QTimer(self)
        self.comment_timeout.setSingleShot(True)
        self.comment_timeout.timeout.connect(lambda: stop_process(self.commenter))
        self.commenter.errorOccurred.connect(lambda _error: self.comment.setText("Comment unavailable"))
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.serve)
        path = socket_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        QLocalServer.removeServer(str(path))  # main's per-runtime LocalInstance is held.
        if not self.server.listen(str(path)):
            raise RuntimeError("Screen context socket unavailable")
        path.chmod(0o600)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(1000)
        QTimer.singleShot(0, self.start_capture)

    def process(self):
        process = QProcess(self)
        if sys.platform == "linux":
            process.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("AI_OS_HOME", str(self.home))
        environment.insert("OMP_THREAD_LIMIT", "2")
        process.setProcessEnvironment(environment)
        return process

    def start_capture(self):
        if self.shutting_down or not load_raw_config(self.home)["screen_context_enabled"]:
            return
        if self.capture and self.capture.isActive():
            return
        self.lock_safe, self.active_user = desktop_state()
        if not self.lock_safe:
            self.status.setText("Paused · desktop locked or lock status unavailable")
            return
        if not shutil.which("tesseract"):
            self.status.setText("Missing local reader: install tesseract and tesseract-data-eng")
            return
        try:
            from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink
        except ImportError:
            self.status.setText("Missing Qt Multimedia: install the project's screen extra")
            return
        if self.capture is None:
            self.capture = QScreenCapture(self)
            self.session = QMediaCaptureSession(self)
            self.sink = QVideoSink(self)
            self.session.setScreenCapture(self.capture)
            self.session.setVideoSink(self.sink)
            self.sink.videoFrameChanged.connect(self.frame)
            self.capture.errorOccurred.connect(self.capture_error)
            self.capture.activeChanged.connect(self.capture_active)
        self.status.setText("Choose a screen in the desktop sharing dialog")
        self.capture.start()

    def capture_active(self, active):
        self.capture_ready = active
        if active:
            self.status.setText("Sharing · waiting for readable text · Pause to stop")
        else:
            self.clear()
            self.status.setText("Sharing stopped · use Resume to select a screen")

    def capture_error(self, error, *_args):
        self.pause()
        self.status.setText(f"Screen sharing unavailable ({error.name}) · use Resume to retry")

    def clear(self):
        self.observation.clear()
        self.last_comment = ""
        self.ocr_valid = False
        self.comment.clear()
        stop_process(self.ocr)
        stop_process(self.commenter)

    def pause(self):
        self.capture_ready = False
        self.clear()
        if self.capture:
            self.capture.stop()
        self.status.setText("Screen sharing paused · no screen context")

    def frame(self, frame):
        if not self.capture_ready or not self.lock_safe or time.monotonic() - self.last_frame < 5:
            return
        if self.ocr.state() != QProcess.ProcessState.NotRunning:
            return
        # Recheck immediately before copying a frame, not only on the timer.
        self.lock_safe, self.active_user = desktop_state()
        if not self.lock_safe or not load_raw_config(self.home)["screen_context_enabled"]:
            self.pause()
            return
        self.last_frame = time.monotonic()
        image = frame.toImage()
        if image.isNull():
            self.observation.clear()
            return
        if max(image.width(), image.height()) > 1920:
            image = image.scaled(1920, 1920, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        # No shell, filenames, OCR logs or recording files.
        self.ocr_valid = True
        self.ocr.start("tesseract", ["stdin", "stdout", "-l", "eng", "--psm", "11"])
        self.ocr.write(buffer.data())
        self.ocr.closeWriteChannel()
        self.ocr_timeout.start(8000)

    def ocr_failed(self):
        self.ocr_valid = False
        self.observation.clear()
        stop_process(self.ocr)
        self.status.setText("Sharing · local text recognition unavailable")

    def ocr_finished(self, code, _status):
        self.ocr_timeout.stop()
        data = bytes(self.ocr.readAllStandardOutput())
        self.ocr.readAllStandardError()  # discard; never log captured text
        unlocked, _active = desktop_state()
        if code or not self.ocr_valid or not unlocked or not load_raw_config(self.home)["screen_context_enabled"]:
            self.observation.clear()
            return
        self.observation.update(data[:24000].decode("utf-8", errors="replace"))
        self.status.setText("Watching · local text only · Pause to stop" if self.observation.snapshot()
                            else "Sharing · no readable text")

    def serve(self):
        while self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            unlocked, _active = desktop_state()
            enabled = load_raw_config(self.home)["screen_context_enabled"]
            snapshot = self.observation.snapshot() if unlocked and enabled else {}
            if not unlocked or not enabled:
                self.observation.clear()
            snapshot = snapshot | {"status": self.status.text(), "capture_active": self.capture_ready,
                                   "comment_visible": bool(self.comment.text())}
            connection.write(json.dumps(snapshot, ensure_ascii=False).encode())
            connection.disconnected.connect(connection.deleteLater)
            connection.disconnectFromServer()

    def poll(self):
        config = load_raw_config(self.home)
        if not config["screen_context_enabled"]:
            self.shutdown()
            QApplication.instance().quit()
            return
        self.lock_safe, self.active_user = desktop_state()
        if not self.lock_safe:
            self.pause()
            self.status.setText("Paused · desktop locked or lock status unavailable")
            return
        snapshot = self.observation.snapshot()
        if not snapshot:
            self.last_comment = ""
            self.comment.clear()
        elif self.comment.text() and not same_scene(self.last_comment, snapshot["text"]):
            self.comment.clear()
        if (self.commenter.state() != QProcess.ProcessState.NotRunning and self.automatic_request
                and self.request_speech_allowed
                and not (config["screen_commentary_speech"] and config["speech_enabled"])):
            stop_process(self.commenter)
        if not config["screen_commentary_enabled"] or not self.active_user:
            if self.commenter.state() != QProcess.ProcessState.NotRunning and self.automatic_request:
                stop_process(self.commenter)
                self.comment.clear()
            return
        if snapshot and time.monotonic() >= self.next_comment:
            # Small clock/cursor/OCR changes alone should not provoke repeated speech.
            if not same_scene(self.last_comment, snapshot["text"]):
                self.request_comment()

    def request_comment(self, automatic=True):
        if self.commenter.state() != QProcess.ProcessState.NotRunning:
            return
        snapshot = self.observation.snapshot()
        if not snapshot:
            self.comment.setText("No fresh screen text yet")
            return
        self.last_comment = snapshot["text"]
        config = load_raw_config(self.home)
        self.next_comment = time.monotonic() + config["screen_commentary_minutes"] * 60
        self.automatic_request = automatic
        self.request_speech_allowed = config["screen_commentary_speech"] and config["speech_enabled"]
        self.comment.clear()
        self.commenter.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.commenter.write(json.dumps({"action": "screen_comment" if automatic else "screen_describe"}).encode())
        self.commenter.closeWriteChannel()
        self.comment_timeout.start(90000)

    def comment_finished(self, code, _status):
        self.comment_timeout.stop()
        data = bytes(self.commenter.readAllStandardOutput())
        self.commenter.readAllStandardError()
        snapshot = self.observation.snapshot()
        if code or not snapshot or not same_scene(snapshot["text"], self.last_comment):
            return
        try:
            value = json.loads(data).get("comment", "")
            if isinstance(value, str):
                self.comment.setText(value[:400])
        except (ValueError, AttributeError):
            self.comment.setText("Comment unavailable")

    def shutdown(self):
        if self.shutting_down:
            return
        self.shutting_down = True
        self.timer.stop()
        self.pause()
        self.server.close()

    def closeEvent(self, event):
        if not self.shutting_down:
            save_settings({"screen_context_enabled": False}, self.home, human_confirmed=True)
        self.shutdown()
        super().closeEvent(event)


def main():
    # The positioned avatar uses XWayland; capture must run in a real Wayland client.
    if os.environ.get("WAYLAND_DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "wayland"
    os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"
    app = QApplication(["regenos-screen"])
    app.setApplicationName("regenos-screen")
    app.setDesktopFileName("regenos-companion")
    instance = LocalInstance(AI_OS_HOME, "regenos-screen")
    if not instance.acquire(lambda: None):
        return 0
    if not load_raw_config(AI_OS_HOME)["screen_context_enabled"]:
        return 0
    observer = ScreenObserver()
    def quit_cleanly(*_args):
        observer.shutdown()
        app.quit()
    signal.signal(signal.SIGTERM, quit_cleanly)
    signal.signal(signal.SIGINT, quit_cleanly)
    app.commitDataRequest.connect(quit_cleanly)
    observer.show()
    app.aboutToQuit.connect(observer.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
