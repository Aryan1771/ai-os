from __future__ import annotations

import os
import sys
import time
import sqlite3
import signal
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer, QEvent, QPropertyAnimation, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QVBoxLayout, QWidget

from ai_os.companion_state import read_state
from ai_os.config import AI_OS_HOME, load_raw_config
from ai_os.native_widgets import CompanionCanvas, EmotionBars, LocalInstance, theme_stylesheet
from ai_os.settings_store import save_settings
from ai_os.security.access_grants import GrantStore, revoke_all


def texture_score(image):
    """Local edge-density heuristic, not OCR or semantic screen understanding."""
    if image.isNull():
        return None
    small = image.scaled(48, 48)
    edges = 0
    for x in range(1, 48):
        for y in range(1, 48):
            value = small.pixelColor(x, y).lightness()
            edges += abs(value-small.pixelColor(x-1, y).lightness()) > 24
            edges += abs(value-small.pixelColor(x, y-1).lightness()) > 24
    return edges / (47*47*2)


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
        self.pointer_since = None
        self.last_move = 0.0
        self.drag_origin = None
        self.dragged = False
        self.auto_corner = None
        self.next_proactive = time.monotonic() + 300
        self.speech_cancelled = False
        self.screen_reader = QProcess(self)
        self.screen_requested = False
        screen_environment = QProcessEnvironment.systemEnvironment()
        screen_environment.insert("AI_OS_HOME", str(home))
        self.screen_reader.setProcessEnvironment(screen_environment)
        self.screen_reader.readyReadStandardOutput.connect(self.screen_reader.readAllStandardOutput)
        self.screen_reader.readyReadStandardError.connect(self.screen_reader.readAllStandardError)
        self.motion = QPropertyAnimation(self, b"pos", self)
        self.motion.setDuration(250)
        self.speaker = QProcess(self)
        if sys.platform == "linux":
            self.speaker.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("AI_OS_HOME", str(home))
        self.speaker.setProcessEnvironment(environment)
        self.speech_timeout = QTimer(self)
        self.speech_timeout.setSingleShot(True)
        self.speech_timeout.setInterval(90_000)
        self.speech_timeout.timeout.connect(self.stop_speech)
        self.speaker.finished.connect(self.speech_finished)
        self.setWindowTitle("REgenOS Companion")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.canvas = CompanionCanvas()
        self.canvas.installEventFilter(self)
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
            if config["screen_context_enabled"] and not self.screen_requested:
                self.screen_requested = True
                self.screen_reader.start(sys.executable, ["-m", "ai_os.screen_observer"])
            elif not config["screen_context_enabled"] and self.screen_requested:
                self.screen_requested = False
                self.stop_screen_reader()
            if not self.last_config or any(config[key] != self.last_config[key] for key in ("proactive_speech_enabled", "proactive_interval_minutes")):
                self.next_proactive = time.monotonic() + config["proactive_interval_minutes"] * 60
            if not self.last_config or config["avatar_corner"] != self.last_config["avatar_corner"]:
                self.auto_corner = None
            self.last_config = config
            branding = config["branding"]
            self.setWindowTitle(f"{branding['brand_name']} {branding['assistant_name']}")
            scale = config["avatar_scale"] / 100
            self.canvas.setFixedHeight(round(230 * scale))
            self.setStyleSheet(
                theme_stylesheet(config["theme"]) + "AvatarOverlay {background: transparent;}"
            )
            self.bars.setVisible(config["avatar_show_emotion_bars"])
            self.setVisible(config["avatar_enabled"])
            self.place()
        state = read_state(self.home)
        self.canvas.set_state(state, config)
        self.status.setText(state["phase"].capitalize())
        if config["avatar_show_status"]:
            mood = max(self.canvas.target_levels, key=self.canvas.target_levels.get)
            self.status.setText(f"{state['phase'].capitalize()} · {mood.capitalize()}")
        if GrantStore(self.home).path.exists():
            try:
                access = GrantStore(self.home).status("default")
                if "request" in access:
                    self.status.setText("Access request · open Settings")
                elif "grant" in access:
                    seconds = max(0, int(access["grant"]["deadline"] - time.monotonic()))
                    self.status.setText(f"Access active · {seconds}s")
            except (OSError, ValueError, sqlite3.Error):
                self.status.setText("Access status unavailable")
        # Debug labels are optional; microphone/permission/speech state is not.
        wake_enabled = config["always_listening_enabled"] and config["wake_word_enabled"]
        if wake_enabled and state["phase"] in {"idle", "reply"} and not self.status.text().startswith("Access"):
            self.status.setText("Wake listening enabled · " + state["phase"].capitalize())
        important = wake_enabled or state["phase"] in {"armed", "listening", "transcribing", "speaking"} or self.status.text().startswith("Access")
        show_status = config["avatar_show_status"] or important
        self.status.setVisible(show_status)
        height = self.canvas.height() + 8 + (27 if show_status else 0) + (129 if config["avatar_show_emotion_bars"] else 0)
        if self.height() != height:
            self.setFixedSize(max(210, round(260 * config["avatar_scale"] / 100)), height)
            self.place()
        self.avoid_pointer()
        now = time.monotonic()
        if not config["proactive_speech_enabled"] or not config["speech_enabled"]:
            self.next_proactive = now + config["proactive_interval_minutes"] * 60
            if self.speaker.state() != QProcess.ProcessState.NotRunning:
                self.stop_speech()
        elif now >= self.next_proactive and state["phase"] in {"idle", "armed"} and self.isVisible():
            self.next_proactive = now + config["proactive_interval_minutes"] * 60
            self.speak_proactively()

    def place(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if not screen or not self.last_config:
            return
        rect = screen.availableGeometry()
        corner = self.auto_corner or self.last_config["avatar_corner"]
        x = rect.left() + 18 if "left" in corner else rect.right() - self.width() - 18
        y = rect.top() + 18 if "top" in corner else rect.bottom() - self.height() - 18
        self.move(x, y)

    def move_away(self):
        screen = self.screen()
        if not screen:
            return
        rect, pointer = screen.availableGeometry(), QCursor.pos()
        self.auto_corner = ("bottom" if pointer.y() < rect.center().y() else "top") + ("-right" if pointer.x() < rect.center().x() else "-left")
        if self.last_config["avatar_screen_awareness"]:
            # Only this opt-in path captures pixels. No disk, OCR, networking or model input.
            full = screen.grabWindow(0).toImage()
            if not full.isNull():
                geometry = screen.geometry()
                ratio_x, ratio_y = full.width()/geometry.width(), full.height()/geometry.height()
                choices = []
                for corner in ("top-left", "top-right", "bottom-left", "bottom-right"):
                    x = rect.left()+18 if "left" in corner else rect.right()-self.width()-18
                    y = rect.top()+18 if "top" in corner else rect.bottom()-self.height()-18
                    candidate = self.geometry().translated(x-self.x(), y-self.y())
                    if candidate.contains(pointer) or candidate.intersects(self.frameGeometry()):
                        continue
                    area = full.copy(round((x-geometry.x())*ratio_x), round((y-geometry.y())*ratio_y),
                                     round(self.width()*ratio_x), round(self.height()*ratio_y))
                    score = texture_score(area)
                    if score is not None:
                        choices.append((score, corner))
                if choices:
                    self.auto_corner = min(choices)[1]
        start = self.pos()
        self.place()
        end = self.pos()
        self.move(start)
        self.motion.stop()
        self.motion.setStartValue(start)
        self.motion.setEndValue(end)
        self.motion.start()
        self.last_move = time.monotonic()
        self.pointer_since = None

    def avoid_pointer(self):
        if not self.last_config["avatar_auto_move"] or self.drag_origin is not None or not self.isVisible():
            return
        now = time.monotonic()
        if now - self.last_move < 10 or not self.frameGeometry().adjusted(-12, -12, 12, 12).contains(QCursor.pos()):
            self.pointer_since = None
            return
        if self.pointer_since is None:
            self.pointer_since = now
        elif now - self.pointer_since > 2:
            self.move_away()

    def eventFilter(self, watched, event):
        if watched is self.canvas:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.motion.stop()
                self.drag_origin = event.globalPosition().toPoint() - self.pos()
                self.dragged = False
                return True
            if event.type() == QEvent.Type.MouseMove and self.drag_origin is not None:
                point = event.globalPosition().toPoint() - self.drag_origin
                self.dragged |= (point-self.pos()).manhattanLength() > 4
                if self.dragged:
                    rect = self.screen().availableGeometry()
                    self.move(QPoint(max(rect.left(), min(point.x(), rect.right()-self.width()+1)),
                                     max(rect.top(), min(point.y(), rect.bottom()-self.height()+1))))
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and self.drag_origin is not None:
                self.drag_origin = None
                self.last_move = time.monotonic() + 290  # Respect manual placement for five minutes.
                if not self.dragged:
                    self.open_settings()
                return True
        return super().eventFilter(watched, event)

    def speak_proactively(self):
        if self.speaker.state() != QProcess.ProcessState.NotRunning:
            return
        self.speech_cancelled = False
        self.speaker.start(sys.executable, ["-m", "ai_os.hub_bridge"])
        self.speaker.write(b'{"action":"proactive_speech"}')
        self.speaker.closeWriteChannel()
        self.speech_timeout.start()

    def stop_speech(self):
        self.speech_timeout.stop()
        if self.speaker.state() != QProcess.ProcessState.NotRunning:
            self.speech_cancelled = True
            pid = self.speaker.processId()
            if sys.platform == "linux" and pid > 0:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            self.speaker.terminate()
            if not self.speaker.waitForFinished(1000):
                if sys.platform == "linux" and pid > 0:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                self.speaker.kill()
                self.speaker.waitForFinished(1000)

    def speech_finished(self, code, _status):
        self.speech_timeout.stop()
        self.speaker.readAllStandardOutput()
        self.speaker.readAllStandardError()
        from ai_os.companion_state import publish_state
        publish_state("error" if code and not self.speech_cancelled else "idle", home=self.home)

    def open_settings(self) -> None:
        QProcess.startDetached(sys.executable, ["-m", "ai_os.hub_launcher"])

    def contextMenuEvent(self, event) -> None:
        self.last_move = time.monotonic() + 30
        menu = QMenu(self)
        menu.addAction("Settings", self.open_settings)
        menu.addAction("Move out of the way", self.move_away)
        for key, label in (("avatar_show_emotion_bars", "Debug emotion bars"), ("avatar_show_status", "Debug mood/activity label"), ("avatar_auto_move", "Move away from pointer")):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.last_config[key])
            action.toggled.connect(lambda value, key=key: save_settings({key: value}, self.home))
        menu.addAction("Stop proactive speech", lambda: (save_settings({"proactive_speech_enabled": False}, self.home, human_confirmed=True), self.stop_speech()))
        menu.addAction("Stop screen awareness", lambda: (save_settings({"screen_context_enabled": False}, self.home, human_confirmed=True), self.stop_screen_reader()))
        menu.addAction("Revoke all access grants", lambda: revoke_all(self.home))
        menu.addAction(
            "Hide companion", lambda: save_settings({"avatar_enabled": False}, self.home)
        )
        menu.exec(event.globalPos())

    def stop_screen_reader(self):
        if self.screen_reader.state() != QProcess.ProcessState.NotRunning:
            self.screen_reader.terminate()
            if not self.screen_reader.waitForFinished(2000):
                self.screen_reader.kill()
                self.screen_reader.waitForFinished(1000)

    def closeEvent(self, event):
        self.stop_screen_reader()
        self.stop_speech()
        self.timer.stop()
        super().closeEvent(event)


def main() -> int:
    # XWayland allows explicit corner positioning; Qt Wayland clients cannot place themselves.
    if sys.platform == "linux" and os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(["regenos-companion"])
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    app.setStyle("Fusion")
    app.setApplicationName("regenos-companion")
    app.setDesktopFileName("regenos-companion")
    app.setQuitOnLastWindowClosed(False)
    instance = LocalInstance(AI_OS_HOME, "regenos-companion")
    if not instance.acquire(lambda: None):
        return 0
    overlay = AvatarOverlay()
    app.aboutToQuit.connect(overlay.timer.stop)
    app.aboutToQuit.connect(overlay.stop_screen_reader)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
