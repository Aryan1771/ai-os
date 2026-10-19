from __future__ import annotations

import sys
import json
import sqlite3
import time
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer
from PySide6.QtGui import QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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
    QInputDialog,
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
from ai_os.native_widgets import CompanionCanvas, EmotionBars, LocalInstance, hologram_palette, theme_stylesheet
from ai_os.settings_store import ALWAYS_CONFIRM_KEYS, apply_user_appearance, protected_changes, save_settings


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
        self.show_avatar_button = self.button(
            "Unhide avatar", QStyle.StandardPixmap.SP_DesktopIcon, self.show_companion
        )
        self.show_avatar_button.setToolTip("Show the avatar again, or start it if it is closed")
        header.addWidget(self.show_avatar_button)
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
        self._conversation_page()
        self._companion_page()
        self._assistant_page()
        self._hardware_page()
        self._voice_page()
        self._memory_page()
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
        for control in self.fields.values():
            signal = (control.toggled if isinstance(control, QCheckBox) else
                      control.currentIndexChanged if isinstance(control, QComboBox) else
                      control.valueChanged if isinstance(control, (QSpinBox, QDoubleSpinBox)) else
                      control.textChanged)
            signal.connect(self.mark_unsaved)
        self.mark_unsaved()
        self.poll = QTimer(self)
        self.poll.setInterval(350)
        self.poll.timeout.connect(self.refresh_preview)
        self.poll.start()
        self.access_poll = QTimer(self)
        self.access_poll.setInterval(1000)
        self.access_poll.timeout.connect(self.refresh_full_access_status)
        self.access_poll.start()
        if launch_companion and self.saved["avatar_enabled"]:
            QTimer.singleShot(0, self.ensure_companion)

    def button(self, text, icon, callback) -> QPushButton:
        button = QPushButton(self.style().standardIcon(icon), text)
        button.clicked.connect(callback)
        return button

    def mark_unsaved(self, *_args):
        count = sum(value != self.saved.get(key) for key, value in self.collect().items())
        self.save_button.setEnabled(bool(count))
        self.save_button.setText(f"Save {count} changes" if count else "Saved")
        self.status.setText(
            "Unsaved changes. Save to apply them to the next reply or voice request; the avatar preview updates here immediately."
            if count else "All preferences saved. AI preferences apply to the next request."
        )
        self.status.setProperty("status", "warning" if count else "success")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def open_native_tool(self, module):
        if module not in {"ai_os.quick_chat", "ai_os.research_widget"}:
            return False
        process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("AI_OS_HOME", str(self.home))
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments(["-m", module])
        result = process.startDetached()
        ok = result[0] if isinstance(result, tuple) else result
        self.status.setText("Application launch requested." if ok else "Application could not start. Check the runtime installation.")
        process.deleteLater()
        return bool(ok)

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
        controls = QHBoxLayout()
        controls.addWidget(self.button("Unhide / start avatar", QStyle.StandardPixmap.SP_DesktopIcon, self.show_companion))
        controls.addWidget(self.button("Quit companion", QStyle.StandardPixmap.SP_DialogCloseButton, self.stop_companion))
        layout.addLayout(controls)
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
        self.check(form, "avatar_show_emotion_bars", "Debug: show emotion bars")
        self.check(form, "avatar_show_status", "Debug: show mood/activity label")
        self.check(form, "avatar_auto_move", "Move away after pointer overlap")
        self.check(form, "avatar_screen_awareness", "Use local screen texture to choose a quieter corner")
        note = QLabel("Screen texture uses a temporary local screen image when moving. Nothing is saved or sent to a model. It estimates visual clutter, not whether text is important; some Wayland sessions deny capture. Drag RE to position it manually.")
        note.setWordWrap(True)
        form.addRow(note)
        self.check(form, "screen_context_enabled", "Let RE read my shared screen locally")
        self.check(form, "desktop_context_enabled", "Read focused app through GNOME accessibility (no screen sharing)")
        self.choice(form, "companion_personality", "Conversation style", [
            (name, name.capitalize()) for name in ("warm", "calm", "playful", "focused")
        ])
        self.text(form, "companion_style_notes", "Personal style preferences (optional)")
        self.check(form, "screen_commentary_enabled", "Offer comments when my screen changes")
        self.check(form, "screen_commentary_speech", "Speak screen comments (also requires Speak replies)")
        self.slider(form, "screen_commentary_minutes", "Minimum screen comment interval (minutes)", 1, 120)
        screen_note = QLabel("Choose a screen in the desktop sharing dialog. RE reads visible English text locally; images and video are not understood. A separate screen indicator has Pause and Ask RE buttons. Screen observations expire, are not saved in memory, and never authorize actions. Locking pauses sharing; Resume opens the selector again. Remote AI providers receive no screen context.")
        screen_note.setWordWrap(True)
        form.addRow(screen_note)
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
        self.choice(form, "avatar_display", "Display",
                    [("", "Current / automatic")] + [(s.name(), s.name()) for s in QApplication.screens()]
                    + ([(self.saved["avatar_display"], self.saved["avatar_display"] + " (disconnected)")]
                       if self.saved["avatar_display"] and self.saved["avatar_display"] not in {s.name() for s in QApplication.screens()} else []))
        self.slider(form, "avatar_scale", "Size (%)", 60, 160)
        self.slider(form, "avatar_motion", "Fluid motion", 0, 100)
        self.slider(form, "avatar_reactivity", "Emotional response", 0, 100)
        self.accent = QToolButton()
        self.accent.setFixedSize(58, 32)
        self.accent.setToolTip("Choose a blue hologram shade")
        self.accent.clicked.connect(self.choose_accent)
        self.accent_value = self.saved["avatar_accent"]
        form.addRow("Hologram blue", self.accent)
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
        self.slider(form, "model_context_tokens", "Context limit", 1024, 8192)
        key = self.text(form, "api_key_env", "API key variable")
        key.setToolTip("The environment variable holding the key, for example AI_OS_API_KEY.")
        self.check(form, "allow_external_apis", "Allow approved online providers")
        hosts = QPlainTextEdit()
        hosts.setFixedHeight(100)
        hosts.setAccessibleName("Approved hostnames, one per line")
        self.fields["allowed_api_hosts"] = hosts
        form.addRow("Approved hosts", hosts)
        layout.addStretch()

    def _hardware_page(self):
        layout = self.page("Hardware policy", QStyle.StandardPixmap.SP_ComputerIcon)
        self.hardware_status = QLabel("No device reaction recorded yet.")
        self.hardware_status.setWordWrap(True)
        self.hardware_status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.hardware_status)
        form = self.form(layout)
        self.check(form, "hardware_notifications_enabled", "Monitor device connections")
        self.check(form, "hardware_speech_enabled", "Speak device reactions (requires speech enabled)")
        self.check(form, "hardware_auto_adapt", "Adapt to detected hardware")
        self.choice(
            form,
            "hardware_backend",
            "Compute policy",
            [("auto", "Ollama automatic"), ("cpu", "CPU only")],
        )
        self.check(
            form,
            "hardware_allow_model_fallback",
            "Allow explicitly listed installed fallback models",
        )
        models = QPlainTextEdit()
        models.setMaximumHeight(90)
        self.fields["hardware_fallback_models"] = models
        form.addRow("Fallback models, one per line", models)
        note = QLabel(
            "Automatic selection uses estimates, not a hard VRAM reservation. "
            "It never downloads a model. Per-machine overrides, if present, take precedence."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

    def _conversation_page(self):
        from ai_os.conversation_widget import ConversationWidget

        layout = self.page("Conversation", QStyle.StandardPixmap.SP_MessageBoxInformation)
        tools = QHBoxLayout()
        tools.addWidget(self.button("Compact chat", QStyle.StandardPixmap.SP_MessageBoxInformation,
                                    lambda: self.open_native_tool("ai_os.quick_chat")))
        tools.addWidget(self.button("Research reports", QStyle.StandardPixmap.SP_FileDialogDetailedView,
                                    lambda: self.open_native_tool("ai_os.research_widget")))
        layout.addLayout(tools)
        self.conversation = ConversationWidget(self.home)
        layout.addWidget(self.conversation)

    def _memory_page(self):
        from ai_os.memory_widget import MemoryWidget

        layout = self.page("Memory", QStyle.StandardPixmap.SP_FileDialogDetailedView)
        form = self.form(layout)
        self.check(form, "memory_enabled", "Short-term memory: retain recent local conversations")
        self.check(form, "reinforced_memory_enabled", "Long-term memory: reinforce repeated user statements (up to 180 days)")
        memory_note = QLabel("Recent history provides conversation context. Repeated statements can enter longer-term memory after three occurrences spaced at least ten minutes apart; reinforcement refreshes expiry. Save important preferences or context notes below to keep them explicitly until you forget them. This stores local records and does not train model weights.")
        memory_note.setWordWrap(True)
        form.addRow(memory_note)
        self.check(form, "memory_allow_remote", "Allow saved memory in remote model requests")
        self.slider(form, "memory_retention_days", "History retention (days)", 1, 365)
        self.check(form, "activity_memory_enabled", "Remember focused app usage (names and approximate time only)")
        self.slider(form, "activity_retention_days", "App usage retention (days)", 1, 30)
        layout.addWidget(MemoryWidget(self.home))

    def _voice_page(self):
        layout = self.page("Voice & listening", QStyle.StandardPixmap.SP_MediaVolume)
        enrollment = QHBoxLayout()
        enrollment.addWidget(self.button("Set up / test my voice…", QStyle.StandardPixmap.SP_MediaVolume,
                                         self.setup_speaker))
        self.speaker_status = QLabel("Speaker filter is off.")
        self.speaker_status.setWordWrap(True)
        self.speaker_status.setTextFormat(Qt.TextFormat.PlainText)
        enrollment.addWidget(self.speaker_status, 1)
        layout.addLayout(enrollment)
        form = self.form(layout)
        self.check(form, "speaker_recognition_enabled", "Respond only to my enrolled voice (conversation filter)")
        self.text(form, "speaker_model", "Local speaker embedding model (.onnx)", file=True)
        threshold = QDoubleSpinBox()
        threshold.setRange(0.4, 0.95)
        threshold.setSingleStep(0.01)
        self.fields["speaker_threshold"] = threshold
        form.addRow("Speaker similarity threshold (requires real testing)", threshold)
        identity_note = QLabel("Setup records only when you press Record and keeps a local speaker profile. Recordings are deleted after processing. Voice matching can be fooled by recordings or synthesis: it cannot approve commands, sudo, or login. Missing models or enrollment block requests while this filter is enabled.")
        identity_note.setWordWrap(True)
        form.addRow(identity_note)
        self.check(form, "always_listening_enabled", "Enable microphone listening")
        self.check(form, "wake_word_enabled", "Require wake word")
        self.check(form, "conversation_listening_enabled", "Conversation listening without a wake word (captures nearby speech)")
        self.voice_status = QLabel("Microphone status unavailable")
        self.voice_status.setWordWrap(True)
        layout.addWidget(self.voice_status)
        self.choice(form, "wake_backend", "Wake detector", [("openwakeword", "Trained openWakeWord model"), ("re_whisper", "RE (R E) — experimental local Whisper")])
        note = QLabel("Choose Require wake word, or explicitly enable conversation listening without it. Conversation mode sends nearby speech to the assistant after a pause; it is not speaker authentication. Disable microphone listening to stop. Voice settings reload in the running daemon. For wake mode say R E, pause, then speak when Listening appears.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.check(form, "speech_enabled", "Speak replies")
        self.check(form, "speech_emotion_enabled", "Adapt speaking pace to simulated emotion")
        self.check(form, "proactive_speech_enabled", "Allow occasional proactive speech (local model only)")
        self.slider(form, "proactive_interval_minutes", "Minimum proactive interval (minutes)", 5, 120)
        threshold = QDoubleSpinBox()
        threshold.setRange(0, 1)
        threshold.setSingleStep(0.05)
        self.fields["wake_word_threshold"] = threshold
        form.addRow("Wake sensitivity threshold", threshold)
        self.slider(form, "voice_command_seconds", "Wait for speech to start (seconds)", 2, 30)
        self.slider(form, "voice_silence_seconds", "Finish after silence (seconds)", 1, 10)
        self.slider(form, "voice_max_utterance_seconds", "Maximum utterance (seconds)", 10, 120)
        endpoint_note = QLabel("After you begin speaking, RE waits for this much continuous silence before transcribing the complete utterance and answering. Five seconds allows pauses while you speak and adds five seconds before processing starts. Silence detection uses microphone energy; adjust input level in a noisy room.")
        endpoint_note.setWordWrap(True)
        form.addRow(endpoint_note)
        self.text(form, "whisper_cli", "Whisper executable", file=True)
        self.text(form, "whisper_model", "Whisper model", file=True)
        self.choice(form, "whisper_language", "Conversation and recognition language", [("auto", "Automatic (multilingual model)"), ("en", "English"), ("hi", "Hindi")])
        self.choice(form, "reply_language_mode", "Reply language", [
            ("selected", "Use the selected language"),
            ("match", "Match each message (English / Hindi)"),
        ])
        language_note = QLabel("Match each message uses multilingual Whisper's detected language for spoken requests and keeps the selected language as a fallback. It does not change the saved language after every phrase. Hindi replies need a Hindi Piper voice, or a separately integrated multilingual voice engine.")
        language_note.setWordWrap(True)
        form.addRow(language_note)
        self.text(form, "piper_model", "English Piper voice", file=True)
        self.text(form, "piper_hindi_model", "Hindi Piper voice (optional)", file=True)
        self.text(form, "wake_word_model", "Custom wake-word model", file=True)
        duration = QDoubleSpinBox()
        duration.setRange(0.5, 2.0)
        duration.setSingleStep(0.1)
        self.fields["piper_length_scale"] = duration
        form.addRow("Speech duration multiplier", duration)
        controls = QHBoxLayout()
        controls.addWidget(self.button("Check readiness", QStyle.StandardPixmap.SP_MessageBoxInformation,
                                       self.check_runtime_readiness))
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
        self.slider(form, "cursor_size", "Cursor size (pixels)", 24, 96)
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
        layout.addWidget(self.button("Apply cursor size now (GNOME)",
                                     QStyle.StandardPixmap.SP_DialogApplyButton, self.apply_cursor_size))
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
        command_form = self.form(layout)
        self.choice(command_form, "command_access", "Command access mode", [
            ("restricted", "Restricted — diagnostics; review other commands"),
            ("supervised", "Full access mode — time-limited ordinary user commands"),
        ])
        controls = QHBoxLayout()
        self.enable_access_button = self.button("Enable full access mode…", QStyle.StandardPixmap.SP_DialogApplyButton,
                                               self.enable_full_access)
        controls.addWidget(self.enable_access_button)
        controls.addWidget(self.button("Revoke full access", QStyle.StandardPixmap.SP_DialogCloseButton,
                                       self.revoke_full_access))
        layout.addLayout(controls)
        self.full_access_status = QLabel()
        self.full_access_status.setWordWrap(True)
        layout.addWidget(self.full_access_status)
        from ai_os.cleanup_widget import show_cleanup_rules
        layout.addWidget(self.button("Remembered cleanup permissions…", QStyle.StandardPixmap.SP_TrashIcon,
                                     lambda: show_cleanup_rules(self.home, self)))
        self.refresh_full_access_status()
        access_note = QLabel(
            "Enable full access mode lets you choose a duration and confirm the scope. Selecting a mode alone does not grant access. "
            "An active grant runs ordinary commands as your account without per-command prompts in the default/voice session. "
            "It can read and change your user files. Sudo/privilege tools, physical disks, partitioning, filesystems, "
            "mounts, boot and security changes stay blocked or separately reviewed. No blanket access to online accounts. "
            "Bubblewrap is required; system files stay read-only and the user session bus is hidden."
        )
        access_note.setWordWrap(True)
        layout.addWidget(access_note)
        github_title = QLabel("GitHub account reading")
        layout.addWidget(github_title)
        self.github_status_label = QLabel()
        self.github_status_label.setWordWrap(True)
        layout.addWidget(self.github_status_label)
        github_controls = QHBoxLayout()
        github_controls.addWidget(self.button(
            "Choose repositories…", QStyle.StandardPixmap.SP_DirOpenIcon,
            self.configure_github_access,
        ))
        github_controls.addWidget(self.button(
            "Disable GitHub access", QStyle.StandardPixmap.SP_DialogCloseButton,
            self.disable_github_access,
        ))
        layout.addLayout(github_controls)
        github_note = QLabel(
            "Online, read-only access through the verified GitHub MCP server and your existing gh login. "
            "Only explicitly chosen repositories can be read. Results stay out of saved chat, memory, "
            "remote AI providers and action planning. No account writes are enabled."
        )
        github_note.setWordWrap(True)
        layout.addWidget(github_note)
        self.refresh_github_status()
        form = self.form(layout)
        self.check(form, "sandbox_lock_settings", "Confirm protected setting changes")
        self.check(form, "browser_enabled", "Allow reviewed browser research and ChatGPT prompts")
        identity = QLabel("Login recognition: not enrolled. Face and voice unlocking are not installed; password login remains active. RE wake detection starts the assistant only and cannot unlock your session. Enrollment and a reviewed system authentication backend are required before unlock controls can be enabled.")
        identity.setWordWrap(True)
        layout.addWidget(identity)
        layout.addStretch()

    def choose_accent(self):
        shades = {"Sky": "#4daaff", "Ice": "#69d8ff", "Electric": "#637dff"}
        current = next((i for i, value in enumerate(shades.values())
                        if value == self.accent_value), 0)
        name, accepted = QInputDialog.getItem(
            self, "Hologram blue", "Shade", list(shades), current, False,
        )
        if accepted and name in shades:
            self.accent_value = shades[name]
            self.update_swatch()
            self.mark_unsaved()

    def update_swatch(self):
        self.accent.setStyleSheet(
            f"background: {hologram_palette(self.accent_value)['+']}; border: 1px solid #8d9ca3; border-radius: 4px;"
        )

    def refresh_github_status(self):
        from ai_os.github_mcp import github_status
        status = github_status(home=self.home)
        if status.get("ok") and status.get("enabled"):
            message = "Read-only access enabled: " + ", ".join(status["repositories"])
        elif status.get("ok"):
            message = "GitHub access is off. Verified server installed."
        else:
            message = "GitHub access unavailable. Provision the verified server before enabling it."
        self.github_status_label.setText(message)

    def configure_github_access(self):
        from ai_os.github_mcp import configure_github, github_status
        status = github_status(home=self.home)
        if not status.get("ok"):
            QMessageBox.warning(self, "GitHub unavailable", status["message"])
            return False
        value, accepted = QInputDialog.getMultiLineText(
            self, "Read-only GitHub repositories", "Exact owner/repository names, one per line:",
            "\n".join(status.get("repositories") or ["Aryan1771/ai-os"]),
        )
        if not accepted:
            return False
        repositories = [line.strip() for line in value.splitlines() if line.strip()]
        # Validate before presenting the exact scope. No network or credential read here.
        from ai_os.github_mcp import REPOSITORY
        if not 1 <= len(repositories) <= 20 or any(not REPOSITORY.fullmatch(x) for x in repositories):
            QMessageBox.warning(self, "Invalid repositories", "Enter 1–20 exact owner/repository names.")
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Allow GitHub repository reads?")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(
            "Allow online reads using your existing gh login for:\n\n"
            + "\n".join(sorted(set(repositories)))
            + "\n\nBranches, commits, issues, pull requests and files only. "
            "Results are shown locally and are not saved automatically. No GitHub writes."
        )
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return False
        try:
            configure_github(True, repositories, home=self.home, human_confirmed=True)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "GitHub access was not enabled", str(exc))
            return False
        self.refresh_github_status()
        return True

    def disable_github_access(self):
        from ai_os.github_mcp import configure_github, github_status
        status = github_status(home=self.home)
        try:
            configure_github(False, status.get("repositories") or ["Aryan1771/ai-os"],
                             home=self.home, human_confirmed=True)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "GitHub access was not disabled", str(exc))
            return False
        self.refresh_github_status()
        return True

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
        self.mark_unsaved()

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
        if load_raw_config(self.home)["speaker_recognition_enabled"]:
            self.speaker_status.setText("Enrolled-voice filter is on. Setup and the local model must be ready.")
            try:
                path = self.home / "run/speaker-status.json"
                if path.stat().st_size <= 2048:
                    speaker = json.loads(path.read_text())
                    if isinstance(speaker, dict) and 0 <= time.time() - speaker.get("updated", 0) < 60:
                        self.speaker_status.setText(str(speaker.get("message", ""))[:300])
            except (OSError, ValueError, TypeError):
                pass
        else:
            self.speaker_status.setText("Speaker filter is off.")
        try:
            event_path = self.home / "run/hardware-event.json"
            if event_path.stat().st_size <= 4096:
                event = json.loads(event_path.read_text())
                self.hardware_status.setText(
                    "Last device event: " + str(event.get("message", ""))[:1000]
                    + (" " + str(event["speech_error"])[:300] if event.get("speech_error") else "")
                    + (f" Waiting to speak: {int(event.get('pending_count', 0))}." if event.get("pending_count") else "")
                )
        except (OSError, ValueError, TypeError):
            pass
        try:
            voice = json.loads((self.home / "run/voice-status.json").read_text())
            fresh = 0 <= time.time() - voice["updated"] < 45
            self.voice_status.setText(
                "Microphone: " + voice["state"] + ". " + voice.get("message", "")
                + (" Last error: " + voice["last_error"] if voice.get("last_error") else "")
                if fresh else "Microphone status stale. Start or restart the AI service."
            )
        except (OSError, ValueError, KeyError, TypeError):
            self.voice_status.setText("Microphone status unavailable. Start or restart the AI service.")

    def save(self) -> bool:
        values = self.collect()
        changes = {key: value for key, value in values.items() if value != self.saved.get(key)}
        confirmed = False
        protected = protected_changes(self.saved, changes)
        if protected and (self.saved["sandbox_lock_settings"] or protected & ALWAYS_CONFIRM_KEYS):
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
        if "command_access" in changes:
            self.refresh_full_access_status()
        if self.launch_companion and self.saved["avatar_enabled"]:
            self.ensure_companion()
        self.apply_branding()
        self.status.setText(
            "Saved. The running daemon reloads voice changes within a second; start it if stopped."
            if any(
                key in changes
                for key in (
                    "always_listening_enabled",
                    "conversation_listening_enabled",
                    "wake_word_enabled",
                    "speech_enabled",
                    "voice_silence_seconds",
                    "voice_max_utterance_seconds",
                    "whisper_language",
                    "reply_language_mode",
                    "speaker_recognition_enabled",
                    "speaker_model",
                    "speaker_threshold",
                    "piper_model",
                    "whisper_model",
                )
            )
            else "Settings saved"
        )
        self.save_button.setText("Saved")
        self.save_button.setEnabled(False)
        self.status.setText(f"Saved {len(changes)} preferences. Conversation style and AI/voice choices apply to the next request. Use the test buttons to verify local readiness.")
        self.status.setProperty("status", "success")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        return True

    def setup_speaker(self):
        model = self.fields["speaker_model"].text().strip()
        if model != load_raw_config(self.home)["speaker_model"]:
            answer = QMessageBox.question(
                self, "Use this local speaker model?",
                "Save the selected speaker model path and open voice setup? Other unsaved preferences will be kept in the form.",
                QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Apply:
                return
            try:
                self.saved = save_settings({"speaker_model": model}, self.home, human_confirmed=True)
            except (OSError, ValueError, PermissionError) as exc:
                QMessageBox.warning(self, "Speaker model was not saved", str(exc))
                return
        from ai_os.speaker_setup import SpeakerSetupDialog
        SpeakerSetupDialog(self.home, parent=self).exec()
        self.mark_unsaved()

    def show_companion(self):
        try:
            self.saved = save_settings({"avatar_enabled": True}, self.home, human_confirmed=True)
            self.fields["avatar_enabled"].setChecked(True)
            if self.start_companion(show=True):
                self.status.setText("Avatar unhidden; companion startup requested.")
            else:
                self.status.setText("Avatar unhidden, but the companion could not start. Open REgenOS Companion from your desktop.")
        except (OSError, ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "Companion could not be shown", str(exc))

    def start_companion(self, *, show=False):
        process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("AI_OS_HOME", str(self.home))
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments(["-m", "ai_os.avatar_overlay"] + (["--show"] if show else []))
        result = process.startDetached()
        process.deleteLater()
        return result[0] if isinstance(result, tuple) else bool(result)

    def refresh_full_access_status(self):
        from ai_os.security.access_grants import GrantStore
        try:
            store = GrantStore(self.home)
            grant = store.status("default").get("grant") if store.path.exists() else None
            mode = load_raw_config(self.home)["command_access"]
            if mode == "supervised" and grant and grant.get("kind") == "user":
                remaining = max(0, int(grant.get("deadline", 0) - time.monotonic()))
                message = f"Full access active for the default/voice session · {remaining} seconds remaining."
            else:
                message = "Full access is off. Saving a mode does not create a grant; enable it here with a duration."
        except (OSError, ValueError, sqlite3.Error):
            message = "Full access status unavailable."
        self.full_access_status.setText(message)

    def enable_full_access(self):
        from ai_os.security.access_grants import GrantStore, USER_SCOPE
        if not Path("/usr/bin/bwrap").is_file():
            QMessageBox.warning(self, "Full access unavailable", "Bubblewrap is required. No unsandboxed fallback is available.")
            return
        minutes, accepted = QInputDialog.getInt(
            self, "Temporary full access", "Allow ordinary user commands for this many minutes:",
            15, 1, 1440,
        )
        if not accepted:
            self.refresh_full_access_status()
            return
        box = QMessageBox(self)
        box.setWindowTitle("Confirm temporary full access")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(f"Duration: {minutes} minutes\nSession: default (including voice requests)\n\n{USER_SCOPE}\n\nGrant only commands you understand and trust.")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            if load_raw_config(self.home)["command_access"] != "supervised":
                # Saving the mode revokes pending requests. Do this before creating
                # the token for the exact duration just confirmed by the human.
                self.saved = save_settings({"command_access": "supervised"}, self.home, human_confirmed=True)
            self.saved["command_access"] = "supervised"
            control = self.fields["command_access"]
            control.setCurrentIndex(control.findData("supervised"))
            store = GrantStore(self.home)
            request = store.request("default", {"kind": "user", "seconds": minutes*60})
            store.confirm("default", request["token"], human_confirmed=True)
            self.status.setText("Temporary full access enabled for the confirmed duration.")
        except (OSError, ValueError, PermissionError, sqlite3.Error) as exc:
            self.status.setText("Full access could not be enabled. Check its status below.")
            QMessageBox.warning(self, "Full access was not enabled", str(exc))
        self.refresh_full_access_status()

    def revoke_full_access(self):
        from ai_os.security.access_grants import revoke_all
        try:
            revoke_all(self.home)
        except (OSError, ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Access could not be revoked", str(exc))
            self.refresh_full_access_status()
            return
        self.refresh_full_access_status()
        self.status.setText("All future command grants revoked.")

    def stop_companion(self):
        from ai_os.companion_control import stop
        self.status.setText(stop()["message"])

    def ensure_companion(self):
        self.start_companion()

    def apply_cursor_size(self):
        from ai_os.cursor_size import apply
        try:
            actual = apply(self.fields["cursor_size"].value(), self.home)
            self.saved["cursor_size"] = actual
            self.status.setText(f"GNOME cursor size verified: {actual}")
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Cursor size was not applied", str(exc))

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

    def check_runtime_readiness(self):
        from PySide6.QtCore import QProcessEnvironment
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("AI_OS_HOME", str(self.home))
        process.setProcessEnvironment(env)
        self.status.setText("Checking readiness without recording or screen capture…")

        def finished(code, _status):
            text = bytes(process.readAllStandardOutput()).decode(errors="replace")[:8000]
            QMessageBox.information(self, "Runtime readiness", text if code == 0 else "Readiness check failed")
            self.status.setText("Readiness check complete. No microphone or screen capture started.")
            process.deleteLater()

        process.finished.connect(finished)
        process.start(sys.executable, ["-m", "ai_os.runtime_health"])
        QTimer.singleShot(9000, process, process.kill)

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
        self.conversation.cancel()
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
