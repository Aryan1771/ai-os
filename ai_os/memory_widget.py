"""Human-operated local memory inspector. Never exposed as a model approval tool."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_os.conversation_memory import ConversationMemory


class MemoryWidget(QWidget):
    def __init__(self, home: Path, parent=None):
        super().__init__(parent)
        self.home = home
        layout = QVBoxLayout(self)
        notice = QLabel(
            "Local memory is not model training. Inspect explicitly before sharing your screen. "
            "Forget removes matching active records, including conversation turns; backups and legacy stores are separate."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        form = QFormLayout()
        self.session = QComboBox()
        self.session.setEditable(True)
        self.session.addItem("default")
        form.addRow("Session", self.session)
        self.key = QLineEdit()
        self.value = QPlainTextEdit()
        self.value.setMaximumHeight(80)
        form.addRow("Preference key / note title", self.key)
        form.addRow("Value / note text", self.value)
        layout.addLayout(form)
        for label, action in [
            ("Inspect selected session", self.inspect),
            ("Remember preference", self.remember),
            ("Save context note", self.note),
            ("Forget matching text", self.forget),
            ("Clear selected session", self.clear_session),
            ("Clear all active memory", self.clear_all),
        ]:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, fn=action: self.perform(fn))
            layout.addWidget(button)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Memory is hidden until you choose Inspect.")
        layout.addWidget(self.output)

    def perform(self, action):
        try:
            action()
        except (OSError, ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Memory operation failed", str(exc))

    def store(self):
        return ConversationMemory(self.home)

    def inspect(self):
        memory = self.store()
        current = self.session.currentText() or "default"
        self.session.clear()
        self.session.addItems(sorted(set(memory.sessions()) | {"default", current}))
        self.session.setCurrentText(current)
        self.output.setPlainText(
            json.dumps(
                {
                    "history": memory.history(current),
                    "notes": memory.notes(),
                    "preferences": memory.preferences(),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    def remember(self):
        self.store().remember(self.key.text(), self.value.toPlainText())
        self.output.setPlainText("Preference saved locally.")

    def note(self):
        self.store().put(self.key.text(), self.value.toPlainText())
        self.output.setPlainText("Context note saved locally.")

    def confirmed(self, message):
        return (
            QMessageBox.question(
                self,
                "Delete local memory",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def forget(self):
        text = self.value.toPlainText().strip()
        if not text:
            raise ValueError("Enter the literal text to forget in the value field.")
        if self.confirmed(
            "Delete active turns, notes and preferences containing this text? Backups are retained."
        ):
            count = self.store().forget(text)
            self.output.setPlainText(f"Deleted {count} active records.")
            self.value.clear()

    def clear_session(self):
        if self.confirmed(
            "Delete history for the selected session? Notes and preferences are retained."
        ):
            self.store().clear_history(self.session.currentText() or "default")
            self.output.setPlainText("Session history deleted.")

    def clear_all(self):
        if self.confirmed(
            "Delete ALL active conversation history, notes and preferences? Backups and legacy stores are retained."
        ):
            self.store().clear_all()
            self.output.setPlainText("Active memory deleted.")
