"""Native post-install onboarding. No disk installer, downloads or sensor activation."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time

from ai_os.config import AI_OS_HOME, DEFAULT_CONFIG, atomic_json

CHOICE_KEYS = {"whisper_language", "reply_language_mode", "companion_personality"}
SETTINGS_PAGES = {"ai": "AI connection", "voice": "Voice & listening",
                  "companion": "Companion", "memory": "Memory", "permissions": "Permissions"}


def read_preferences(home: Path) -> dict:
    """Read only the selected runtime's settings, without initializing its tree."""
    try:
        with (home / "config.json").open("r", encoding="utf-8") as handle:
            text = handle.read(65537)
    except FileNotFoundError:
        return deepcopy(DEFAULT_CONFIG)
    if len(text) > 65536:
        raise ValueError("Runtime preferences need review in Settings.")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Runtime preferences need review in Settings.")
    return deepcopy(DEFAULT_CONFIG) | value


def completion_path(home: Path) -> Path:
    return home / "data/private/first-run.json"


def live_session() -> bool:
    return os.environ.get("REGENOS_LIVE_SESSION") == "1" or Path("/run/archiso").exists()


def setup_needed(home: Path = AI_OS_HOME, *, live: bool | None = None) -> bool:
    if live_session() if live is None else live:
        return False
    path = completion_path(home)
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 2048:
            return True
        data = json.loads(path.read_text(encoding="utf-8"))
        return not (isinstance(data, dict) and type(data.get("version")) is int and data.get("version") == 1 and data.get("completed") is True
                    and type(data.get("completed_at")) is int
                    and 0 < data["completed_at"] <= time.time() + 300)
    except (OSError, ValueError, TypeError):
        return True


def complete_setup(home: Path, changes: dict | None = None, *, human_confirmed=False,
                   baseline: dict | None = None, live: bool | None = None) -> None:
    """Trusted Finish only; preserve unrelated preferences and private stores."""
    if human_confirmed is not True:
        raise PermissionError("Choose Finish setup explicitly to save onboarding.")
    if live_session() if live is None else live:
        raise PermissionError("Live preview setup cannot mark an installed system complete.")
    changes = {} if changes is None else changes
    if not isinstance(changes, dict) or set(changes) - CHOICE_KEYS:
        raise ValueError("Setup only changes conversation language and personality.")
    from ai_os.settings_store import save_settings, validate_setting

    validated = {key: validate_setting(key, value) for key, value in changes.items()}
    if validated and (home / "config.json").is_symlink():
        raise ValueError("The preference destination needs review before setup can change it.")
    current = read_preferences(home)
    if baseline is not None and any(current.get(key) != baseline.get(key) for key in validated):
        raise ValueError("A selected preference changed elsewhere. Reopen setup to review it.")
    path = completion_path(home)
    for directory in (home, home / "data", path.parent):
        if directory.is_symlink() or directory.exists() and not directory.is_dir():
            raise ValueError("The setup destination needs review; nothing was marked complete.")
    if path.is_symlink() or path.exists() and not path.is_file():
        raise ValueError("The setup marker needs review; nothing was marked complete.")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        path.parent.chmod(0o700)
    if validated:
        save_settings(validated, home)
    atomic_json(path, {"version": 1, "completed": True, "completed_at": int(time.time())})
    if os.name == "posix":
        path.chmod(0o600)


def readiness_snapshot(home: Path) -> dict:
    """Static presence checks only: no process, network, inference or capture."""
    config = read_preferences(home)

    def asset(key):
        value = config.get(key)
        if not isinstance(value, str) or not value:
            return False
        path = Path(value).expanduser()
        return (path if path.is_absolute() else home / path).is_file()

    items = [
        ("Python 3.12+", sys.version_info >= (3, 12)),
        ("Virtual environment", sys.prefix != sys.base_prefix),
        ("Ollama executable", bool(shutil.which("ollama"))),
        ("Microphone recorder", bool(shutil.which("pw-record"))),
        ("Audio playback", bool(shutil.which("pw-play"))),
        ("Whisper executable", bool(shutil.which(str(config.get("whisper_cli", ""))))),
        ("Whisper model file", asset("whisper_model")),
        ("Piper executable", Path(sys.executable).with_name("piper").is_file() or bool(shutil.which("piper"))),
        ("English voice model", asset("piper_model")),
        ("Hindi voice model (optional)", asset("piper_hindi_model")),
    ]
    return {"ok": True, "scope": "static_presence_only",
            "items": [{"name": name, "present": bool(present)} for name, present in items],
            "message": "Presence only. Model service/inference, microphone, sound, language accuracy and desktop behavior are not verified."}


