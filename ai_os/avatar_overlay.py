from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QVBoxLayout, QWidget

from ai_os.companion_state import read_state
from ai_os.config import AI_OS_HOME, load_raw_config
from ai_os.native_widgets import CompanionCanvas, EmotionBars, LocalInstance, theme_stylesheet
from ai_os.settings_store import save_settings


class AvatarOverlay(QWidget):
    def __init__(self, home: Path = AI_OS_HOME) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.home = home
        self.setWindowTitle("REgenOS Companion")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.canvas = CompanionCanvas()
        self.status = QLabel("Idle")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setFixedHeight(24)
        self.bars = EmotionBars(compact=True)
        self.bars.setFixedHeight(126)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 8)
        layout.setSpacing(3)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.bars)
        self.canvas.levels_changed.connect(self.bars.set_levels)
        self.canvas.clicked.connect(self.open_settings)
        self.last_config = None
        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()
        app = QApplication.instance()
        app.screenAdded.connect(lambda _screen: self.place())
        app.screenRemoved.connect(lambda _screen: self.place())
        for screen in app.screens():
            screen.availableGeometryChanged.connect(lambda _rect: self.place())

    def refresh(self) -> None:
        try:
            config = load_raw_config(self.home)
        except (OSError, ValueError, TypeError):
            return
        if config != self.last_config:
            self.last_config = config
            branding = config["branding"]
            self.setWindowTitle(f"{branding['brand_name']} {branding['assistant_name']}")
            scale = config["avatar_scale"] / 100
            self.canvas.setFixedHeight(round(230 * scale))
            self.setFixedSize(
                max(210, round(260 * scale)),
                round(230 * scale) + 30 + (138 if config["avatar_show_emotion_bars"] else 0),
            )
            self.setStyleSheet(
                theme_stylesheet(config["theme"]) + "AvatarOverlay {background: transparent;}"
            )
            self.bars.setVisible(config["avatar_show_emotion_bars"])
            self.setVisible(config["avatar_enabled"])
            self.place()
        state = read_state(self.home)
        self.canvas.set_state(state, config)
        self.status.setText(state["phase"].capitalize())

    def place(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen or not self.last_config:
            return
        rect = screen.availableGeometry()
        corner = self.last_config["avatar_corner"]
        x = rect.left() + 18 if "left" in corner else rect.right() - self.width() - 18
        y = rect.top() + 18 if "top" in corner else rect.bottom() - self.height() - 18
        self.move(x, y)

    def open_settings(self) -> None:
        QProcess.startDetached(sys.executable, ["-m", "ai_os.hub_launcher"])

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("Settings", self.open_settings)
        menu.addAction(
            "Hide companion", lambda: save_settings({"avatar_enabled": False}, self.home)
        )
        menu.exec(event.globalPos())


def main() -> int:
    # XWayland allows explicit corner positioning; Qt Wayland clients cannot place themselves.
    if sys.platform == "linux" and os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(["regenos-companion"])
    app.setStyle("Fusion")
    app.setApplicationName("regenos-companion")
    app.setDesktopFileName("regenos-companion")
    app.setQuitOnLastWindowClosed(False)
    instance = LocalInstance(AI_OS_HOME, "regenos-companion")
    if not instance.acquire(lambda: None):
        return 0
    overlay = AvatarOverlay()
    app.aboutToQuit.connect(overlay.timer.stop)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
