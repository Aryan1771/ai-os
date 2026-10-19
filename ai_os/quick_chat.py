"""Compact native RE chat. Reuses the reviewed conversation/tool client."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from ai_os.config import AI_OS_HOME, load_raw_config
from ai_os.conversation_widget import ConversationWidget
from ai_os.native_widgets import CompanionCanvas, LocalInstance, theme_stylesheet
from ai_os.companion_state import read_state


class QuickChatWindow(QMainWindow):
    def __init__(self, home: Path = AI_OS_HOME):
        super().__init__()
        self.home = Path(home)
        self.setWindowTitle("REgenOS Chat")
        self.resize(620, 740)
        self.setMinimumSize(520, 540)
        outer = QWidget()
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(18, 16, 18, 12)
        header = QHBoxLayout()
        self.canvas = CompanionCanvas()
        self.canvas.setMinimumSize(58, 58)
        self.canvas.setFixedSize(58, 58)
        header.addWidget(self.canvas)
        title = QLabel("RE")
        title.setObjectName("product")
        header.addWidget(title)
        subtitle = QLabel("Your desktop companion")
        subtitle.setObjectName("muted")
        header.addWidget(subtitle)
        header.addStretch()
        settings = QPushButton("Settings")
        settings.clicked.connect(self.open_settings)
        header.addWidget(settings)
        layout.addLayout(header)
        self.mode_indicator = QLabel()
        self.mode_indicator.setObjectName("muted")
        self.mode_indicator.setTextFormat(Qt.TextFormat.PlainText)
        self.mode_indicator.setWordWrap(True)
        layout.addWidget(self.mode_indicator)
        self.conversation = ConversationWidget(self.home, compact=True)
        layout.addWidget(self.conversation, 1)
        hint = QLabel("Enter sends · Shift+Enter adds a line · Ctrl+Enter stops and steers the current request")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.setCentralWidget(outer)
        self.poll = QTimer(self)
        self.poll.setInterval(350)
        self.poll.timeout.connect(self.refresh_mode)
        self.poll.start()
        self.refresh_mode()
        self.conversation.input.setFocus()

    def refresh_mode(self):
        try:
            config = load_raw_config(self.home)
            mic = "Continuous microphone ON" if config["always_listening_enabled"] else "Continuous microphone off"
            speech = "Spoken replies on" if config["speech_enabled"] else "Spoken replies off"
            identity = " · Enrolled voice filter on" if config.get("speaker_recognition_enabled") else ""
            self.mode_indicator.setText(mic + " · " + speech + identity)
            self.canvas.set_state(read_state(self.home), config)
            if getattr(self, "_theme", None) != config["theme"]:
                self.setStyleSheet(theme_stylesheet(config["theme"]))
                self._theme = config["theme"]
        except (OSError, ValueError, TypeError, KeyError):
            self.mode_indicator.setText("Microphone and voice settings unavailable — open Settings")

    def open_settings(self):
        process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("AI_OS_HOME", str(self.home))
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments(["-m", "ai_os.native_settings"])
        result = process.startDetached()
        success = result[0] if isinstance(result, tuple) else result
        if not success:
            self.conversation.status.setText("Settings could not start. Run regenos-settings from your desktop terminal.")
        process.deleteLater()

    def closeEvent(self, event):
        if not self.conversation.cancel():
            event.ignore()
            return
        self.poll.stop()
        self.canvas.timer.stop()
        self.conversation.grant_timer.stop()
        event.accept()


def main() -> int:
    app = QApplication(["regenos-chat", *sys.argv[1:]])
    app.setApplicationName("regenos-chat")
    app.setDesktopFileName("regenos-chat")
    app.setStyle("Fusion")
    window = None

    def activate():
        if window is not None:
            window.showNormal()
            window.raise_()
            window.activateWindow()
            window.conversation.input.setFocus()

    instance = LocalInstance(AI_OS_HOME, "quick-chat")
    if not instance.acquire(activate):
        return 0
    window = QuickChatWindow(AI_OS_HOME)
    window.show()
    try:
        return app.exec()
    finally:
        instance.server.close()
        instance.lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
