"""Native, explicitly confirmed public research and paused paragraph narration."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sys

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QTextBrowser, QPlainTextEdit, QComboBox, QPushButton, QVBoxLayout, QWidget,
)

from ai_os.config import AI_OS_HOME, load_raw_config
from ai_os.native_widgets import theme_stylesheet
from ai_os.research_reports import _topic, read_report, list_reports, _source_url


class ResearchWidget(QWidget):
    def __init__(self, home: Path = AI_OS_HOME, parent=None):
        super().__init__(parent)
        self.home = Path(home)
        self.report_id = None
        self.paragraphs = []
        self.index = 0
        self.action = None
        self.cancelled = False
        self.output = bytearray()
        self.process = QProcess(self)
        if sys.platform == "linux":
            self.process.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("AI_OS_HOME", str(self.home))
        self.process.setProcessEnvironment(environment)
        self.process.readyReadStandardOutput.connect(self._output)
        self.process.readyReadStandardError.connect(lambda: self.process.readAllStandardError())
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.stop)
        layout = QVBoxLayout(self)
        title = QLabel("Research")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        notice = QLabel("Review a public topic, save a cited Markdown brief locally, then read one paragraph at a time. Full papers are not downloaded or read. No private context or account data is uploaded.")
        notice.setWordWrap(True)
        notice.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(notice)
        query = QHBoxLayout()
        self.topic = QLineEdit()
        self.topic.setMaxLength(160)
        self.topic.setPlaceholderText("Topic, e.g. giant panda conservation")
        query.addWidget(self.topic, 1)
        self.research_button = QPushButton("Research online…")
        self.research_button.setObjectName("primary")
        self.research_button.clicked.connect(self.research)
        query.addWidget(self.research_button)
        layout.addLayout(query)
        saved = QHBoxLayout()
        self.saved_id = QLineEdit()
        self.saved_id.setPlaceholderText("Saved report ID")
        saved.addWidget(self.saved_id, 1)
        self.load_button = QPushButton("Load saved report")
        self.load_button.clicked.connect(lambda: self.load_report(self.saved_id.text().strip()))
        saved.addWidget(self.load_button)
        layout.addLayout(saved)
        self.saved_reports = QComboBox()
        self.saved_reports.setPlaceholderText("Choose a saved report")
        self.saved_reports.activated.connect(lambda index: self.load_report(self.saved_reports.itemData(index)))
        layout.addWidget(self.saved_reports)
        self.preview = QTextBrowser()
        self.preview.setOpenLinks(False)
        self.preview.anchorClicked.connect(self.open_source)
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("The saved Markdown report and cited sources appear here.")
        layout.addWidget(self.preview, 1)
        self.explanation = QPlainTextEdit()
        self.explanation.setReadOnly(True)
        self.explanation.setMaximumHeight(110)
        self.explanation.setPlaceholderText("Optional local-model explanation appears here. Verify it against the sources.")
        layout.addWidget(self.explanation)
        controls = QHBoxLayout()
        self.read_button = QPushButton("Read paragraph")
        self.read_button.clicked.connect(self.read_current)
        controls.addWidget(self.read_button)
        self.next_button = QPushButton("Next paragraph")
        self.next_button.clicked.connect(self.read_next)
        controls.addWidget(self.next_button)
        self.stop_button = QPushButton("Stop / pause")
        self.stop_button.clicked.connect(self.stop)
        controls.addWidget(self.stop_button)
        self.open_button = QPushButton("Open report file")
        self.open_button.clicked.connect(self.open_report)
        controls.addWidget(self.open_button)
        self.position = QLabel("No report loaded")
        controls.addWidget(self.position)
        controls.addStretch()
        layout.addLayout(controls)
        explain_controls = QHBoxLayout()
        self.explain_button = QPushButton("Explain & read this paragraph")
        self.explain_button.clicked.connect(self.explain_current)
        explain_controls.addWidget(self.explain_button)
        self.language = QComboBox()
        self.language.addItem("English explanation", "en")
        self.language.addItem("Hindi explanation", "hi")
        self.language.setCurrentIndex(1 if load_raw_config(self.home)["whisper_language"] == "hi" else 0)
        explain_controls.addWidget(self.language)
        explain_controls.addStretch()
        layout.addLayout(explain_controls)
        self.status = QLabel("Online research and reading aloud each require an explicit action. Voice pause/next commands are not connected.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.refresh_saved()
        self._controls()

    def refresh_saved(self):
        self.saved_reports.clear()
        try:
            for report in list_reports(self.home):
                self.saved_reports.addItem(report["title"], report["report_id"])
            self.saved_reports.setCurrentIndex(-1)
        except (OSError, ValueError):
            self.status.setText("Could not inspect local report storage.")

    def open_source(self, url):
        value = url.toString()
        if (_source_url(value, "en.wikipedia.org", "/wiki/")
                or _source_url(value, "doi.org", "/10.")):
            QDesktopServices.openUrl(url)

    def open_report(self):
        if self.report_id:
            report = read_report(self.report_id, home=self.home)
            QDesktopServices.openUrl(QUrl.fromLocalFile(report["path"]))

    def _controls(self):
        busy = self.process.state() != QProcess.ProcessState.NotRunning
        self.research_button.setEnabled(not busy)
        self.load_button.setEnabled(not busy)
        self.topic.setEnabled(not busy)
        self.saved_id.setEnabled(not busy)
        self.saved_reports.setEnabled(not busy)
        self.open_button.setEnabled(bool(self.report_id) and not busy)
        self.explain_button.setEnabled(bool(self.paragraphs) and not busy)
        self.language.setEnabled(not busy)
        self.read_button.setEnabled(bool(self.paragraphs) and not busy)
        self.next_button.setEnabled(bool(self.paragraphs) and self.index + 1 < len(self.paragraphs) and not busy)
        self.stop_button.setEnabled(busy)
        self.position.setText(f"Paragraph {self.index + 1} of {len(self.paragraphs)}" if self.paragraphs else "No report loaded")

    def _start(self, request, seconds):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        self.output.clear()
        self.cancelled = False
        self.action = request["action"]
        self.process.start(sys.executable, ["-m", "ai_os.research_reports", "--home", str(self.home)])
        self.process.write(json.dumps(request).encode("utf-8"))
        self.process.closeWriteChannel()
        self.timer.start(seconds * 1000)
        self._controls()
        return True

    def research(self):
        try:
            topic = _topic(self.topic.text())
        except ValueError as exc:
            self.status.setText(str(exc))
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Research this exact topic online?")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(f"Topic: {topic}\n\nThis topic and your network address will be visible to Wikipedia and Crossref. No chat history, memory, files or account details are uploaded. Results stay in your local REgenOS research folder. Sources may be incomplete or unrelated. Continue?")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.status.setText("Online research cancelled.")
            return False
        self.status.setText("Starting public-source search…")
        return self._start({"action": "research", "topic": topic, "confirmed": True}, 45)

    def load_report(self, report_id):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        try:
            report = read_report(report_id, home=self.home)
        except (OSError, ValueError):
            self.status.setText("Could not load that local report. Check its ID and permissions.")
            return False
        self.report_id = report_id
        self.saved_id.setText(report_id)
        self.paragraphs = report["paragraphs"]
        self.index = 0
        self.explanation.clear()
        self.preview.setMarkdown(report["markdown"])
        self.refresh_saved()
        self.status.setText("Saved locally: " + report["path"] + ". Reading pauses after every paragraph.")
        self._controls()
        return True

    def read_current(self):
        if not self.paragraphs:
            return False
        self.status.setText(f"Speaking paragraph {self.index + 1}. Stop / pause stops its audio.")
        return self._start({"action": "speak", "report_id": self.report_id, "index": self.index,
                            "confirmed": True}, 250)

    def read_next(self):
        if self.process.state() != QProcess.ProcessState.NotRunning or self.index + 1 >= len(self.paragraphs):
            return False
        self.index += 1
        self._controls()
        return self.read_current()

    def explain_current(self):
        if not self.paragraphs:
            return False
        self.status.setText("Explaining this excerpt with local Ollama, then reading it. Verify the interpretation against the source.")
        return self._start({"action": "explain", "report_id": self.report_id, "index": self.index,
                            "language": self.language.currentData(), "confirmed": True}, 300)

    def _output(self):
        self.output.extend(bytes(self.process.readAllStandardOutput()))
        if len(self.output) > 65536:
            self.stop()

    def _finished(self, code, exit_status):
        self.timer.stop()
        self._output()
        if self.cancelled:
            self.status.setText("Stopped. Reading is paused; Read paragraph repeats the selected paragraph.")
            self._controls()
            return
        result = None
        try:
            for line in self.output.decode("utf-8").splitlines():
                item = json.loads(line)
                if "result" in item:
                    result = item["result"]
                elif isinstance(item.get("progress"), str):
                    self.status.setText(item["progress"][:200])
        except (ValueError, UnicodeError, TypeError):
            result = None
        if isinstance(result, dict) and result.get("ok"):
            if self.action == "research":
                self.load_report(result["report_id"])
            else:
                if self.action == "explain":
                    self.explanation.setPlainText(str(result.get("explanation", ""))[:3000])
                self.status.setText(str(result.get("message", "Paragraph finished. Paused; choose Next paragraph to continue."))[:300])
        else:
            self.status.setText(result.get("error", "Research or reading failed.")[:300] if isinstance(result, dict) else "Research worker stopped without a valid result.")
        self._controls()

    def _error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.timer.stop()
            self.status.setText("Could not start the research worker.")
            self._controls()

    def stop(self):
        self.cancelled = True
        self.timer.stop()
        pid = self.process.processId()
        if pid and sys.platform == "linux":
            try:
                os.killpg(pid, signal.SIGKILL)
            except OSError:
                pass
        self.process.kill()
        self.process.waitForFinished(1000)
        if self.action in {"speak", "explain"}:
            from ai_os.speech_lease import speech_lease
            from ai_os.companion_state import publish_state
            with speech_lease(self.home) as acquired:
                if acquired:
                    publish_state("idle", home=self.home)
        self._controls()

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("REgenOS Research")
    app.setStyleSheet(theme_stylesheet(load_raw_config(AI_OS_HOME)["theme"]))
    window = QMainWindow()
    widget = ResearchWidget()
    window.setCentralWidget(widget)
    window.setWindowTitle("REgenOS Research")
    window.resize(940, 720)
    app.aboutToQuit.connect(widget.stop)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
