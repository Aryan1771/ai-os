"""Native conversation client using a bounded, noninteractive Python child."""

from __future__ import annotations

import json
import sys
import shlex
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ai_os.conversation_memory import ConversationMemory
from ai_os.config import load_raw_config
from ai_os.security.access_grants import GrantStore, SCOPE
import time
import sqlite3


class ConversationWidget(QWidget):
    def __init__(self, home: Path, parent=None):
        super().__init__(parent)
        self.home = home
        self.process = QProcess(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150_000)
        self.timer.timeout.connect(self.cancel)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.failed)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("AI_OS_HOME", str(home))
        self.process.setProcessEnvironment(env)
        layout = QVBoxLayout(self)
        self.session = QLineEdit("default")
        self.session.setMaxLength(80)
        layout.addWidget(QLabel("Persistent session (use a different name to separate topics)"))
        layout.addWidget(self.session)
        self.access_status = QLabel("No temporary access grant")
        self.access_status.setWordWrap(True)
        layout.addWidget(self.access_status)
        grant_actions = QHBoxLayout()
        self.confirm_grant_button = QPushButton("Review access request")
        self.confirm_grant_button.clicked.connect(self.confirm_grant)
        self.confirm_grant_button.setEnabled(False)
        grant_actions.addWidget(self.confirm_grant_button)
        self.revoke_grant_button = QPushButton("Revoke access")
        self.revoke_grant_button.clicked.connect(self.revoke_grant)
        grant_actions.addWidget(self.revoke_grant_button)
        layout.addLayout(grant_actions)
        self.grant_timer = QTimer(self)
        self.grant_timer.setInterval(1000)
        self.grant_timer.timeout.connect(self.refresh_grant)
        self.grant_timer.start()
        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setMaximumBlockCount(500)
        self.history.setPlaceholderText(
            "History is hidden until loaded. Memory settings control retention."
        )
        layout.addWidget(self.history)
        self.input = QPlainTextEdit()
        self.input.setMaximumHeight(100)
        self.input.setPlaceholderText("Message REgenOS")
        layout.addWidget(self.input)
        actions = QHBoxLayout()
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send)
        actions.addWidget(self.send_button)
        self.load_button = QPushButton("Load recent history")
        self.load_button.clicked.connect(self.load_history)
        actions.addWidget(self.load_button)
        stop = QPushButton("Cancel request")
        stop.clicked.connect(self.cancel)
        actions.addWidget(stop)
        layout.addLayout(actions)
        self.status = QLabel("Apps can be opened directly. Enable full command access in Permissions for reviewed changes.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.cancelled = False

    def load_history(self):
        rows = ConversationMemory(self.home).history(self.session.text() or "default")
        self.history.setPlainText(
            "\n\n".join(f"You: {row['user']}\nREgenOS: {row['assistant']}" for row in rows)
        )

    def send(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        text = self.input.toPlainText().strip()
        if not 1 <= len(text) <= 8000:
            self.status.setText("Enter 1–8000 characters.")
            return
        self.cancelled = False
        request = json.dumps(
            {"action": "chat", "text": text, "session": self.session.text() or "default"}
        )
        self.send_button.setEnabled(False)
        self.session.setEnabled(False)
        self.load_button.setEnabled(False)
        self.history.appendPlainText("You: " + text)
        self.input.clear()
        self.status.setText("Thinking…")
        self.process.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.process.write(request.encode())
        self.process.closeWriteChannel()
        self.timer.start()

    def finished(self, code, _status):
        self.timer.stop()
        self.send_button.setEnabled(True)
        self.session.setEnabled(True)
        self.load_button.setEnabled(True)
        raw = bytes(self.process.readAllStandardOutput())
        self.process.readAllStandardError()  # Do not echo arbitrary diagnostic text into history.
        if self.cancelled:
            return
        try:
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("Response exceeds display limit")
            result = json.loads(raw)
            if code or not result.get("ok"):
                self.status.setText(
                    "Request failed: " + str(result.get("error", "backend error"))[:500]
                )
                return
            reply = result["response"]
            proposal = reply.get("result", {}).get("approval_required") if reply.get("type") == "tool_result" else None
            if proposal and load_raw_config(self.home)["command_access"] == "supervised":
                self.approve_command(proposal)
                return
            text = (
                reply.get("content")
                if reply.get("type") == "text"
                else json.dumps(reply, default=str)
            )
            self.history.appendPlainText("REgenOS: " + text)
            self.status.setText("Reply received. Memory follows the saved retention setting.")
        except (ValueError, KeyError, TypeError):
            self.status.setText("The backend returned an invalid response.")

    def approve_command(self, proposal):
        if proposal.get("tool") != "run_command":
            return False
        arguments = proposal["arguments"]
        cwd = arguments.get("cwd")
        if cwd is not None and (not isinstance(cwd, str) or not cwd.isprintable() or len(cwd) > 4096):
            raise ValueError("Invalid working directory")
        from ai_os.tools.system_tools import assess_command, RiskLevel
        assessment = assess_command(arguments.get("command", []))
        if assessment.risk == RiskLevel.PROHIBITED:
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Approve this command once")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(
            f"Risk: {assessment.risk.value}\n{assessment.reason}\n\n"
            f"Command: {shlex.join(assessment.command)}\n"
            f"Working directory: {arguments.get('cwd') or 'backend default'}\n"
            f"Timeout: {arguments.get('timeout_sec', 15)} seconds (maximum 60)\n\n"
            "Only approve if you understand this exact action. Sudo authentication is never requested in chat."
        )
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.status.setText("Command denied.")
            return False
        payload = json.dumps({"action": "approved_command", "arguments": arguments, "confirmed": True,
                              "session": self.session.text() or "default"})
        self.send_button.setEnabled(False)
        self.session.setEnabled(False)
        self.load_button.setEnabled(False)
        self.status.setText("Running approved command…")
        self.process.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.process.write(payload.encode())
        self.process.closeWriteChannel()
        self.timer.start()
        return True

    def refresh_grant(self):
        try:
            state = GrantStore(self.home).status(self.session.text() or "default")
            grant = state.get("grant")
            label = "No temporary access grant"
            if grant:
                remaining = max(0, int(min(grant["deadline"]-time.monotonic(), grant["wall_deadline"]-time.time())))
                label = f"{grant['kind'].capitalize()} access: {remaining}s remaining — this session"
            if "request" in state:
                label += " · Access request awaiting your review"
            self.access_status.setText(label)
            self.confirm_grant_button.setEnabled("request" in state and self.process.state() == QProcess.ProcessState.NotRunning)
        except (OSError, ValueError, sqlite3.Error):
            self.access_status.setText("Access status unavailable — review disabled")
            self.confirm_grant_button.setEnabled(False)

    def revoke_grant(self):
        GrantStore(self.home).revoke(self.session.text() or "default")
        self.refresh_grant()
        self.status.setText("Access revoked. Already running/completed actions are not undone.")

    def confirm_grant(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        request = GrantStore(self.home).status(self.session.text() or "default").get("request")
        if not request:
            self.refresh_grant()
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Confirm temporary command access")
        box.setTextFormat(Qt.TextFormat.PlainText)
        from ai_os.tools.system_tools import assess_command
        description = SCOPE if request["kind"] == "timed" else (
            "Run this exact command once. Risk: " + assess_command(request["spec"]["command"]).risk.value
            + "\n" + json.dumps(request["spec"], ensure_ascii=True, indent=2))
        box.setText(f"Session: {self.session.text() or 'default'}\nDuration: {request['seconds']} seconds\n\n{description}\n\nAccess expires automatically. Revoke access stops future commands, not effects already completed. This is not an OS sandbox.")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.revoke_grant()
            return False
        payload = json.dumps({"action": "confirm_access_grant", "confirmed": True,
                              "token": request["token"], "session": self.session.text() or "default"})
        self.send_button.setEnabled(False)
        self.session.setEnabled(False)
        self.load_button.setEnabled(False)
        self.status.setText("Confirming access…")
        self.process.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.process.write(payload.encode())
        self.process.closeWriteChannel()
        self.timer.start()
        return True

    def failed(self, _error):
        self.timer.stop()
        self.send_button.setEnabled(True)
        self.session.setEnabled(True)
        self.load_button.setEnabled(True)
        if not self.cancelled:
            self.status.setText("Could not run the Python backend.")

    def cancel(self):
        self.cancelled = True
        self.timer.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(2000)
        self.status.setText("Request cancelled. Completed memory writes, if any, are retained.")
