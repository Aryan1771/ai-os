"""Native conversation client using a bounded, noninteractive Python child."""

from __future__ import annotations

import json
import sys
import shlex
import os
import signal
import tempfile
import secrets
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QInputDialog,
    QToolButton,
)

from ai_os.conversation_memory import ConversationMemory
from ai_os.config import load_raw_config
from ai_os.security.access_grants import GrantStore, SCOPE, USER_SCOPE
import time
import sqlite3


class ConversationInput(QPlainTextEdit):
    sendRequested = Signal()
    steerRequested = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.steerRequested.emit()
                event.accept()
                return
            if not modifiers & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
                self.sendRequested.emit()
                event.accept()
                return
        super().keyPressEvent(event)


class ConversationWidget(QWidget):
    def __init__(self, home: Path, parent=None, *, compact: bool = False):
        super().__init__(parent)
        self.home = home
        self.request_generation = 0
        self.process = None
        self._request_started_wall = 0.0
        self._request_started_mono = 0.0
        self._last_phase = None
        self._new_process()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150_000)
        self.timer.timeout.connect(self.cancel)
        layout = QVBoxLayout(self)
        self.session = QLineEdit("default")
        self.session.setMaxLength(80)
        session_controls = QWidget()
        session_layout = QVBoxLayout(session_controls)
        session_layout.setContentsMargins(0, 0, 0, 0)
        session_layout.addWidget(QLabel("Conversation session" if compact else "Persistent session (use a different name to separate topics)"))
        session_layout.addWidget(self.session)
        self.access_status = QLabel("No temporary access grant")
        self.access_status.setWordWrap(True)
        layout.addWidget(self.access_status)
        self.pending_review_button = QPushButton("Review requested task…")
        self.pending_review_button.clicked.connect(self.review_pending_task)
        self.pending_review_button.hide()
        layout.addWidget(self.pending_review_button)
        grant_actions = QHBoxLayout()
        self.confirm_grant_button = QPushButton("Review access request")
        self.confirm_grant_button.clicked.connect(self.confirm_grant)
        self.confirm_grant_button.setEnabled(False)
        grant_actions.addWidget(self.confirm_grant_button)
        self.user_access_button = QPushButton("Broad user access…")
        self.user_access_button.clicked.connect(self.request_user_access)
        grant_actions.addWidget(self.user_access_button)
        self.revoke_grant_button = QPushButton("Revoke access")
        self.revoke_grant_button.clicked.connect(self.revoke_grant)
        grant_actions.addWidget(self.revoke_grant_button)
        session_layout.addLayout(grant_actions)
        if compact:
            options = QToolButton()
            options.setText("Conversation & access ▸")
            options.setCheckable(True)
            options.toggled.connect(session_controls.setVisible)
            options.toggled.connect(lambda checked: options.setText("Conversation & access ▾" if checked else "Conversation & access ▸"))
            layout.addWidget(options)
            session_controls.setVisible(False)
        layout.addWidget(session_controls)
        browser_actions = QHBoxLayout()
        for label, callback in (("ChatGPT sign-in", lambda: self.approve_action({"tool": "chatgpt_login", "arguments": {}})),
                                ("Ask ChatGPT", self.ask_browser_ai), ("Research page", self.research_page)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            browser_actions.addWidget(button)
        browser_widget = QWidget()
        browser_widget.setLayout(browser_actions)
        browser_widget.setVisible(not compact)
        layout.addWidget(browser_widget)
        if compact:
            self.confirm_grant_button.setText("Review access")
            self.user_access_button.setText("Grant access…")
            self.revoke_grant_button.setText("Revoke")
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
        self.input = ConversationInput()
        self.input.setMaximumHeight(100)
        self.input.setPlaceholderText("Message RE · Enter to send · Shift+Enter new line · Ctrl+Enter to steer")
        self.input.sendRequested.connect(self.send)
        self.input.steerRequested.connect(self.steer)
        layout.addWidget(self.input)
        actions = QHBoxLayout()
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("primary")
        self.send_button.clicked.connect(self.send)
        actions.addWidget(self.send_button)
        self.mic_button = QPushButton("Speak once")
        self.mic_button.clicked.connect(self.speak_once)
        actions.addWidget(self.mic_button)
        self.load_button = QPushButton("Load recent history")
        self.load_button.clicked.connect(self.load_history)
        actions.addWidget(self.load_button)
        self.stop_button = QPushButton("Stop" if compact else "Cancel request")
        self.stop_button.clicked.connect(self.cancel)
        actions.addWidget(self.stop_button)
        if compact:
            self.load_button.setText("History")
        layout.addLayout(actions)
        self.status = QLabel("Apps can be opened directly. Enable full command access in Permissions for reviewed changes.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.activity_status = QLabel("Ready")
        self.activity_status.setTextFormat(Qt.TextFormat.PlainText)
        self.activity_status.setObjectName("muted")
        self.activity_status.setWordWrap(True)
        layout.addWidget(self.activity_status)
        self.activity = QPlainTextEdit()
        self.activity.setReadOnly(True)
        self.activity.setMaximumBlockCount(30)
        self.activity.setMaximumHeight(85)
        self.activity.setPlaceholderText("Operational activity appears here; private model reasoning is not displayed.")
        if compact:
            activity_toggle = QToolButton()
            activity_toggle.setText("Show activity ▸")
            activity_toggle.setCheckable(True)
            activity_toggle.toggled.connect(self.activity.setVisible)
            activity_toggle.toggled.connect(lambda checked: activity_toggle.setText("Hide activity ▾" if checked else "Show activity ▸"))
            layout.addWidget(activity_toggle)
            self.activity.setVisible(False)
        layout.addWidget(self.activity)
        self.activity_timer = QTimer(self)
        self.activity_timer.setInterval(400)
        self.activity_timer.timeout.connect(self.refresh_activity)
        self.cancelled = False
        self.voice_directory = None

    def _new_process(self):
        self.request_generation += 1
        generation = self.request_generation
        process = QProcess(self)
        if sys.platform == "linux":
            process.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("AI_OS_HOME", str(self.home))
        env.insert("AI_OS_REQUEST_ID", secrets.token_hex(16))
        process.setProcessEnvironment(env)
        process.finished.connect(lambda code, status: self._finished_current(process, generation, code, status))
        process.errorOccurred.connect(lambda error: self._failed_current(process, generation, error))
        process.started.connect(lambda: self._started_current(process, generation))
        self.process = process
        self.worker_group = None
        self._active_chat = None

    def _finished_current(self, process, generation, code, status):
        if process is self.process and generation == self.request_generation:
            self.finished(code, status)

    def _failed_current(self, process, generation, error):
        if process is self.process and generation == self.request_generation:
            self.failed(error)

    def _started_current(self, process, generation):
        if process is not self.process or generation != self.request_generation:
            return
        self._remember_worker_group(process)
        self.cancelled = False
        self._request_started_wall = time.time()
        self._request_started_mono = time.monotonic()
        self._last_phase = None
        self._last_progress = None
        self.activity.clear()
        self.activity.appendPlainText("Request started. You can type a correction and press Ctrl+Enter to steer.")
        self.activity_status.setText("Preparing request…")
        self.mic_button.setEnabled(False)
        self.activity_timer.start()

    def _remember_worker_group(self, process):
        if sys.platform != "linux":
            return
        pid = process.processId()
        try:
            if pid > 1 and pid != os.getpgrp() and os.getpgid(pid) == pid:
                self.worker_group = pid
        except (ProcessLookupError, PermissionError):
            pass

    def _signal_worker_group(self, signum):
        if self.worker_group is None:
            return False
        try:
            os.killpg(self.worker_group, signum)
        except ProcessLookupError:
            pass
        except PermissionError:
            return False
        return True

    def refresh_activity(self):
        if self.process.state() == QProcess.ProcessState.NotRunning:
            return
        elapsed = max(0, int(time.monotonic() - self._request_started_mono))
        labels = {"listening": "Microphone recording", "transcribing": "Transcribing speech",
                  "thinking": "Preparing the response", "working": "Running a requested task",
                  "speaking": "Speaking the response", "error": "Handling a request error"}
        phase = None
        try:
            path = self.home / "run/avatar_state.json"
            if path.stat().st_size <= 16384:
                state = json.loads(path.read_text(encoding="utf-8"))
                if (isinstance(state, dict) and isinstance(state.get("updated_at"), (int, float))
                        and self._request_started_wall <= state["updated_at"] <= time.time() + 1):
                    phase = state.get("phase")
        except (OSError, ValueError, TypeError):
            pass
        label = labels.get(phase, "Waiting for the backend")
        try:
            path = self.home / "run/request-progress.json"
            if path.stat().st_size <= 2048:
                event = json.loads(path.read_text())
                expected = self.process.processEnvironment().value("AI_OS_REQUEST_ID")
                if isinstance(event, dict) and event.get("request_id") == expected and event.get("updated_at", 0) >= self._request_started_wall:
                    state = event.get("state")
                    tool = event.get("tool", "task")
                    from ai_os.ai_os_core import build_tool_registry
                    if tool not in build_tool_registry(self.home):
                        tool = "task"
                    public = {"model": "Preparing a response", "tool_started": f"Using {tool}",
                              "tool_finished": f"Finished {tool}", "approval": f"Waiting for your approval: {tool}",
                              "error": f"Task returned an error: {tool}", "cancelled": "Request stopped"}.get(state)
                    if public:
                        label = public
                        if public != getattr(self, "_last_progress", None):
                            self.activity.appendPlainText(public + ".")
                            self._last_progress = public
        except (OSError, ValueError, TypeError):
            pass
        self.activity_status.setText(f"{label} · {elapsed}s")
        if phase in labels and phase != self._last_phase:
            self.activity.appendPlainText(labels[phase] + ".")
            self._last_phase = phase

    def steer(self):
        text = self.input.toPlainText().strip()
        if not 1 <= len(text) <= 8000:
            self.status.setText("Enter 1–8000 characters to send or steer.")
            return False
        active = self.process.state() != QProcess.ProcessState.NotRunning
        interrupted = None
        previous = self._active_chat
        if (active and previous and previous["generation"] == self.request_generation
                and previous["session"] == (self.session.text() or "default")):
            interrupted = previous["text"][:4000]
        if active:
            if not self.cancel():
                return False
            self.history.appendPlainText("RE: Previous request stopped. Already completed actions and saved history remain.")
        if interrupted:
            self.send(interrupted_context=interrupted)
        else:
            self.send()
        return True

    def load_history(self):
        rows = ConversationMemory(self.home).history(self.session.text() or "default")
        self.history.setPlainText(
            "\n\n".join(f"You: {row['user']}\nREgenOS: {row['assistant']}" for row in rows)
        )

    def send(self, *, interrupted_context=None):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.status.setText("Request active. Ctrl+Enter sends this message as a correction after stopping it.")
            return
        text = self.input.toPlainText().strip()
        if not 1 <= len(text) <= 8000:
            self.status.setText("Enter 1–8000 characters.")
            return
        if interrupted_context is not None and (
            not isinstance(interrupted_context, str) or len(interrupted_context) > 4000
        ):
            self.status.setText("The interrupted-request reference is invalid; no new request was sent.")
            return
        self.cancelled = False
        session = self.session.text() or "default"
        payload = {"action": "chat", "text": text, "session": session}
        if interrupted_context:
            payload["interrupted_context"] = interrupted_context
        request = json.dumps(payload)
        # This is only the current explicit chat, never a voice transcript,
        # approval, saved conversation, model reply or earlier steering chain.
        self._active_chat = {"text": text, "session": session, "generation": self.request_generation}
        self.send_button.setEnabled(False)
        self.session.setEnabled(False)
        self.load_button.setEnabled(False)
        self.history.appendPlainText("You: " + text)
        self.input.clear()
        self.status.setText("Thinking…")
        self.process.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.process.write(request.encode())
        self.process.closeWriteChannel()
        self.timer.setInterval(150_000)
        self.timer.start()

    def speak_once(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self._active_chat = None
        config = load_raw_config(self.home)
        if config["always_listening_enabled"]:
            self.status.setText("Disable continuous listening in Voice before using Speak once.")
            return
        self.cancelled = False
        temporary_root = self.home / "run/private"
        temporary_root.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.voice_directory = tempfile.TemporaryDirectory(prefix="voice-once-", dir=temporary_root)
        env = self.process.processEnvironment()
        env.insert("AI_OS_VOICE_TMP", self.voice_directory.name)
        self.process.setProcessEnvironment(env)
        self.send_button.setEnabled(False)
        self.session.setEnabled(False)
        self.load_button.setEnabled(False)
        self.status.setText("Microphone on — speak now. Cancel request stops capture.")
        payload = json.dumps({"action": "voice_once", "confirmed": True,
                              "session": self.session.text() or "default"})
        self.process.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.process.write(payload.encode())
        self.process.closeWriteChannel()
        # Long utterances need their recording budget in addition to bounded
        # transcription, inference and playback; Cancel remains available.
        seconds = (int(config["voice_command_seconds"]) + int(config["voice_max_utterance_seconds"])
                   + 120 + 120 + 90)
        self.timer.setInterval(min(600, max(150, seconds)) * 1000)
        self.timer.start()

    def cleanup_voice(self):
        if self.voice_directory is not None:
            self.voice_directory.cleanup()
            self.voice_directory = None
            env = self.process.processEnvironment()
            env.remove("AI_OS_VOICE_TMP")
            self.process.setProcessEnvironment(env)

    def finished(self, code, _status):
        self._active_chat = None
        # A completed desktop launch may deliberately leave its application
        # running. Only an active cancellation owns descendant teardown.
        self.worker_group = None
        self.timer.stop()
        self.activity_timer.stop()
        self.mic_button.setEnabled(True)
        self.activity_status.setText("Request complete" if code == 0 else "Request ended")
        self.cleanup_voice()
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
            if result.get("recognized_text"):
                self.history.appendPlainText("Heard: " + str(result["recognized_text"])[:8000])
            reply = result["response"]
            proposal = reply.get("result", {}).get("approval_required") if reply.get("type") == "tool_result" else None
            if proposal and proposal.get("tool") == "power_action":
                self.approve_power(proposal)
                return
            if proposal and proposal.get("tool") == "cleanup_files":
                self.approve_cleanup(proposal)
                return
            if proposal and proposal.get("tool") == "research_topic":
                self.approve_research(proposal)
                return
            if proposal and proposal.get("tool") in {"write_bash", "research_page", "ask_chatgpt"}:
                self.approve_action(proposal)
                return
            if proposal and load_raw_config(self.home)["command_access"] == "supervised":
                if proposal.get("tool") == "run_terminal_command":
                    self.approve_terminal_command(proposal)
                else:
                    self.approve_command(proposal)
                return
            if reply.get("type") == "text":
                text = reply.get("content", "")
            elif reply.get("type") == "tool_result":
                from ai_os.ai_os_core import spoken_response
                text = spoken_response(reply)
            else:
                text = "The assistant returned an unsupported response."
            self.history.appendPlainText("REgenOS: " + text)
            self.status.setText("Reply received. Memory follows the saved retention setting.")
        except (ValueError, KeyError, TypeError):
            self.status.setText("The backend returned an invalid response.")

    def _start_reviewed_request(self, payload, status):
        self._active_chat = None
        self.cancelled = False
        self.send_button.setEnabled(False)
        self.session.setEnabled(False)
        self.load_button.setEnabled(False)
        self.status.setText(status)
        self.process.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.process.write(json.dumps(payload).encode())
        self.process.closeWriteChannel()
        self.timer.setInterval(150_000)
        self.timer.start()

    def refresh_pending_review(self):
        from ai_os.pending_review import read
        try:
            pending = read(self.home, self.session.text() or "default")
            self.pending_review_button.setVisible(bool(pending))
            self.pending_review_button.setEnabled(self.process.state() == QProcess.ProcessState.NotRunning)
            if pending:
                self.pending_review_button.setText("Review requested task: " + pending["tool"].replace("_", " ") + "…")
        except (OSError, ValueError, sqlite3.Error):
            self.pending_review_button.hide()

    def discard_pending_review(self, proposal):
        from ai_os.pending_review import discard
        try:
            discard(self.home, self.session.text() or "default", proposal)
        except (OSError, ValueError, sqlite3.Error):
            pass
        self.refresh_pending_review()

    def review_pending_task(self):
        from ai_os.pending_review import read
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        try:
            pending = read(self.home, self.session.text() or "default")
        except (OSError, ValueError, sqlite3.Error):
            pending = None
        if not pending:
            self.status.setText("No current pending task. Ask again if the preview expired.")
            self.refresh_pending_review()
            return False
        return {"cleanup_files": self.approve_cleanup, "research_topic": self.approve_research,
                "run_terminal_command": self.approve_terminal_command,
                "power_action": self.approve_power}[pending["tool"]](pending)

    def approve_cleanup(self, proposal):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        from ai_os.cleanup_widget import review_cleanup
        try:
            approved = review_cleanup(proposal["arguments"]["token"], self.home, self)
        except (ValueError, OSError, KeyError, TypeError):
            self.discard_pending_review(proposal)
            self.status.setText("Cleanup preview expired or changed. Request a new preview.")
            return False
        if approved is None:
            self.discard_pending_review(proposal)
            self.status.setText("Cleanup cancelled. Nothing moved.")
            return False
        self.discard_pending_review(proposal)
        self._start_reviewed_request({"action": "approved_cleanup", "confirmed": True, **approved}, "Moving reviewed files to Trash…")
        return True

    def approve_research(self, proposal):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        from ai_os.research_reports import propose_research
        try:
            arguments = propose_research(**proposal["arguments"])["approval_required"]["arguments"]
            topic, mode = arguments["topic"], arguments["mode"]
        except (KeyError, ValueError, TypeError):
            self.status.setText("Invalid research topic.")
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Research this topic online?")
        box.setTextFormat(Qt.TextFormat.PlainText)
        behavior = ("A cited source report will be saved locally because report mode was explicitly requested."
                    if mode == "report" else "Up to three relevant public source articles will be opened in your browser. No report/document will be created.")
        box.setText(f"Topic: {topic}\n\nOnly this topic and your network address go to Wikipedia and Crossref. No private history or accounts are uploaded. "
                    + behavior + " Full papers are not read or independently verified. Continue?")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.status.setText("Online research cancelled.")
            self.discard_pending_review(proposal)
            return False
        self.discard_pending_review(proposal)
        self._start_reviewed_request({"action": "approved_research", "topic": topic, "mode": mode, "confirmed": True},
                                     "Searching public sources and opening articles…" if mode == "articles" else "Compiling the explicitly requested report…")
        return True

    def approve_power(self, proposal):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        from ai_os.power_actions import power_action, command_arguments
        try:
            arguments = power_action(**proposal["arguments"])["approval_required"]["arguments"]
            action, minutes = arguments["action"], arguments["delay_minutes"]
        except (KeyError, TypeError, ValueError):
            self.status.setText("Invalid power request. Nothing was scheduled.")
            return False
        if action != "cancel" and minutes is None:
            minutes, accepted = QInputDialog.getInt(self, "When should the computer power off or restart?",
                "Delay in minutes (0 means immediately). Save your work before confirming.", 5, 0, 1440, 1)
            if not accepted:
                self.discard_pending_review(proposal)
                self.status.setText("Power request cancelled. Nothing was scheduled.")
                return False
        argv = command_arguments(action, minutes)
        box = QMessageBox(self)
        box.setWindowTitle("Confirm system power action")
        box.setTextFormat(Qt.TextFormat.PlainText)
        description = ("Cancel the system's pending shutdown/restart schedule, including one created outside REgenOS."
                       if action == "cancel" else
                       f"{'Power off' if action == 'poweroff' else 'Restart'} {'IMMEDIATELY' if minutes == 0 else 'in ' + str(minutes) + ' minute(s)'}. Save your work. Unsaved data may be lost.")
        box.setText(description + "\n\nExact command: " + shlex.join(argv)
                    + "\n\nThis is a system action. OS permissions and inhibitors still apply. Chat Stop will not cancel an accepted schedule. "
                      "To cancel a future schedule, request Cancel scheduled shutdown. Confirm this exact action?")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.discard_pending_review(proposal)
            self.status.setText("Power action denied. Nothing was scheduled.")
            return False
        self.discard_pending_review(proposal)
        self._start_reviewed_request({"action": "approved_power", "power_action": action,
                                     "delay_minutes": minutes, "confirmed": True}, "Submitting the exact reviewed power request…")
        return True

    def approve_terminal_command(self, proposal):
        if (proposal.get("tool") != "run_terminal_command"
                or self.process.state() != QProcess.ProcessState.NotRunning
                or load_raw_config(self.home)["command_access"] != "supervised"):
            return False
        from ai_os.terminal_tasks import propose_terminal_command
        try:
            arguments = propose_terminal_command(**proposal["arguments"])["approval_required"]["arguments"]
        except (ValueError, TypeError, KeyError, OSError):
            self.status.setText("Command cannot be reviewed. Check the exact binary, directory and safety restrictions.")
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Run this exact command in a terminal?")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(
            f"Command: {shlex.join(arguments['command'])}\n"
            f"Working directory: {arguments['cwd']}\n"
            f"Time limit: {arguments['timeout_sec']} seconds\n\n"
            "This starts a visible terminal. Ordinary commands have access to your account; "
            "sudo elevates the reviewed program. Enter any sudo password only in that terminal. "
            "Sudo uses the fixed /usr/bin/timeout helper for the foreground command deadline. "
            "Privileged or background descendants cannot be guaranteed contained. "
            "Command output is not saved in chat. Review every argument before continuing."
        )
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.status.setText("Terminal command denied.")
            self.discard_pending_review(proposal)
            return False
        self.discard_pending_review(proposal)
        payload = json.dumps({"action": "approved_terminal_command", "arguments": arguments, "confirmed": True})
        self.send_button.setEnabled(False)
        self.session.setEnabled(False)
        self.load_button.setEnabled(False)
        self.status.setText("Requesting the reviewed terminal…")
        self.process.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.process.write(payload.encode())
        self.process.closeWriteChannel()
        self.timer.setInterval(150_000)
        self.timer.start()
        return True

    def approve_command(self, proposal):
        if proposal.get("tool") != "run_command":
            return False
        arguments = dict(proposal["arguments"])
        cwd = arguments.get("cwd")
        if cwd is not None and (not isinstance(cwd, str) or not cwd.isprintable() or len(cwd) > 4096):
            raise ValueError("Invalid working directory")
        arguments["cwd"] = str(Path(cwd).expanduser().resolve()) if cwd else str(Path.home())
        from ai_os.tools.system_tools import assess_command, RiskLevel
        assessment = assess_command(arguments.get("command", []))
        if assessment.risk == RiskLevel.PROHIBITED:
            return False
        from ai_os.power_actions import command_proposal
        try:
            power = command_proposal(assessment.command)
        except ValueError:
            self.status.setText("Unsupported power flags. Ask for a reviewed shutdown/restart time instead.")
            return False
        if power is not None:
            return self.approve_power(power["approval_required"])
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

    def ask_browser_ai(self):
        self.approve_action({"tool": "ask_chatgpt", "arguments": {"prompt": self.input.toPlainText()}})

    def research_page(self):
        url, accepted = QInputDialog.getText(self, "Research a public page", "HTTPS URL")
        if accepted:
            self.approve_action({"tool": "research_page", "arguments": {"url": url}})

    def approve_action(self, proposal):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        from ai_os.reviewed_actions import validate
        tool, arguments = proposal.get("tool"), proposal.get("arguments")
        try:
            if tool != "chatgpt_login":
                validate(tool, arguments)
            elif arguments != {}:
                raise ValueError("Login does not accept arguments")
            if tool != "write_bash" and not load_raw_config(self.home)["browser_enabled"]:
                raise ValueError("Enable reviewed browser tools in Permissions first")
        except (ValueError, TypeError):
            self.status.setText("Invalid action or browser tools disabled. Check Permissions and the exact input.")
            return False
        description = {
            "write_bash": "Save this exact Bash source as a new private draft. It will be syntax-checked, not executed.",
            "research_page": "Load this exact public HTTPS URL in a separate browser and extract page text. The URL is sent online; no personal browser profile is used.",
            "ask_chatgpt": "Send this exact prompt to ChatGPT through its website, using the separate RE browser profile. This shares the text with an external provider. Submission is not automatically retried.",
            "chatgpt_login": "Open a separate Brave profile at chatgpt.com for up to 110 seconds. Sign in directly in that browser, then close it. Cookies stay in RE's private runtime; your usual browser profile is not imported.",
        }[tool]
        box = QMessageBox(self)
        box.setWindowTitle("Review exact action")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(description + "\n\n" + json.dumps(arguments, ensure_ascii=True, indent=2))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            self.status.setText("Action denied.")
            return False
        self.cancelled = False
        self.send_button.setEnabled(False)
        self.session.setEnabled(False)
        self.load_button.setEnabled(False)
        self.status.setText("Running reviewed action…")
        payload = json.dumps({"action": "reviewed_action", "tool": tool, "arguments": arguments, "confirmed": True})
        self.process.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.process.write(payload.encode())
        self.process.closeWriteChannel()
        self.timer.start()
        return True

    def refresh_grant(self):
        self.refresh_pending_review()
        try:
            state = GrantStore(self.home).status(self.session.text() or "default")
            grant = state.get("grant")
            label = "No temporary access grant"
            if grant:
                remaining = max(0, int(min(grant["deadline"]-time.monotonic(), grant["wall_deadline"]-time.time())))
                label = f"{grant['kind'].capitalize()} access: {remaining}s remaining — this session"
            if "command" in state:
                label += " · Command awaiting your review"
            if "request" in state:
                label += " · Access request awaiting your review"
            self.access_status.setText(label)
            self.confirm_grant_button.setEnabled(bool({"request", "command"} & state.keys()) and self.process.state() == QProcess.ProcessState.NotRunning)
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
        if load_raw_config(self.home)["command_access"] != "supervised":
            self.status.setText("Enable supervised command access in Permissions to review actions.")
            return False
        state = GrantStore(self.home).status(self.session.text() or "default")
        request = state.get("request")
        if not request and "command" in state:
            return self.approve_command({"tool": "run_command", "arguments": state["command"]["spec"]})
        if not request:
            self.refresh_grant()
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Confirm temporary command access")
        box.setTextFormat(Qt.TextFormat.PlainText)
        from ai_os.tools.system_tools import assess_command
        description = USER_SCOPE if request["kind"] == "user" else SCOPE if request["kind"] == "timed" else (
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

    def request_user_access(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        if load_raw_config(self.home)["command_access"] != "supervised":
            self.status.setText("Enable supervised command access in Permissions first.")
            return
        minutes, accepted = QInputDialog.getInt(
            self, "Broad user access", "Duration in minutes (this conversation session):", 15, 1, 1440,
        )
        if accepted:
            GrantStore(self.home).request(self.session.text() or "default", {
                "kind": "user", "seconds": minutes * 60,
            })
            self.confirm_grant()

    def failed(self, _error):
        self._active_chat = None
        self.timer.stop()
        self.activity_timer.stop()
        if self.process.state() == QProcess.ProcessState.NotRunning:
            self.cleanup_voice()
        self.send_button.setEnabled(True)
        self.mic_button.setEnabled(True)
        self.session.setEnabled(True)
        self.load_button.setEnabled(True)
        if not self.cancelled:
            self.status.setText("Could not run the Python backend.")
            self.activity_status.setText("Backend unavailable")

    def cancel(self):
        self._active_chat = None
        self.cancelled = True
        self.timer.stop()
        self.activity_timer.stop()
        process = self.process
        if process.state() != QProcess.ProcessState.NotRunning:
            # Block synchronous and already queued callbacks from the old request.
            # New requests get a separate QProcess and generation guard as well.
            process.blockSignals(True)
            self._remember_worker_group(process)
            if not self._signal_worker_group(signal.SIGTERM):
                process.terminate()
            if not process.waitForFinished(3000):
                self._signal_worker_group(signal.SIGKILL)
                process.kill()
            if process.state() != QProcess.ProcessState.NotRunning and not process.waitForFinished(2000):
                self.status.setText("The previous backend has not stopped. A new request was not started.")
                self.activity_status.setText("Waiting for the previous backend to exit")
                return False
        self._signal_worker_group(signal.SIGKILL)
        self.worker_group = None
        self.cleanup_voice()
        process.blockSignals(True)
        self._new_process()
        process.deleteLater()
        self.send_button.setEnabled(True)
        self.mic_button.setEnabled(True)
        self.session.setEnabled(True)
        self.load_button.setEnabled(True)
        self.activity_status.setText("Stopped")
        self.status.setText("Request stopped. Already completed actions and saved history remain.")
        return True