def create_wizard(home: Path = AI_OS_HOME, *, live: bool | None = None):
    from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel,
                                  QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                                  QWizard, QWizardPage)
    from ai_os.brand_assets import brand_icon
    from ai_os.native_widgets import theme_stylesheet

    home = Path(home)
    preview = live_session() if live is None else live

    class SetupWizard(QWizard):
        def __init__(self):
            super().__init__()
            self.home, self.preview = home, preview
            self.worker = None
            self.worker_output = bytearray()
            self.settings_window = None
            self.load_error = False
            try:
                self.initial = read_preferences(home)
            except (OSError, ValueError, TypeError):
                self.initial = deepcopy(DEFAULT_CONFIG)
                self.load_error = True
            self.setWindowTitle("REgenOS Setup" + (" — live preview" if preview else ""))
            self.setWindowIcon(brand_icon())
            self.resize(900, 650)
            self.setMinimumSize(720, 540)
            self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
            self.setStyleSheet(theme_stylesheet("graphite") + "QWizardPage { background: #171d29; } QLabel#setupHero { color: #69c8ff; font-size: 27px; font-weight: 600; }")
            self.setButtonText(QWizard.WizardButton.NextButton, "Continue")
            self.setButtonText(QWizard.WizardButton.CancelButton, "Do this later")
            self.setButtonText(QWizard.WizardButton.FinishButton, "Close preview" if preview else "Finish setup")

            page, layout = self.make_page("Welcome to REgenOS", "A calmer, local AI workspace.")
            mark = QLabel()
            mark.setPixmap(brand_icon().pixmap(100, 100))
            layout.addWidget(mark)
            hero = QLabel("Make this workspace yours.")
            hero.setObjectName("setupHero")
            layout.addWidget(hero)
            layout.addWidget(self.text("Meet RE, choose how you converse, and see what is available locally. "
                "You stay in control of listening, screen access and computer actions."))
            layout.addWidget(self.text("This is post-install setup for the native REgenOS runtime. "
                "It does not install an operating system, partition a disk, change boot settings or download models."))
            if preview:
                layout.addWidget(self.text("Live preview: choices and completion are not saved. "
                    "The graphical disk installer is a separate, currently unvalidated Calamares integration."))
            layout.addStretch()
            self.addPage(page)

            page, layout = self.make_page("Your conversation", "Choose presentation preferences, not permissions.")
            form = QFormLayout()
            self.language = self.combo((("en", "English"), ("hi", "हिन्दी / Hindi"),
                                        ("auto", "Automatic speech language")), self.initial["whisper_language"])
            self.reply_mode = self.combo((("selected", "Use my selected language"), ("match", "Match each English / Hindi message")), self.initial["reply_language_mode"])
            self.personality = self.combo(tuple((key, key.capitalize()) for key in ("warm", "calm", "playful", "focused")), self.initial["companion_personality"])
            for label, control in (("Speech / fallback language", self.language), ("Reply language", self.reply_mode), ("RE's conversation style", self.personality)):
                form.addRow(label, control)
                control.setEnabled(not preview)
            layout.addLayout(form)
            layout.addWidget(self.text("Choose the tone that suits you. These preferences can be changed later. "
                "Voice quality depends on installed transcription and voice assets."))
            layout.addStretch()
            self.initial_choices = self.choices()
            self.addPage(page)

            page, layout = self.make_page("Your permissions, your choice", "Setup does not switch these features on.")
            for title, detail in (
                ("Listening is a deliberate choice", "Continuous listening and wake-word activation require separate explicit controls. Speaker matching is not command or login authorization."),
                ("Screen context stays under your control", "Screen sharing needs its own approval and screen selection. Context is temporary, local and cannot authorize actions."),
                ("Computer actions have boundaries", "Command grants and privileged operations require their own review. Setup grants no access and changes no system service."),
                ("Memory is context, not training", "Existing memory, online-provider and sharing choices are preserved. You can inspect or forget active local records in Settings."),
            ):
                heading = QLabel(title)
                heading.setStyleSheet("font-weight: 600; color: #69c8ff;")
                layout.addWidget(heading)
                layout.addWidget(self.text(detail))
            self.acknowledge = QCheckBox("I understand that permissions are reviewed separately.")
            page.registerField("boundaries_understood*", self.acknowledge)
            layout.addWidget(self.acknowledge)
            self.addPage(page)

            page, layout = self.make_page("Check what is installed", "A read-only inventory; no microphone, model request or screen capture.")
            self.check_button = QPushButton("Check installed runtime")
            self.check_button.clicked.connect(self.start_inventory)
            layout.addWidget(self.check_button)
            self.inventory = QTreeWidget()
            self.inventory.setHeaderLabels(["Component", "Presence"])
            self.inventory.setRootIsDecorated(False)
            layout.addWidget(self.inventory, 1)
            self.inventory_status = self.text("Not checked. Missing assets can be provisioned later with separate approval; nothing downloads automatically.")
            layout.addWidget(self.inventory_status)
            self.addPage(page)

            page, layout = self.make_page("Explore your workspace", "Open native tools when you are ready.")
            for key, label in (("ai", "Review AI connection"), ("voice", "Set up voice and listening"),
                               ("companion", "Customize RE and screen access"), ("memory", "Review memory controls"),
                               ("permissions", "Review command permissions")):
                button = QPushButton(label)
                button.clicked.connect(lambda _checked=False, key=key: self.open_settings(key))
                layout.addWidget(button)
            actions = QHBoxLayout()
            for module, label in (("ai_os.quick_chat", "Open RE Chat"), ("ai_os.research_widget", "Open Research")):
                button = QPushButton(label)
                button.clicked.connect(lambda _checked=False, module=module: self.open_app(module))
                actions.addWidget(button)
            layout.addLayout(actions)
            self.app_status = self.text("Opening a tool does not enable recording or grant command access. Settings saves and protected changes use their normal explicit controls.")
            layout.addWidget(self.app_status)
            layout.addStretch()
            self.addPage(page)

            page, layout = self.make_page("Ready for your next step", "Finish onboarding without claiming every feature is verified.")
            layout.addWidget(self.text("Finish saves only edited language/personality preferences and a local setup-completion marker. "
                "Listening, screen access, online providers, command grants and desktop settings remain unchanged."))
            layout.addWidget(self.text("You can finish while assets or hardware checks are pending. "
                "The inventory shows presence; actual voice and desktop behavior still need your own check."))
            self.finish_status = self.text("Live preview will save nothing." if preview else "Choose Finish setup to save; closing or cancelling leaves onboarding incomplete.")
            layout.addWidget(self.finish_status)
            layout.addStretch()
            self.final_page = self.addPage(page)
            self.worker_timer = QTimer(self)
            self.worker_timer.setSingleShot(True)
            self.worker_timer.timeout.connect(lambda: self.stop_inventory("Inventory timed out; no settings were changed."))

        @staticmethod
        def text(value):
            label = QLabel(value)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            return label

        @staticmethod
        def combo(options, selected):
            control = QComboBox()
            for value, label in options:
                control.addItem(label, value)
            control.setCurrentIndex(max(0, control.findData(selected)))
            return control

        @staticmethod
        def make_page(title, subtitle):
            page = QWizardPage()
            page.setTitle(title)
            page.setSubTitle(subtitle)
            return page, QVBoxLayout(page)

        def choices(self):
            return {"whisper_language": self.language.currentData(),
                    "reply_language_mode": self.reply_mode.currentData(),
                    "companion_personality": self.personality.currentData()}

        def start_inventory(self):
            if self.worker is not None:
                return
            self.worker_output.clear()
            self.inventory.clear()
            self.worker = QProcess(self)
            process = self.worker
            environment = QProcessEnvironment.systemEnvironment()
            environment.insert("AI_OS_HOME", str(home))
            process.setProcessEnvironment(environment)
            process.readyReadStandardOutput.connect(self.read_inventory)
            process.readyReadStandardError.connect(process.readAllStandardError)
            process.finished.connect(self.inventory_finished)
            process.errorOccurred.connect(lambda _error: self.stop_inventory("Inventory could not start; no settings were changed."))
            self.check_button.setEnabled(False)
            self.inventory_status.setText("Checking file and executable presence only…")
            self.worker_timer.start(8000)
            try:
                process.start(sys.executable, ["-m", "ai_os.first_run", "--inventory"])
            except (OSError, RuntimeError):
                self.stop_inventory("Inventory could not start; no settings were changed.")

        def read_inventory(self):
            if self.worker is None:
                return
            self.worker_output.extend(bytes(self.worker.readAllStandardOutput()))
            if len(self.worker_output) > 16384:
                self.stop_inventory("Inventory returned too much data; no settings were changed.")

        def inventory_finished(self, code, _status):
            if self.worker is None:
                return
            self.read_inventory()
            try:
                data = json.loads(self.worker_output)
                if code or data.get("scope") != "static_presence_only" or not isinstance(data.get("items"), list):
                    raise ValueError()
                for item in data["items"][:16]:
                    if not isinstance(item, dict) or not isinstance(item.get("name"), str) or type(item.get("present")) is not bool:
                        raise ValueError()
                    QTreeWidgetItem(self.inventory, [item["name"][:80], "Available" if item["present"] else "Needs provisioning"])
                self.inventory_status.setText("Presence checked. Model service/inference, microphone, audio quality and display behavior remain unverified.")
            except (ValueError, TypeError, AttributeError):
                self.inventory_status.setText("Inventory did not return a valid result. No settings were changed.")
            self.release_inventory()

        def release_inventory(self):
            self.worker_timer.stop()
            if self.worker is not None:
                self.worker.deleteLater()
                self.worker = None
            self.worker_output.clear()
            self.check_button.setEnabled(True)

        def stop_inventory(self, message):
            if self.worker is not None:
                self.worker.blockSignals(True)
                if self.worker.state() != QProcess.ProcessState.NotRunning:
                    self.worker.kill()
                    self.worker.waitForFinished(1000)
            self.release_inventory()
            self.inventory_status.setText(message)

        def open_settings(self, key):
            if key not in SETTINGS_PAGES:
                return
            try:
                panel = self.settings_window
                if panel is None:
                    from ai_os.native_settings import SettingsWindow
                    panel = SettingsWindow(home, launch_companion=False)
                    self.settings_window = panel
                    panel.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    panel.destroyed.connect(lambda: setattr(self, "settings_window", None))
                for index in range(panel.navigation.count()):
                    if panel.navigation.item(index).text() == SETTINGS_PAGES[key]:
                        panel.navigation.setCurrentRow(index)
                        break
                else:
                    raise ValueError()
                panel.showNormal()
                panel.raise_()
                panel.activateWindow()
                self.app_status.setText("Settings opened. Review and save there explicitly; unfinished drafts are preserved in this window.")
            except (OSError, ValueError, RuntimeError):
                self.app_status.setText("Settings could not open. Launch REgenOS Dashboard from the applications menu.")

        def open_app(self, module):
            if module not in {"ai_os.quick_chat", "ai_os.research_widget"}:
                return
            process = QProcess(self)
            environment = QProcessEnvironment.systemEnvironment()
            environment.insert("AI_OS_HOME", str(home))
            process.setProcessEnvironment(environment)
            process.setProgram(sys.executable)
            process.setArguments(["-m", module])
            try:
                result = process.startDetached()
                success = result[0] if isinstance(result, tuple) else result
            except (OSError, RuntimeError):
                success = False
            process.deleteLater()
            self.app_status.setText("Opening the native application…" if success else "The application could not start; use its applications-menu entry.")

        def accept(self):
            if self.currentId() != self.final_page or not self.acknowledge.isChecked():
                return
            self.stop_inventory("Inventory stopped.")
            if not preview:
                try:
                    if self.load_error:
                        raise ValueError()
                    changes = {key: value for key, value in self.choices().items() if value != self.initial_choices[key]}
                    complete_setup(home, changes, human_confirmed=True, baseline=self.initial, live=False)
                except (OSError, ValueError, PermissionError):
                    self.finish_status.setText("Setup could not be completed. Preferences changed elsewhere or the local destination needs review; reopen setup or check Settings.")
                    return
            super().accept()

        def reject(self):
            self.stop_inventory("Inventory stopped. Setup was not marked complete.")
            super().reject()

        def closeEvent(self, event):
            self.stop_inventory("Inventory stopped. Setup was not marked complete.")
            super().closeEvent(event)

    return SetupWizard()


def main() -> int:
    parser = argparse.ArgumentParser(description="Native REgenOS post-install setup")
    parser.add_argument("--if-needed", action="store_true", help="Exit before opening a window when setup is complete or this is a live session")
    parser.add_argument("--live", action="store_true", help="Show a read-only live preview without marking installed setup complete")
    parser.add_argument("--inventory", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    preview = args.live or live_session()
    if args.inventory:
        try:
            result = readiness_snapshot(AI_OS_HOME)
        except (OSError, ValueError, TypeError):
            print(json.dumps({"ok": False, "message": "Runtime preferences need review in Settings."}))
            return 1
        print(json.dumps(result))
        return 0
    if args.if_needed and not setup_needed(AI_OS_HOME, live=preview):
        return 0
    from PySide6.QtWidgets import QApplication

    app = QApplication(["regenos-setup"])
    app.setApplicationName("regenos-setup")
    app.setDesktopFileName("regenos-setup")
    app.setStyle("Fusion")
    wizard = create_wizard(AI_OS_HOME, live=preview)
    wizard.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
