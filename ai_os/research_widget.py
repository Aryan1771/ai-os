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
        self.report_language = QComboBox()
        self.report_language.addItem("English report", "en")
        self.report_language.addItem("हिंदी रिपोर्ट", "hi")
        self.report_language.setCurrentIndex(1 if load_raw_config(self.home)["whisper_language"] == "hi" else 0)
        query.addWidget(self.report_language)
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
        self.paragraph_picker = QComboBox()
        self.paragraph_picker.setPlaceholderText("Choose a paragraph to read or explain")
        self.paragraph_picker.activated.connect(self.select_paragraph)
        layout.addWidget(self.paragraph_picker)
        controls = QHBoxLayout()
        self.previous_button = QPushButton("Previous paragraph")
        self.previous_button.clicked.connect(self.read_previous)
        controls.addWidget(self.previous_button)
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
            try:
                report = read_report(self.report_id, home=self.home)
            except (OSError, ValueError):
                self.status.setText("The report file is no longer available or its permissions changed. Reload a saved report.")
                return False
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(report["path"])):
                self.status.setText("The desktop could not open this report. Its path is shown above.")
                return False
            return True
        return False

    def _controls(self):
        busy = self.process.state() != QProcess.ProcessState.NotRunning
        self.research_button.setEnabled(not busy)
        self.load_button.setEnabled(not busy)
        self.topic.setEnabled(not busy)
        self.report_language.setEnabled(not busy)
        self.saved_id.setEnabled(not busy)
        self.saved_reports.setEnabled(not busy)
        self.open_button.setEnabled(bool(self.report_id) and not busy)
        self.explain_button.setEnabled(bool(self.paragraphs) and not busy)
        self.language.setEnabled(not busy)
        self.read_button.setEnabled(bool(self.paragraphs) and not busy)
        self.previous_button.setEnabled(bool(self.paragraphs) and self.index > 0 and not busy)
        self.paragraph_picker.setEnabled(bool(self.paragraphs) and not busy)
        self.next_button.setEnabled(bool(self.paragraphs) and self.index + 1 < len(self.paragraphs) and not busy)
        self.stop_button.setEnabled(busy)
        self.position.setText(f"Paragraph {self.index + 1} of {len(self.paragraphs)}" if self.paragraphs else "No report loaded")
        if self.paragraphs:
            self.paragraph_picker.setCurrentIndex(self.index)

    def _start(self, request, seconds):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        self.output.clear()
        self._progress_offset = 0
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
        language = self.report_language.currentData()
        box.setText(f"Topic: {topic}\nReport labels: {'Hindi' if language == 'hi' else 'English'}\n\nThis exact topic and your network address will be visible to Wikipedia and Crossref. No chat history, memory, files or account details are uploaded. Results stay in your local REgenOS research folder. Source excerpts keep their original language; use local Explain & read for your selected language. Sources may be incomplete or unrelated. Continue?")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.status.setText("Online research cancelled.")
            return False
        self.status.setText("Starting public-source search…")
        return self._start({"action": "research", "topic": topic, "language": language,
                            "confirmed": True}, 45)

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
        self.paragraph_picker.clear()
        for number, paragraph in enumerate(self.paragraphs, 1):
            self.paragraph_picker.addItem(f"{number}. {paragraph[:100]}", number - 1)
        language_index = self.language.findData(report["language"])
        self.language.setCurrentIndex(max(0, language_index))
        self.explanation.clear()
        self.preview.setMarkdown(report["markdown"])
        self.refresh_saved()
        self.status.setText("Saved locally: " + report["path"] + ". Reading pauses after every paragraph.")
        self._controls()
        self._show_current()
        return True

    def _show_current(self):
        if self.paragraphs:
            # Highlight a literal prefix in the already rendered local report;
            # do not interpret source text as rich markup or a navigation URL.
            cursor = self.preview.document().find(self.paragraphs[self.index][:80])
            if not cursor.isNull():
                self.preview.setTextCursor(cursor)
                self.preview.ensureCursorVisible()

    def select_paragraph(self, index):
        if (self.process.state() != QProcess.ProcessState.NotRunning
                or type(index) is not int or not 0 <= index < len(self.paragraphs)):
            return False
        self.index = index
        self.explanation.clear()
        self._controls()
        self._show_current()
        self.status.setText(f"Paragraph {index + 1} selected. Choose Read or Explain & read; nothing plays automatically.")
        return True

    def read_current(self):
        if not self.paragraphs:
            return False
        self._show_current()
        self.status.setText(f"Speaking paragraph {self.index + 1}. Stop / pause stops its audio.")
        return self._start({"action": "speak", "report_id": self.report_id, "index": self.index,
                            "confirmed": True}, 250)

    def read_next(self):
        if self.process.state() != QProcess.ProcessState.NotRunning or self.index + 1 >= len(self.paragraphs):
            return False
        self.index += 1
        self.explanation.clear()
        self._controls()
        return self.read_current()

    def read_previous(self):
        if self.process.state() != QProcess.ProcessState.NotRunning or self.index <= 0:
            return False
        self.index -= 1
        self.explanation.clear()
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
            self.output.clear()  # Avoid recursively stopping on the same buffer.
            self.stop()
            self.status.setText("Research worker exceeded its output limit and was stopped.")
            return
        # Display completed progress lines as they arrive rather than waiting
        # for the finished signal. A partial UTF-8/JSON line remains buffered.
        offset = getattr(self, "_progress_offset", 0)
        while b"\n" in self.output[offset:]:
            end = self.output.index(b"\n", offset)
            line = self.output[offset:end]
            offset = end + 1
            try:
                event = json.loads(line)
                if (not self.cancelled and isinstance(event, dict)
                        and isinstance(event.get("progress"), str)):
                    self.status.setText(event["progress"][:200])
            except (ValueError, UnicodeError):
                pass
        self._progress_offset = offset

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
        if code == 0 and isinstance(result, dict) and result.get("ok") is True:
            if self.action == "research":
                self.load_report(result["report_id"])
            else:
                if self.action == "explain":
                    self.explanation.setPlainText(str(result.get("explanation", ""))[:3000])
                self.status.setText(str(result.get("message", "Paragraph finished. Paused; choose Next paragraph to continue."))[:300])
        else:
            error = result.get("error") if isinstance(result, dict) else None
            self.status.setText(error[:300] if isinstance(error, str) else "Research worker stopped without a valid successful result.")
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
