from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_os.companion_state import EMOTIONS, SHAPE_NAMES, read_state
from ai_os.config import AI_OS_HOME, load_raw_config
from ai_os.native_widgets import CompanionCanvas, EmotionBars, LocalInstance, theme_stylesheet
from ai_os.settings_store import apply_user_appearance, protected_changes, save_settings


class SettingsWindow(QMainWindow):
    def __init__(self, home: Path = AI_OS_HOME, *, launch_companion: bool = True) -> None:
        super().__init__()
        self.home, self.launch_companion = home, launch_companion
        self.saved = load_raw_config(home)
        self.fields = {}
        self.service_process = None
        self.setWindowTitle("REgenOS Settings")
        self.resize(1030, 760)
        self.setMinimumSize(780, 570)
        outer = QWidget()
        self.setCentralWidget(outer)
        root = QVBoxLayout(outer)
        root.setContentsMargins(22, 18, 22, 18)
        header = QHBoxLayout()
        brand = QLabel("REgenOS")
        self.brand = brand
        brand.setMaximumWidth(360)
        brand.setObjectName("product")
        header.addWidget(brand)
        header.addStretch()
        header.addWidget(QLabel("Settings"))
        root.addLayout(header)
        body = QHBoxLayout()
        body.setSpacing(24)
        self.navigation = QListWidget()
        self.navigation.setFixedWidth(188)
        self.pages = QStackedWidget()
        body.addWidget(self.navigation)
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)
        self._companion_page()
        self._assistant_page()
        self._voice_page()
        self._appearance_page()
        self._desktop_page()
        self._sandbox_page()
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        footer = QHBoxLayout()
        self.status = QLabel("Ready")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        reset = self.button("Revert", QStyle.StandardPixmap.SP_BrowserReload, self.restore)
        self.save_button = self.button(
            "Save changes", QStyle.StandardPixmap.SP_DialogSaveButton, self.save
        )
        self.save_button.setObjectName("primary")
        footer.addWidget(reset)
        footer.addWidget(self.save_button)
        root.addLayout(footer)
        self.restore()
        self.poll = QTimer(self)
        self.poll.setInterval(350)
        self.poll.timeout.connect(self.refresh_preview)
        self.poll.start()
        if launch_companion and self.saved["avatar_enabled"]:
            QTimer.singleShot(0, self.ensure_companion)

    def button(self, text, icon, callback) -> QPushButton:
        button = QPushButton(self.style().standardIcon(icon), text)
        button.clicked.connect(callback)
        return button

    def page(self, name, icon):
        self.navigation.addItem(QListWidgetItem(self.style().standardIcon(icon), name))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 12, 12)
        layout.setSpacing(14)
        title = QLabel(name)
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        return layout

    def form(self, layout):
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        layout.addLayout(form)
        return form

    def check(self, form, key, label):
        control = QCheckBox(label)
        self.fields[key] = control
        form.addRow(control)
        return control

    def text(self, form, key, label, *, file=False):
        control = QLineEdit()
        control.setAccessibleName(label)
        self.fields[key] = control
        if file:
            row = QHBoxLayout()
            row.addWidget(control, 1)
            browse = QToolButton()
            browse.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
            browse.setToolTip(f"Choose {label.lower()}")

            def choose():
                path, _ = QFileDialog.getOpenFileName(self, label, str(self.home))
                if path:
                    control.setText(path)

            browse.clicked.connect(choose)
            row.addWidget(browse)
            form.addRow(label, row)
        else:
            form.addRow(label, control)
        return control

    def choice(self, form, key, label, choices):
        control = QComboBox()
        for value, caption in choices:
            control.addItem(caption, value)
        control.setAccessibleName(label)
        self.fields[key] = control
        form.addRow(label, control)
        return control

    def slider(self, form, key, label, low, high):
        row = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setAccessibleName(label)
        number = QSpinBox()
        number.setRange(low, high)
        number.setFixedWidth(76)
        number.setAccessibleName(label)
        slider.valueChanged.connect(number.setValue)
        number.valueChanged.connect(slider.setValue)
        row.addWidget(slider, 1)
        row.addWidget(number)
        self.fields[key] = number
        form.addRow(label, row)

    def _companion_page(self):
        layout = self.page("Companion", QStyle.StandardPixmap.SP_ComputerIcon)
        preview = QHBoxLayout()
        self.canvas = CompanionCanvas()
        self.canvas.setMinimumSize(235, 230)
        self.bars = EmotionBars()
        self.canvas.levels_changed.connect(self.bars.set_levels)
        preview.addWidget(self.canvas, 1)
        preview.addWidget(self.bars, 1)
        layout.addLayout(preview)
        self.activity = QLabel("Idle")
        self.activity.setObjectName("muted")
        layout.addWidget(self.activity)
        form = self.form(layout)
        self.check(form, "avatar_enabled", "Show corner companion")
        self.check(form, "avatar_show_emotion_bars", "Show emotion bars in corner")
        self.check(form, "avatar_animation_enabled", "Animate pixels")
        self.check(form, "avatar_topic_morphing", "Morph with topics and tasks")
        self.choice(
            form,
            "avatar_corner",
            "Corner",
            [
                (key, key.replace("-", " ").title())
                for key in ("bottom-right", "bottom-left", "top-right", "top-left")
            ],
        )
        self.choice(
            form, "avatar_idle_shape", "Resting form", [(key, key.title()) for key in SHAPE_NAMES]
        )
        self.slider(form, "avatar_scale", "Size (%)", 60, 160)
        self.slider(form, "avatar_motion", "Fluid motion", 0, 100)
        self.slider(form, "avatar_reactivity", "Emotional response", 0, 100)
        self.accent = QToolButton()
        self.accent.setFixedSize(58, 32)
        self.accent.setToolTip("Companion accent color")
        self.accent.clicked.connect(self.choose_accent)
        self.accent_value = self.saved["avatar_accent"]
        form.addRow("Accent", self.accent)
        label = QLabel("Emotion baseline")
        label.setToolTip("Simulated character values. Activity changes the live bars above.")
        layout.addWidget(label)
        form = self.form(layout)
        for key in EMOTIONS:
            self.slider(form, f"avatar_emotions.{key}", key.capitalize(), 0, 100)
        layout.addStretch()

    def _assistant_page(self):
        layout = self.page("AI connection", QStyle.StandardPixmap.SP_DriveNetIcon)
        form = self.form(layout)
        self.choice(
            form,
            "ai_provider",
            "Provider",
            [("ollama", "Ollama"), ("openai_compatible", "OpenAI-compatible")],
        )
        self.text(form, "ollama_url", "Endpoint")
        self.text(form, "ollama_model", "Model")
        key = self.text(form, "api_key_env", "API key variable")
        key.setToolTip("The environment variable holding the key, for example AI_OS_API_KEY.")
        self.check(form, "allow_external_apis", "Allow approved online providers")
        hosts = QPlainTextEdit()
        hosts.setFixedHeight(100)
        hosts.setAccessibleName("Approved hostnames, one per line")
        self.fields["allowed_api_hosts"] = hosts
        form.addRow("Approved hosts", hosts)
        layout.addStretch()

    def _voice_page(self):
        layout = self.page("Voice & listening", QStyle.StandardPixmap.SP_MediaVolume)
        form = self.form(layout)
        self.check(form, "always_listening_enabled", "Listen for wake word")
        self.check(form, "wake_word_enabled", "Require wake word")
        self.check(form, "speech_enabled", "Speak replies")
        threshold = QDoubleSpinBox()
        threshold.setRange(0, 1)
        threshold.setSingleStep(0.05)
        self.fields["wake_word_threshold"] = threshold
        form.addRow("Wake sensitivity threshold", threshold)
        self.slider(form, "voice_command_seconds", "Capture time (seconds)", 2, 30)
        self.text(form, "whisper_cli", "Whisper executable", file=True)
        self.text(form, "whisper_model", "Whisper model", file=True)
        self.text(form, "piper_model", "Piper voice", file=True)
        controls = QHBoxLayout()
        controls.addWidget(
            self.button(
                "Start listener",
                QStyle.StandardPixmap.SP_MediaPlay,
                lambda: self.control_service("start"),
            )
        )
        controls.addWidget(
            self.button(
                "Restart",
                QStyle.StandardPixmap.SP_BrowserReload,
                lambda: self.control_service("restart"),
            )
        )
        controls.addWidget(
            self.button(
                "Stop", QStyle.StandardPixmap.SP_MediaStop, lambda: self.control_service("stop")
            )
        )
        layout.addLayout(controls)
        layout.addStretch()

    def _appearance_page(self):
        layout = self.page("Appearance", QStyle.StandardPixmap.SP_DesktopIcon)
        form = self.form(layout)
        theme = self.choice(
            form,
            "theme",
            "Window theme",
            [(key, key.title()) for key in ("forest", "graphite", "ocean", "light", "sunrise")],
        )
        theme.currentIndexChanged.connect(
            lambda: self.setStyleSheet(theme_stylesheet(theme.currentData()))
        )
        for key, label in (
            ("brand_name", "Product name"),
            ("assistant_name", "Companion name"),
            ("logo_path", "Logo"),
            ("wallpaper_path", "Wallpaper"),
            ("lockscreen_path", "Lock screen"),
            ("icon_theme", "Icon theme"),
            ("cursor_theme", "Cursor theme"),
            ("font", "Desktop font"),
        ):
            self.text(form, f"branding.{key}", label, file=key.endswith("_path"))
        layout.addWidget(
            self.button(
                "Apply desktop appearance",
                QStyle.StandardPixmap.SP_DialogApplyButton,
                self.apply_appearance,
            )
        )
        layout.addStretch()

    def _desktop_page(self):
        layout = self.page("Desktop", QStyle.StandardPixmap.SP_FileDialogListView)
        form = self.form(layout)
        self.check(form, "hyprland_enabled", "Allow Hyprland window tools")
        for keys, action in (
            ("Super + A", "REgenOS Settings"),
            ("Super + Space", "Application launcher"),
            ("Super + Enter", "Terminal"),
            ("Super + R", "Start AI service"),
            ("Super + Ctrl + R", "Stop AI service"),
            ("Super + L", "Lock screen"),
        ):
            form.addRow(keys, QLabel(action))
        layout.addStretch()

    def _sandbox_page(self):
        layout = self.page("Permissions", QStyle.StandardPixmap.SP_MessageBoxWarning)
        form = self.form(layout)
        self.check(form, "sandbox_lock_settings", "Confirm protected setting changes")
        label = QLabel("System actions: terminal approval")
        label.setToolTip(
            "Destructive actions need a human terminal approval. A background daemon denies requests without an interactive terminal."
        )
        form.addRow(label)
        layout.addStretch()

    def choose_accent(self):
        color = QColorDialog.getColor(QColor(self.accent_value), self, "Companion accent")
        if color.isValid():
            self.accent_value = color.name()
            self.update_swatch()

    def update_swatch(self):
        self.accent.setStyleSheet(
            f"background: {self.accent_value}; border: 1px solid #8d9ca3; border-radius: 4px;"
        )

    def restore(self):
        for key, control in self.fields.items():
            parts = key.split(".")
            value = self.saved[parts[0]] if len(parts) == 1 else self.saved[parts[0]][parts[1]]
            if isinstance(control, QCheckBox):
                control.setChecked(value)
            elif isinstance(control, QComboBox):
                control.setCurrentIndex(max(0, control.findData(value)))
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.setValue(value)
            elif isinstance(control, QPlainTextEdit):
                control.setPlainText("\n".join(value))
            else:
                control.setText(value)
        self.accent_value = self.saved["avatar_accent"]
        self.update_swatch()
        self.setStyleSheet(theme_stylesheet(self.saved["theme"]))
        self.apply_branding()

    def apply_branding(self):
        name = self.saved["branding"]["brand_name"] or "REgenOS"
        self.brand.setText(
            QFontMetrics(self.brand.font()).elidedText(name, Qt.TextElideMode.ElideRight, 350)
        )
        self.brand.setToolTip(name)
        self.setWindowTitle(f"{name} Settings")
        logo = self.saved["branding"]["logo_path"]
        self.setWindowIcon(QIcon(logo) if logo and Path(logo).is_file() else QIcon())

    def collect(self) -> dict:
        data = deepcopy(self.saved)
        for key, control in self.fields.items():
            if isinstance(control, QCheckBox):
                value = control.isChecked()
            elif isinstance(control, QComboBox):
                value = control.currentData()
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                value = control.value()
            elif isinstance(control, QPlainTextEdit):
                value = [
                    line.strip() for line in control.toPlainText().splitlines() if line.strip()
                ]
            else:
                value = control.text()
            parts = key.split(".")
            if len(parts) == 2:
                data[parts[0]][parts[1]] = value
            else:
                data[key] = value
        data["avatar_accent"] = self.accent_value
        return data

    def refresh_preview(self):
        state = read_state(self.home)
        self.canvas.set_state(state, self.collect())
        self.activity.setText(state["phase"].capitalize())

    def save(self) -> bool:
        values = self.collect()
        changes = {key: value for key, value in values.items() if value != self.saved.get(key)}
        confirmed = False
        if self.saved["sandbox_lock_settings"] and protected_changes(self.saved, changes):
            names = ", ".join(
                key.replace("_", " ") for key in sorted(protected_changes(self.saved, changes))
            )
            confirmed = (
                QMessageBox.question(
                    self,
                    "Protected settings",
                    f"Apply changes to {names}?",
                    QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                == QMessageBox.StandardButton.Apply
            )
            if not confirmed:
                return False
        try:
            self.saved = save_settings(changes, self.home, human_confirmed=confirmed)
        except (OSError, ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "Settings were not saved", str(exc))
            return False
        if self.launch_companion and self.saved["avatar_enabled"]:
            self.ensure_companion()
        self.apply_branding()
        self.status.setText(
            "Saved. Voice changes take effect on service restart."
            if any(
                key in changes
                for key in (
                    "always_listening_enabled",
                    "wake_word_enabled",
                    "speech_enabled",
                    "piper_model",
                    "whisper_model",
                )
            )
            else "Settings saved"
        )
        return True

    def ensure_companion(self):
        QProcess.startDetached(sys.executable, ["-m", "ai_os.avatar_overlay"])

    def apply_appearance(self):
        if not self.save():
            return
        try:
            apply_user_appearance(self.saved)
            self.status.setText(
                "Desktop appearance saved. Restart wallpaper and GTK applications to apply."
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Appearance was not applied", str(exc))

    def control_service(self, action):
        if action != "stop" and not self.save():
            return
        if (
            self.service_process
            and self.service_process.state() != QProcess.ProcessState.NotRunning
        ):
            return
        process = QProcess(self)
        self.service_process = process
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        def finished(code, _status):
            output = bytes(process.readAllStandardOutput()).decode(errors="replace").strip()
            self.status.setText(
                f"AI service: {action} complete" if code == 0 else output or "Service action failed"
            )

        process.finished.connect(finished)
        process.errorOccurred.connect(lambda _error: self.status.setText(process.errorString()))
        self.status.setText(f"AI service: {action}...")
        process.start("systemctl", ["--user", action, "ai-os.service"])
        QTimer.singleShot(
            8000,
            process,
            lambda: process.kill() if process.state() != QProcess.ProcessState.NotRunning else None,
        )

    def closeEvent(self, event):
        if self.collect() != self.saved:
            answer = QMessageBox.question(
                self,
                "Unsaved settings",
                "Discard unsaved changes?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
        event.accept()


def main() -> int:
    app = QApplication(["regenos-settings"])
    app.setStyle("Fusion")
    app.setApplicationName("regenos-settings")
    app.setDesktopFileName("regenos-settings")
    window = None

    def activate():
        if window:
            window.showNormal()
            window.raise_()
            window.activateWindow()

    instance = LocalInstance(AI_OS_HOME, "regenos-settings")
    if not instance.acquire(activate):
        return 0
    window = SettingsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
