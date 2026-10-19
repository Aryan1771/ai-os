from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QLockFile, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ai_os.companion_state import EMOTIONS, emotion_levels
from ai_os.config import DEFAULT_CONFIG
from ai_os.pixel_engine import PixelEngine, speech_mouth_frame

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
    light = QColor(bg).lightness() > 128
    border = QColor(surface).darker(118).name() if light else QColor(surface).lighter(145).name()
    hover = QColor(surface).darker(104).name() if light else QColor(surface).lighter(120).name()
    success, warning = ("#226c50", "#8a4e18") if light else ("#9ad9b9", "#ecc18c")
    return f"""
    QWidget {{ background: {bg}; color: {text}; font-family: 'Noto Sans', 'Segoe UI'; font-size: 13px; }}
    QLabel {{ background: transparent; }}
    QLabel#product {{ font-size: 23px; font-weight: 600; letter-spacing: 0.3px; }}
    QLabel#pageTitle {{ font-size: 21px; font-weight: 600; padding-bottom: 5px; }}
    QLabel#muted {{ color: {muted}; }}
    QLabel[status="success"] {{ color: {success}; }}
    QLabel[status="warning"], QLabel[status="error"] {{ color: {warning}; }}
    QLabel[status="busy"] {{ color: {accent}; }}
    QListWidget {{ border: none; padding: 8px 6px; background: {surface}; outline: 0; }}
    QListWidget::item {{ padding: 10px 10px; border-radius: 6px; margin: 3px 0; }}
    QListWidget::item:hover {{ background: {hover}; }}
    QListWidget::item:selected {{ background: {accent}; color: {bg}; }}
    QListWidget::item:focus {{ border: 1px solid {accent}; }}
    QScrollArea, QStackedWidget {{ border: none; }}
    QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {surface}; border: 1px solid {border}; border-radius: 6px;
        padding: 7px 9px; selection-background-color: {accent}; selection-color: {bg}; min-height: 20px;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {accent}; }}
    QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {{ color: {muted}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QAbstractItemView {{ background: {surface}; border: 1px solid {border}; padding: 4px;
        selection-background-color: {accent}; selection-color: {bg}; }}
    QPushButton, QToolButton {{ background: {surface}; border: 1px solid {border};
        border-radius: 6px; padding: 7px 12px; min-height: 20px; }}
    QPushButton:hover, QToolButton:hover {{ background: {hover}; border-color: {accent}; }}
    QPushButton:focus, QToolButton:focus {{ border-color: {accent}; }}
    QPushButton:pressed, QToolButton:pressed {{ background: {accent}; color: {bg}; }}
    QPushButton#primary {{ background: {accent}; color: {bg}; border-color: {accent}; font-weight: 600; }}
    QPushButton:disabled, QToolButton:disabled {{ background: {surface}; color: {muted}; border-color: {border}; }}
    QCheckBox {{ spacing: 10px; padding: 5px 0; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; }}
    QCheckBox:focus {{ color: {accent}; }}
    QSlider::groove:horizontal {{ height: 4px; background: {surface}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; background: {accent}; border-radius: 7px; }}
    QSlider::handle:horizontal:focus {{ border: 1px solid {text}; }}
    QProgressBar {{ border: none; background: {surface}; border-radius: 3px; text-align: center; }}
    QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
    QTabWidget::pane {{ border: 1px solid {border}; border-radius: 6px; padding: 8px; }}
    QTabBar::tab {{ padding: 8px 12px; background: {surface}; border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ color: {accent}; border-bottom-color: {accent}; }}
    QTabBar::tab:hover {{ background: {hover}; }}
    QGroupBox {{ border: 1px solid {border}; border-radius: 7px; margin-top: 12px; padding: 12px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; color: {muted}; }}
    QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {border}; border-radius: 3px; min-height: 28px; }}
    QScrollBar::handle:vertical:hover {{ background: {muted}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QMenu {{ background: {surface}; border: 1px solid {border}; padding: 4px; }}
    QMenu::item {{ padding: 8px 16px; }}
    QMenu::item:selected {{ background: {accent}; color: {bg}; }}
    QToolTip {{ background: {surface}; color: {text}; border: 1px solid {border}; padding: 6px; }}
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
        self.speech_elapsed = 0.0
        self.mouth_frame = None
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.advance)
        self.timer.start()
        self.set_state(self.state, self.config)

    def set_state(self, state: dict, config: dict) -> None:
        if state["phase"] == "speaking" and self.state["phase"] != "speaking":
            self.speech_elapsed = 0.0
        self.state, self.config = state, config
        self.target_levels = emotion_levels(state, config)
        self.update_form()

    def update_form(self) -> None:
        state, config = self.state, self.config
        shape = state["shape"] if state["phase"] != "idle" else config["avatar_idle_shape"]
        custom = state.get("pixels")
        if not config["avatar_topic_morphing"]:
            shape, custom = config["avatar_idle_shape"], None
        self.mouth_frame = None
        if state["phase"] == "speaking":
            # Use a known face while talking; arbitrary task/custom patterns do
            # not define mouth coordinates. Restore their form after speech.
            shape, custom = "core", None
            self.mouth_frame = (speech_mouth_frame(self.speech_elapsed)
                                if config["avatar_animation_enabled"] and config["avatar_motion"] > 0 else 0)
        self.engine.set_form(shape, self.target_levels, custom, mouth_open=self.mouth_frame)

    def advance(self) -> None:
        now = time.monotonic()
        dt, self.last_tick = min(0.05, now - self.last_tick), now
        if not self.isVisible():
            return
        if self.state["phase"] == "speaking":
            self.speech_elapsed += dt
            self.update_form()
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
