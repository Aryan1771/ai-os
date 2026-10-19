"""Trusted native review for recoverable cleanup; no model approval flags."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QListWidget, QPushButton, QVBoxLayout, QMessageBox

from ai_os.file_cleanup import read_preview, list_rules, forget_rules


def review_cleanup(token, home, parent=None):
    spec = read_preview(token, home)
    dialog = QDialog(parent)
    dialog.setWindowTitle("Review files to move to Trash")
    dialog.resize(680, 500)
    layout = QVBoxLayout(dialog)
    title = QLabel(f"{len(spec['files'])} files · {spec['bytes']} bytes\n{spec['directory']}\nPattern: {spec['pattern']}")
    title.setTextFormat(Qt.TextFormat.PlainText)
    title.setWordWrap(True)
    layout.addWidget(title)
    files = QListWidget()
    files.addItems([f"{item['name']}   ({item['size']} bytes)" for item in spec["files"]])
    layout.addWidget(files)
    notice = QLabel("Review every filename. RE cannot prove that these files are unimportant. This moves them to desktop Trash for recovery; it does not permanently erase them. Hidden files, directories, symlinks, repositories and environments are excluded.")
    notice.setWordWrap(True)
    layout.addWidget(notice)
    remember = QCheckBox(f"Allow this exact directory + pattern again for 30 days / 20 uses (up to {max(10, len(spec['files']))} files and {max(10 * 1024 ** 2, spec['bytes'])} bytes per request)")
    remember.setChecked(False)
    layout.addWidget(remember)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Move these files to Trash")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return {"token": token, "remember": remember.isChecked()}


def show_cleanup_rules(home, parent=None):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Remembered cleanup permissions")
    dialog.resize(680, 400)
    layout = QVBoxLayout(dialog)
    notice = QLabel("Only these explicitly approved directory + pattern rules can skip another cleanup confirmation. They expire after 30 days or 20 uses. Requests stay recoverable through desktop Trash.")
    notice.setWordWrap(True)
    layout.addWidget(notice)
    rules = QListWidget()
    layout.addWidget(rules)
    def refresh():
        rules.clear()
        rules.addItems([f"{rule['directory']} / {rule['pattern']} · {rule['uses']} uses left" for rule in list_rules(home)])
        if rules.count() == 0:
            rules.addItem("No remembered cleanup permissions.")
    refresh()
    forget = QPushButton("Forget all cleanup permissions…")
    def clear():
        if QMessageBox.question(dialog, "Forget cleanup permissions?", "Future cleanup requests will need a new file preview and confirmation.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            forget_rules(home, human_confirmed=True)
            refresh()
    forget.clicked.connect(clear)
    layout.addWidget(forget)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
