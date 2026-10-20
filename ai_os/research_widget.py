"""Native, explicitly confirmed public research and paused paragraph narration."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import secrets
import sys
import time

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QTextBrowser, QPlainTextEdit, QComboBox, QPushButton, QVBoxLayout, QWidget,
    QListWidget, QListWidgetItem,
)

from ai_os.config import AI_OS_HOME, load_raw_config
from ai_os.native_widgets import theme_stylesheet
from ai_os.research_reports import _topic, read_report, list_reports, _source_url, report_revision, NAVIGATION_ACTIONS, article_sources, selected_article_urls


class ResearchWidget(QWidget):
    def __init__(self, home: Path = AI_OS_HOME, parent=None):
        super().__init__(parent)
        self.home = Path(home)
        self.report_id = None
        self.paragraphs = []
        self.index = 0
        self.action = None
        self.cancelled = False
        self.navigation_request = None
        self.loaded_revision = None
        self.articles = []
        self.article_topic = None
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
        notice = QLabel("Research finds public article links by default. Choose pages to open; documents are created only with Save report. Full papers are not downloaded or read. No private context or account data is uploaded.")
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
        self.research_button = QPushButton("Find articles…")
        self.research_button.setObjectName("primary")
        self.research_button.clicked.connect(lambda: self.research())
        query.addWidget(self.research_button)
        self.save_report_button = QPushButton("Save report…")
        self.save_report_button.clicked.connect(lambda: self.research(mode="report"))
        query.addWidget(self.save_report_button)
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
        self.active_report = QLabel("Active report: none")
        self.active_report.setTextFormat(Qt.TextFormat.PlainText)
        self.active_report.setWordWrap(True)
        layout.addWidget(self.active_report)
        self.article_list = QListWidget()
        self.article_list.setMaximumHeight(160)
        self.article_list.setToolTip("Select at most three returned public sources. Nothing opens until you confirm their exact URLs.")
        layout.addWidget(self.article_list)
        self.open_articles_button = QPushButton("Open selected articles…")
        self.open_articles_button.clicked.connect(self.open_selected_articles)
        layout.addWidget(self.open_articles_button)
        self.article_list.hide()
        self.open_articles_button.hide()
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
        self.navigation_button = QPushButton("Voice command once…")
        self.navigation_button.clicked.connect(self.request_navigation)
        explain_controls.addWidget(self.navigation_button)
        explain_controls.addStretch()
        layout.addLayout(explain_controls)
        self.status = QLabel("Online research, narration and each voice navigation capture require explicit actions. No continuous report microphone.")
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
        self.save_report_button.setEnabled(not busy)
        self.article_list.setEnabled(not busy)
        self.open_articles_button.setEnabled(bool(self.articles) and not busy)
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
        self.navigation_button.setEnabled(bool(self.report_id) and (not busy or self.action in {"speak", "explain"}))
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
        if self.action == "navigate" and sys.platform == "linux":
            # Verify cancellation ownership before sending permission to record.
            if not self.process.waitForStarted(1000) or not self._owned_group():
                self.stop()
                self.status.setText("Could not establish an owned recording worker. No microphone permission was sent.")
                return False
        self.process.write(json.dumps(request).encode("utf-8"))
        self.process.closeWriteChannel()
        self.timer.start(seconds * 1000)
        self._controls()
        return True

    def research(self, *, mode="articles"):
        if mode not in {"articles", "report"}:
            self.status.setText("Choose article search or an explicit saved report.")
            return False
        try:
            topic = _topic(self.topic.text())
        except ValueError as exc:
            self.status.setText(str(exc))
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Research this exact topic online?")
        box.setTextFormat(Qt.TextFormat.PlainText)
        language = self.report_language.currentData()
        output = ("Output: saved Markdown report file (explicitly requested).\nReport labels: "
                  + ("Hindi" if language == "hi" else "English") if mode == "report" else
                  "Output: public article links only. No document will be created. Choose and confirm up to three links afterward to open them in your browser.")
        box.setText(f"Topic: {topic}\n{output}\n\nThis exact topic and your network address will be visible to Wikipedia and Crossref. No chat history, memory, files or account details are uploaded. Source excerpts keep their original language. Sources may be incomplete or unrelated. Continue?")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.status.setText("Online research cancelled.")
            return False
        self.status.setText("Starting public-source search…")
        return self._start({"action": "research", "topic": topic, "language": language,
                            "mode": mode, "confirmed": True}, 45)

    def show_articles(self, result):
        """Present an existing approved result; no network, file or browser work."""
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        try:
            if not isinstance(result, dict) or result.get("ok") is not True or result.get("mode") != "articles":
                raise ValueError("Invalid article result")
            topic = _topic(result.get("topic"))
            sources = article_sources(result.get("sources"))
        except (ValueError, TypeError):
            self.status.setText("The returned article list was invalid. Nothing was opened or saved.")
            return False
        self.report_id = None
        self.navigation_request = None
        self.loaded_revision = None
        self.paragraphs = []
        self.paragraph_picker.clear()
        self.explanation.clear()
        self.articles, self.article_topic = sources, topic
        self.topic.setText(topic)
        self.active_report.setText("Article results: " + topic + "\nNo report file was created.")
        self.article_list.clear()
        for source in sources:
            item = QListWidgetItem(source["title"] + " · " + source["kind"] + "\n" + source["url"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.article_list.addItem(item)
        self.article_list.show()
        self.open_articles_button.show()
        self.preview.setPlainText("\n\n".join(source["title"] + "\n" + source["summary"] + "\n" + source["url"] for source in sources))
        self.status.setText(f"Found {len(sources)} public source links. Select up to three to open, or explicitly choose Save report. Nothing has opened or been saved.")
        self._controls()
        return True

    def open_selected_articles(self):
        if self.process.state() != QProcess.ProcessState.NotRunning or not self.articles:
            return False
        selected = [index for index in range(self.article_list.count())
                    if self.article_list.item(index).checkState() == Qt.CheckState.Checked]
        try:
            snapshot = article_sources(self.articles)
            urls = selected_article_urls(snapshot, selected, check_network=False)
            chosen = [{key: snapshot[index][key] for key in ("title", "url", "kind")} for index in selected]
        except (OSError, ValueError, TypeError):
            self.status.setText("Select one to three public source links. Private or invalid destinations are blocked.")
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Open these exact public articles?")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText("Topic: " + self.article_topic + "\n\n" + "\n".join(urls)
                    + "\n\nOpen these pages in your browser. The browser may follow publisher redirects; RE does not capture page content, sign in or submit forms. No report file will be created.")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.status.setText("Article opening cancelled.")
            return False
        self.status.setText("Validating and opening the exact selected public article URLs…")
        return self._start({"action": "open_articles", "sources": chosen,
                            "indices": list(range(len(chosen))), "confirmed": True}, 40)

    def load_report(self, report_id):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        try:
            report = read_report(report_id, home=self.home)
        except (OSError, ValueError):
            self.status.setText("Could not load that local report. Check its ID and permissions.")
            return False
        self.report_id = report_id
        self.articles, self.article_topic = [], None
        self.article_list.clear()
        self.article_list.hide()
        self.open_articles_button.hide()
        self.navigation_request = None
        self.loaded_revision = report_revision(report)
        self.saved_id.setText(report_id)
        report_title = report["markdown"].splitlines()[0].removeprefix("# Research: ")[:160]
        self.active_report.setText(f"Active report: {report_title}\nID: {report_id}")
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

    def request_navigation(self):
        if not self.report_id or not self.paragraphs:
            self.status.setText("Load a saved report before recording a navigation command.")
            return False
        if self.process.state() != QProcess.ProcessState.NotRunning and self.action not in {"speak", "explain"}:
            self.status.setText("Finish or stop the current task before another report voice command.")
            return False
        if load_raw_config(self.home)["always_listening_enabled"]:
            self.status.setText("Disable continuous listening before recording one report navigation command.")
            return False
        try:
            report = read_report(self.report_id, home=self.home)
            if report_revision(report) != self.loaded_revision:
                raise ValueError("Changed report")
        except (OSError, ValueError):
            self.status.setText("The visible report changed or is unavailable. Reload it before voice navigation.")
            return False
        box = QMessageBox(self)
        box.setWindowTitle("One local voice command for this report?")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(self.active_report.text()
                    + f"\nParagraph: {self.index + 1}\n\n"
                    "Record one short English/Hindi navigation command using your saved language and speaker-filter settings. "
                    "Allowed: next, previous, repeat, pause or explain. This may read a paragraph or explain it with local Ollama. "
                    "No general computer commands, new research, account access, uploads or saved transcripts. "
                    "Current narration pauses before recording to avoid hearing RE's voice. "
                    "Initial wait: up to 8 seconds; utterance: up to 15 seconds, preserving your ending pause. "
                    "Stop cancels microphone/transcription and owned audio children. Continue?")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.status.setText("Report voice command cancelled. No microphone started.")
            return False
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.stop()
            if self.process.state() != QProcess.ProcessState.NotRunning:
                self.status.setText("Could not stop report narration. Microphone stays off.")
                return False
        self.navigation_request = {"report_id": self.report_id, "index": self.index,
                                   "revision": self.loaded_revision, "nonce": secrets.token_hex(16),
                                   "expires": time.monotonic() + 180}
        request = {key: value for key, value in self.navigation_request.items() if key != "expires"}
        self.status.setText("Microphone navigation: one approved recording. Stop cancels it.")
        if not self._start({"action": "navigate", **request, "confirmed": True}, 160):
            self.navigation_request = None
            return False
        return True

    def _apply_navigation(self, result):
        request, self.navigation_request = self.navigation_request, None
        try:
            if (not isinstance(request, dict) or not isinstance(result, dict)
                    or result.get("ok") is not True or type(result.get("index")) is not int
                    or time.monotonic() > request["expires"]
                    or any(result.get(key) != request[key] for key in ("report_id", "index", "revision", "nonce"))
                    or self.report_id != request["report_id"] or self.index != request["index"]
                    or report_revision(read_report(self.report_id, home=self.home)) != request["revision"]
                    or result.get("navigation") not in NAVIGATION_ACTIONS
                    or result.get("language") not in {"en", "hi"}):
                raise ValueError("Expired or changed report command")
        except (OSError, ValueError, TypeError, KeyError):
            self.status.setText("Stale or changed report voice command discarded. Nothing was read or explained.")
            self._controls()
            return False
        action = result["navigation"]
        self.status.setText("Recognized report command: " + action + ". No transcript saved.")
        if action == "pause":
            self.status.setText("Report reading paused. No microphone remains active.")
            self._controls()
            return True
        if action == "next":
            if self.index + 1 >= len(self.paragraphs):
                self.status.setText("Already at the last paragraph. Reading remains paused.")
                self._controls()
                return False
            return self.read_next()
        if action == "previous":
            if self.index <= 0:
                self.status.setText("Already at the first paragraph. Reading remains paused.")
                self._controls()
                return False
            return self.read_previous()
        if action == "explain":
            self.language.setCurrentIndex(self.language.findData(result["language"]))
            return self.explain_current()
        return self.read_current()

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
            if self.action == "navigate":
                self._apply_navigation(result)
                return
            if self.action == "research":
                if result.get("mode") == "articles":
                    self.show_articles(result)
                else:
                    self.load_report(result["report_id"])
            else:
                if self.action == "explain":
                    self.explanation.setPlainText(str(result.get("explanation", ""))[:3000])
                self.status.setText(str(result.get("message", "Paragraph finished. Paused; choose Next paragraph to continue."))[:300])
        else:
            self.navigation_request = None
            error = result.get("error") if isinstance(result, dict) else None
            self.status.setText(error[:300] if isinstance(error, str) else "Research worker stopped without a valid successful result.")
        self._controls()

    def _error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.timer.stop()
            self.navigation_request = None
            self.status.setText("Could not start the research worker.")
            self._controls()

    def _owned_group(self):
        pid = self.process.processId()
        if not pid or pid <= 1 or sys.platform != "linux":
            return False
        try:
            return os.getpgid(pid) == pid and pid != os.getpgrp()
        except OSError:
            return False

    def stop(self):
        self.cancelled = True
        self.navigation_request = None
        self.timer.stop()
        pid = self.process.processId()
        if self._owned_group():
            try:
                os.killpg(pid, signal.SIGKILL)
            except OSError:
                pass
        self.process.kill()
        self.process.waitForFinished(1000)
        if self.action in {"speak", "explain", "navigate"}:
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
    app.setDesktopFileName("regenos-research")
    from ai_os.brand_assets import brand_icon
    app.setWindowIcon(brand_icon())
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
