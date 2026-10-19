"""Human-operated local memory inspector. Never exposed as a model approval tool."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
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
            "Recent history expires; preferences and context notes are shared across sessions and persist until edited or forgotten. "
            "Pin important user statements explicitly; repetition does not establish truth. "
            "Forget removes matching active records; backups and legacy stores are separate."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        form = QFormLayout()
        self.session = QComboBox()
        self.session.setEditable(True)
        self.session.addItem("default")
        form.addRow("Session", self.session)
        self.records = QComboBox()
        self.records.setAccessibleName("Inspected memory record")
        self.records.addItem("Hidden until you choose Inspect", None)
        self.records.currentIndexChanged.connect(self.load_selected)
        self.inspected_revision = None
        self.inspected_records = {}
        form.addRow("Inspected record", self.records)
        self.key = QLineEdit()
        self.value = QPlainTextEdit()
        self.value.setMaximumHeight(80)
        form.addRow("Preference key / note title", self.key)
        form.addRow("Value / note text", self.value)
        layout.addLayout(form)
        curation = QHBoxLayout()
        self.pin_button = QPushButton("Pin user statement")
        self.pin_button.setToolTip("Pins the original user statement; use Save context note for edited text.")
        self.edit_button = QPushButton("Save note edits")
        self.remove_button = QPushButton("Remove note")
        for button, action in ((self.pin_button, self.pin_statement),
                               (self.edit_button, self.edit_note),
                               (self.remove_button, self.remove_note)):
            button.setEnabled(False)
            button.clicked.connect(lambda _checked=False, fn=action: self.perform(fn))
            curation.addWidget(button)
        layout.addLayout(curation)
        actions = QGridLayout()
        for index, (label, action) in enumerate([
            ("Inspect selected session", self.inspect),
            ("Remember preference", self.remember),
            ("Save context note", self.note),
            ("Forget matching text", self.forget),
            ("Clear selected session", self.clear_session),
            ("Clear conversations, notes and preferences", self.clear_all),
            ("Inspect app usage", self.inspect_activity),
            ("Clear app usage", self.clear_activity),
        ]):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, fn=action: self.perform(fn))
            actions.addWidget(button, index // 2, index % 2)
        layout.addLayout(actions)
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
        # Capture before the reads: a concurrent forget/edit invalidates any
        # subsequent curation instead of promoting a stale inspected copy.
        self.inspected_revision = memory.revision()
        history = memory.history(current)
        notes = memory.notes()
        statements = memory.recent_user_statements(current)
        self.session.clear()
        self.session.addItems(sorted(set(memory.sessions()) | {"default", current}))
        self.session.setCurrentText(current)
        self.inspected_session = current
        self.inspected_records = {}
        with QSignalBlocker(self.records):
            self.records.clear()
            self.records.addItem("Choose a note or user statement", None)
            for note in notes:
                identity = ("note", note["id"])
                self.inspected_records[identity] = note
                self.records.addItem("Long-term note · " + note["title"], identity)
            for statement in statements:
                identity = ("statement", statement["id"])
                self.inspected_records[identity] = statement
                stamp = datetime.fromtimestamp(statement["created"]).strftime("%Y-%m-%d %H:%M")
                excerpt = " ".join(statement["user"].split())[:65]
                self.records.addItem(f"User statement · {stamp} · {excerpt}", identity)
        self.load_selected()
        self.output.setPlainText(
            json.dumps(
                {
                    "history": history,
                    "notes": notes,
                    "preferences": memory.preferences(),
                    "reinforced": memory.reinforced(current),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    def load_selected(self, _index=None):
        identity = self.records.currentData()
        record = self.inspected_records.get(identity)
        note = bool(record and identity[0] == "note")
        statement = bool(record and identity[0] == "statement")
        self.pin_button.setEnabled(statement)
        self.edit_button.setEnabled(note)
        self.remove_button.setEnabled(note)
        if record:
            self.key.setText(record["title"] if note else "Important user statement")
            self.value.setPlainText(record["body"] if note else record["user"])

    def invalidate_selection(self):
        self.inspected_records = {}
        self.inspected_revision = None
        self.records.clear()
        self.records.addItem("Inspect again to choose a memory", None)
        self.load_selected()

    def selected(self, kind):
        identity = self.records.currentData()
        if not identity or identity[0] != kind or identity not in self.inspected_records:
            raise ValueError("Inspect memory and choose the appropriate record first.")
        if (self.session.currentText() or "default") != self.inspected_session:
            raise ValueError("The selected session changed. Inspect it again before saving.")
        return identity[1]

    def pin_statement(self):
        turn_id = self.selected("statement")
        if not self.confirmed(
            "Keep the original selected user statement as a long-term context note? "
            "It will be shared across sessions and remain until edited or forgotten, without further repetition. "
            "This does not verify its truth or grant any permission.", title="Keep important memory"
        ):
            return
        note_id = self.store().pin_user_statement(
            turn_id, self.key.text(), session=self.inspected_session,
            expected_revision=self.inspected_revision,
        )
        self.invalidate_selection()
        self.output.setPlainText(f"User statement saved as long-term note #{note_id}. Inspect to edit or remove it.")

    def edit_note(self):
        note_id = self.selected("note")
        self.store().put(self.key.text(), self.value.toPlainText(), note_id,
                         expected_revision=self.inspected_revision)
        self.invalidate_selection()
        self.output.setPlainText(f"Long-term note #{note_id} updated. Inspect to view the saved version.")

    def remove_note(self):
        note_id = self.selected("note")
        if self.confirmed(
            "Remove this selected long-term note? Original conversation turns and backups remain. "
            "Use Forget matching text to remove matching active source records too."
        ):
            self.store().delete_note(note_id, expected_revision=self.inspected_revision)
            self.invalidate_selection()
            self.key.clear()
            self.value.clear()
            self.output.setPlainText(f"Long-term note #{note_id} removed; source history was retained.")

    def remember(self):
        self.store().remember(self.key.text(), self.value.toPlainText())
        self.invalidate_selection()
        self.output.setPlainText("Preference saved locally.")

    def inspect_activity(self):
        from ai_os.activity_memory import ActivityMemory
        self.output.setPlainText(json.dumps(ActivityMemory(self.home).summary(), indent=2))

    def clear_activity(self):
        from ai_os.activity_memory import ActivityMemory
        if self.confirmed("Delete recorded app usage? Disable app usage memory to stop future collection."):
            ActivityMemory(self.home).clear()
            self.output.setPlainText("Recorded app usage cleared.")

    def note(self):
        self.store().put(self.key.text(), self.value.toPlainText())
        self.invalidate_selection()
        self.output.setPlainText("Context note saved locally.")

    def confirmed(self, message, *, title="Delete local memory"):
        return (
            QMessageBox.question(
                self,
                title,
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
            self.invalidate_selection()
            self.output.setPlainText(f"Deleted {count} active records.")
            self.value.clear()

    def clear_session(self):
        if self.confirmed(
            "Delete history for the selected session? Notes and preferences are retained."
        ):
            self.store().clear_history(self.session.currentText() or "default")
            self.invalidate_selection()
            self.output.setPlainText("Session history deleted.")

    def clear_all(self):
        if self.confirmed(
            "Delete all conversation history, notes and preferences? App usage has its own Clear button; backups and legacy stores are retained."
        ):
            self.store().clear_all()
            self.invalidate_selection()
            self.output.setPlainText("Active memory deleted.")
