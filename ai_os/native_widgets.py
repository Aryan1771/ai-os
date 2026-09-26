from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QLockFile, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ai_os.companion_state import EMOTIONS, emotion_levels
from ai_os.config import DEFAULT_CONFIG
from ai_os.pixel_engine import PixelEngine

EMOTION_COLORS = {
    "joy": "#e8ba71",
    "curiosity": "#79c8de",
    "focus": "#b6baf3",
    "calm": "#72d4ad",
    "concern": "#ee9188",
    "energy": "#d8cb81",
}
THEMES = {
    "forest": ("#14191b", "#1e2629", "#e9f0f0", "#9baeb3", "#72d4ad"),
    "graphite": ("#202020", "#2b2b2b", "#e5e5e5", "#a0a0a0", "#79b8ec"),
    "ocean": ("#151c21", "#222e34", "#ecf5f7", "#a0b4be", "#79c8de"),
    "light": ("#f3f5f7", "#ffffff", "#222a30", "#586872", "#147c62"),
    "sunrise": ("#202024", "#2b2b30", "#f5f3f0", "#b0aaaf", "#e6a575"),
}


def theme_stylesheet(name: str) -> str:
    bg, surface, text, muted, accent = THEMES.get(name, THEMES["graphite"])
    return f"""
    QWidget {{ background: {bg}; color: {text}; font-family: 'Noto Sans', 'Segoe UI'; font-size: 13px; }}
    QLabel#product {{ font-size: 23px; font-weight: 650; }}
    QLabel#pageTitle {{ font-size: 21px; font-weight: 600; }}
    QLabel#muted {{ color: {muted}; }}
    QListWidget {{ border: none; padding: 6px; background: {surface}; }}
    QListWidget::item {{ padding: 12px 10px; border-radius: 5px; margin: 2px 0; }}
    QListWidget::item:selected {{ background: {accent}; color: {bg}; }}
    QScrollArea, QStackedWidget {{ border: none; }}
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {surface}; border: 1px solid {muted}; border-radius: 4px;
        padding: 7px; selection-background-color: {accent}; min-height: 20px;
    }}
    QPushButton, QToolButton {{ background: {surface}; border: 1px solid {muted};
        border-radius: 4px; padding: 7px 12px; min-height: 20px; }}
    QPushButton:hover, QToolButton:hover {{ border-color: {accent}; }}
    QPushButton#primary {{ background: {accent}; color: {bg}; border-color: {accent}; font-weight: 600; }}
    QPushButton:disabled {{ color: {muted}; }}
    QCheckBox {{ spacing: 10px; padding: 5px 0; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; }}
    QSlider::groove:horizontal {{ height: 4px; background: {surface}; }}
    QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; background: {accent}; border-radius: 7px; }}
    QProgressBar {{ border: none; background: {surface}; border-radius: 3px; text-align: center; }}
    QMenu {{ background: {surface}; border: 1px solid {muted}; }}
    QMenu::item {{ padding: 8px 16px; }}
    QMenu::item:selected {{ background: {accent}; color: {bg}; }}
    """


class LocalInstance:
    """A user-local socket raises the existing window; no TCP server is involved."""

    def __init__(self, home: Path, name: str) -> None:
        (home / "run").mkdir(parents=True, exist_ok=True)
        self.address = str(home / "run" / f"{name}.sock")
        self.lock = QLockFile(str(home / "run" / f"{name}.lock"))
        self.lock.setStaleLockTime(0)
        self.server = QLocalServer()
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)

    def acquire(self, activate) -> bool:
        if not self.lock.tryLock(0):
            socket = QLocalSocket()
            socket.connectToServer(self.address)
            if socket.waitForConnected(500):
                socket.write(b"show")
                socket.waitForBytesWritten(500)
                socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.address)
        if not self.server.listen(self.address):
            self.lock.unlock()
            raise RuntimeError(self.server.errorString())

        def receive():
            while self.server.hasPendingConnections():
                socket = self.server.nextPendingConnection()
                socket.close()
                socket.deleteLater()
                activate()

        self.server.newConnection.connect(receive)
        return True


class EmotionBars(QWidget):
    def __init__(self, compact: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.bars = {}
        self.values = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(4 if compact else 9)
        for key in EMOTIONS:
            row = QHBoxLayout()
            label = QLabel(key.capitalize())
            label.setFixedWidth(60 if compact else 70)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(10 if compact else 17)
            bar.setTextVisible(False)
            bar.setAccessibleName(key.capitalize())
            bar.setStyleSheet(
                f"QProgressBar::chunk {{background: {EMOTION_COLORS[key]}; border-radius: 3px;}}"
            )
            self.bars[key] = bar
            row.addWidget(label)
            row.addWidget(bar, 1)
            if not compact:
                value = QLabel("0")
                value.setFixedWidth(30)
                value.setAlignment(Qt.AlignmentFlag.AlignRight)
                self.values[key] = value
                row.addWidget(value)
            layout.addLayout(row)

    def set_levels(self, levels: dict[str, float]) -> None:
        for key, bar in self.bars.items():
            bar.setValue(round(levels[key]))
            if key in self.values:
                self.values[key].setText(str(round(levels[key])))


class CompanionCanvas(QWidget):
    levels_changed = Signal(dict)
    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(96, 96)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("CompanionCanvas {background: transparent;}")
        self.setAccessibleName("REgenOS pixel companion")
        self.engine = PixelEngine()
        self.config = DEFAULT_CONFIG.copy()
        self.state = {"phase": "idle", "shape": "core", "emotions": {}, "pixels": None}
        self.levels = dict(DEFAULT_CONFIG["avatar_emotions"])
        self.target_levels = self.levels.copy()
        self.last_tick = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.advance)
        self.timer.start()
        self.set_state(self.state, self.config)

    def set_state(self, state: dict, config: dict) -> None:
        self.state, self.config = state, config
        self.target_levels = emotion_levels(state, config)
        shape = state["shape"] if state["phase"] != "idle" else config["avatar_idle_shape"]
        custom = state.get("pixels")
        if not config["avatar_topic_morphing"]:
            shape, custom = config["avatar_idle_shape"], None
        self.engine.set_form(shape, self.target_levels, custom)

    def advance(self) -> None:
        now = time.monotonic()
        dt, self.last_tick = min(0.05, now - self.last_tick), now
        if not self.isVisible():
            return
        for key in self.levels:
            self.levels[key] += (self.target_levels[key] - self.levels[key]) * min(1, dt * 5)
        self.engine.advance(
            dt, self.config["avatar_motion"] / 100, self.config["avatar_animation_enabled"]
        )
        self.levels_changed.emit(self.levels.copy())
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        unit = min(self.width(), self.height()) / 27
        colors = {"#": "#b3c8d1", "+": self.config["avatar_accent"], "*": "#edbd79", "o": "#142126"}
        for pixel in self.engine.pixels:
            if pixel.opacity < 0.01:
                continue
            color = QColor(colors[pixel.material])
            color.setAlphaF(max(0, min(1, pixel.opacity)))
            painter.setBrush(color)
            x, y = self.width() / 2 + pixel.x * unit, self.height() / 2 + pixel.y * unit
            side = unit * 0.91
            painter.drawRect(QRectF(x - side / 2, y - side / 2, side, side))
        painter.end()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
