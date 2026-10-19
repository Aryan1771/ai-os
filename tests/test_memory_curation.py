"""Synthetic human-only long-term curation; never reads a private runtime."""
from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from ai_os.conversation_memory import ConversationMemory
from ai_os.memory_widget import MemoryWidget


def test_pinning_keeps_only_user_statement_and_survives_recent_history_clear(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("Copper Finch is my preferred project codename", "I invented a secret second codename", "work")
    turn = memory.recent_user_statements("work")[0]
    assert "assistant" not in turn
    note_id = memory.pin_user_statement(turn["id"], "Project codename", session="work")
    memory.clear_history("work")
    note = memory.notes()[0]
    assert note["id"] == note_id and note["body"] == turn["user"]
    assert "invented" not in note["body"]
    assert memory.history("work") == []
    assert "Copper Finch" in str(memory.context("What is my project codename?", session="work"))


def test_statement_pinning_rejects_wrong_session_missing_and_expired_sources(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("My important synthetic preference", "Okay", "private-session")
    turn_id = memory.recent_user_statements("private-session")[0]["id"]
    with pytest.raises(ValueError, match="unavailable or expired"):
        memory.pin_user_statement(turn_id, "Preference", session="other-session")
    with pytest.raises(ValueError, match="unavailable or expired"):
        memory.pin_user_statement(turn_id + 1, "Preference", session="private-session")
    with memory.connect() as db:
        db.execute("UPDATE turns SET created=?", (time.time() - 400 * 86400,))
    assert memory.recent_user_statements("private-session") == []
    with pytest.raises(ValueError, match="unavailable or expired"):
        memory.pin_user_statement(turn_id, "Preference", session="private-session")
    assert memory.notes() == []


def test_pin_obeys_note_capacity_without_losing_source(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("An important synthetic statement", "Okay")
    turn_id = memory.recent_user_statements()[0]["id"]
    with memory.connect() as db:
        db.executemany("INSERT INTO notes(title,body,updated) VALUES(?,?,?)",
                       [(f"Note {i}", "Synthetic", time.time()) for i in range(256)])
    with pytest.raises(ValueError, match="limited to 256"):
        memory.pin_user_statement(turn_id, "Too many notes")
    assert len(memory.notes()) == 256
    assert len(memory.history()) == 1


@pytest.mark.parametrize("operation", ["pin", "edit", "delete"])
def test_stale_inspection_cannot_pin_edit_or_remove_records(tmp_path, operation):
    memory = ConversationMemory(tmp_path)
    memory.append("A synthetic project statement", "Okay")
    turn_id = memory.recent_user_statements()[0]["id"]
    note_id = memory.put("Original", "Original body")
    old_revision = memory.revision()
    memory.forget("unrelated text")
    with pytest.raises(ValueError, match="changed since inspection"):
        if operation == "pin":
            memory.pin_user_statement(turn_id, "Project", expected_revision=old_revision)
        elif operation == "edit":
            memory.put("Edited", "Changed body", note_id, expected_revision=old_revision)
        else:
            memory.delete_note(note_id, expected_revision=old_revision)
    assert len(memory.notes()) == 1
    assert memory.notes()[0]["body"] == "Original body"


def test_note_correction_invalidates_late_reply_and_exact_remove_keeps_source(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("The project uses an old codename", "Okay")
    turn_id = memory.recent_user_statements()[0]["id"]
    note_id = memory.pin_user_statement(turn_id, "Project")
    revision = memory.revision()
    memory.put("Project", "The corrected codename is Copper Finch", note_id, expected_revision=revision)
    memory.append("Late stale request", "The old codename remains", expected_revision=revision)
    assert len(memory.history()) == 1
    assert memory.notes()[0]["body"] == "The corrected codename is Copper Finch"
    memory.delete_note(note_id, expected_revision=memory.revision())
    assert memory.notes() == []
    assert len(memory.history()) == 1
    with pytest.raises(ValueError, match="no longer exists"):
        memory.delete_note(note_id)


def _choose(widget, kind):
    for index in range(widget.records.count()):
        identity = widget.records.itemData(index)
        if identity and identity[0] == kind:
            widget.records.setCurrentIndex(index)
            return identity
    raise AssertionError("No appropriate inspected record")


@pytest.fixture
def memory_ui(tmp_path):
    app = QApplication.instance() or QApplication(["memory-curation-test"])
    widget = MemoryWidget(tmp_path)
    yield widget
    widget.close()
    app.processEvents()


def test_native_pin_is_hidden_until_inspection_and_requires_default_no_confirmation(memory_ui, monkeypatch):
    widget = memory_ui
    memory = ConversationMemory(widget.home)
    memory.append("My project codename is Copper Finch", "Assistant guess is a different codename")
    assert widget.output.toPlainText() == ""
    assert widget.records.count() == 1
    assert not widget.pin_button.isEnabled() and not widget.edit_button.isEnabled()
    widget.inspect()
    _choose(widget, "statement")
    assert widget.pin_button.isEnabled() and not widget.edit_button.isEnabled()
    assert widget.value.toPlainText() == "My project codename is Copper Finch"
    questions = []

    def reject(*args):
        questions.append(args)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", reject)
    widget.pin_statement()
    assert questions[0][-1] == QMessageBox.StandardButton.No
    assert memory.notes() == []
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    widget.value.setPlainText("An edited draft must not replace the selected source")
    widget.pin_statement()
    assert memory.notes()[0]["body"] == "My project codename is Copper Finch"
    assert not widget.pin_button.isEnabled()


def test_native_edit_and_remove_apply_only_to_selected_note(memory_ui, monkeypatch):
    widget = memory_ui
    memory = ConversationMemory(widget.home)
    first = memory.put("First", "Original first")
    second = memory.put("Second", "Original second")
    widget.inspect()
    for index in range(widget.records.count()):
        if widget.records.itemData(index) == ("note", first):
            widget.records.setCurrentIndex(index)
            break
    widget.value.setPlainText("Corrected first")
    widget.edit_note()
    notes = {row["id"]: row["body"] for row in memory.notes()}
    assert notes == {first: "Corrected first", second: "Original second"}
    widget.inspect()
    chosen = _choose(widget, "note")[1]
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    widget.remove_note()
    assert len(memory.notes()) == 2
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    widget.remove_note()
    assert chosen not in {row["id"] for row in memory.notes()}
    assert len(memory.notes()) == 1


def test_native_pin_fails_if_session_changed_or_source_forgotten(memory_ui, monkeypatch):
    widget = memory_ui
    memory = ConversationMemory(widget.home)
    memory.append("Synthetic codename Copper Finch", "Okay")
    widget.inspect()
    _choose(widget, "statement")
    widget.session.setCurrentText("different")
    with pytest.raises(ValueError, match="session changed"):
        widget.pin_statement()
    widget.session.setCurrentText("default")
    memory.forget("Copper Finch")
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    with pytest.raises(ValueError, match="changed since inspection"):
        widget.pin_statement()
    assert memory.notes() == [] and memory.history() == []
