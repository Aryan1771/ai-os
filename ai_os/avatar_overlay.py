from __future__ import annotations

import os
import argparse
import json
import sys
import time
import sqlite3
import signal
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer, QEvent, QPropertyAnimation, QPoint
from PySide6.QtGui import QActionGroup, QCursor
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QMessageBox, QVBoxLayout, QWidget

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


def placement_report(home: Path = AI_OS_HOME) -> dict:
    """Read configuration/display geometry without constructing or raising an overlay."""
    app = QApplication.instance()
    screens = []
    if app is not None:
        for screen in app.screens():
            rect = screen.availableGeometry()
            screens.append({"name": screen.name(), "available": [rect.x(), rect.y(), rect.width(), rect.height()]})
    enabled, selected, error = None, "", ""
    try:
        with (home / "config.json").open("r", encoding="utf-8") as handle:
            saved = handle.read(65537)
        if len(saved) > 65536:
            raise ValueError()
        config = json.loads(saved)
        if not isinstance(config, dict):
            raise ValueError()
        enabled = config.get("avatar_enabled", True)
        selected = config.get("avatar_display", "")
        if not isinstance(enabled, bool) or not isinstance(selected, str) or len(selected) > 255:
            enabled, selected = None, ""
            raise ValueError()
    except (OSError, ValueError, TypeError):
        error = "Saved companion preferences are unavailable; no settings were changed."
    return {
        "ok": bool(screens) and not error,
        "configured_visible": enabled,
        "configured_display": selected,
        "configured_display_connected": any(screen["name"] == selected for screen in screens) if selected else None,
        "platform": app.platformName() if app is not None else "unavailable",
        "screens": screens,
        "message": error or "Configuration and available displays only; this does not prove the resident avatar is visible.",
        "recovery": "Run regenos-companion --show from the graphical desktop terminal to unhide and reposition the companion.",
    }


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
        self.selected_screen_name = ""
        self.next_proactive = time.monotonic() + 300
        self.speech_cancelled = False
        self.speaker_group = None
        self.settings_launch_error_until = 0.0
        self.control_notice = ""
        self.control_notice_until = 0.0
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
        self.speaker.started.connect(self.remember_speech_group)
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
        app.screenAdded.connect(self.screen_added)
        app.screenRemoved.connect(lambda _screen: self.place())
        for screen in app.screens():
            self.watch_screen(screen)

    def reveal_if_enabled(self):
        """Recover an existing resident window, while honoring hidden startup."""
        self.refresh()
        if self.last_config and self.last_config["avatar_enabled"]:
            self.place()
            self.show()
            self.raise_()

    def refresh(self) -> None:
        try:
            config = load_raw_config(self.home)
        except (OSError, ValueError, TypeError):
            return
        if config != self.last_config:
            geometry_changed = not self.last_config or any(
                config[key] != self.last_config[key] for key in
                ("avatar_corner", "avatar_display", "avatar_scale", "avatar_show_status", "avatar_show_emotion_bars")
            )
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
            self.selected_screen_name = config["avatar_display"]
            self.last_config = config
            branding = config["branding"]
            self.setWindowTitle(f"{branding['brand_name']} {branding['assistant_name']}")
            scale = config["avatar_scale"] / 100
            if geometry_changed:
                self.canvas.setFixedHeight(round(230 * scale))
            self.setStyleSheet(
                theme_stylesheet(config["theme"]) + "AvatarOverlay {background: transparent;}"
            )
            self.bars.setVisible(config["avatar_show_emotion_bars"])
            self.setVisible(config["avatar_enabled"])
            if geometry_changed:
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
        wake_enabled = config["always_listening_enabled"]
        if wake_enabled and state["phase"] in {"idle", "reply"} and not self.status.text().startswith("Access"):
            label = "Wake listening" if config["wake_word_enabled"] else "Conversation listening" if config["conversation_listening_enabled"] else "Choose listening mode"
            self.status.setText((label + " enabled" if label != "Choose listening mode" else label)
                                + " · " + state["phase"].capitalize())
        important = wake_enabled or state["phase"] in {"armed", "listening", "transcribing", "speaking"} or self.status.text().startswith("Access")
        if config["desktop_context_enabled"]:
            self.status.setText(self.status.text() + " · Accessibility on")
            important = True
        if config["activity_memory_enabled"]:
            self.status.setText(self.status.text() + " · App usage memory on")
            important = True
        if config["speaker_recognition_enabled"]:
            self.status.setText(self.status.text() + " · Enrolled voice filter on")
            important = True
        if time.monotonic() < self.settings_launch_error_until:
            self.status.setText(self.status.text() + " · Settings failed; run regenos-settings")
            important = True
        if time.monotonic() < self.control_notice_until:
            self.status.setText(self.status.text() + " · " + self.control_notice)
            self.status.setToolTip(self.control_notice)
            important = True
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

    def watch_screen(self, screen):
        screen.availableGeometryChanged.connect(lambda _rect: self.place())
        screen.geometryChanged.connect(lambda _rect: self.place())

    def screen_added(self, screen):
        self.watch_screen(screen)
        self.place()

    def preferred_screen(self):
        screens = QApplication.screens()
        return next((s for s in screens if s.name() == self.selected_screen_name), None) or (
            self.screen() if self.screen() in screens else QApplication.primaryScreen()
        )

    def move_to_screen(self, name):
        if not any(screen.name() == name for screen in QApplication.screens()):
            return False
        self.motion.stop()
        save_settings({"avatar_display": name}, self.home)
        self.selected_screen_name = name
        if self.last_config:
            self.last_config["avatar_display"] = name
        self.last_move = time.monotonic() + 290
        self.place()
        return True

    def drag_to(self, global_pointer):
        target = QApplication.screenAt(global_pointer) or self.preferred_screen()
        if target is None:
            return
        self.selected_screen_name = target.name()
        rect = target.availableGeometry()
        self.fit_workarea(rect)
        point = global_pointer - self.drag_origin
        self.move(QPoint(max(rect.left(), min(point.x(), rect.right()-self.width()+1)),
                         max(rect.top(), min(point.y(), rect.bottom()-self.height()+1))))

    def place(self) -> None:
        screen = self.preferred_screen()
        if not screen or not self.last_config:
            return
        rect = screen.availableGeometry()
        self.motion.stop()
        self.fit_workarea(rect)
        corner = self.auto_corner or self.last_config["avatar_corner"]
        x = rect.left() + 18 if "left" in corner else rect.right() - self.width() - 17
        y = rect.top() + 18 if "top" in corner else rect.bottom() - self.height() - 17
        x = max(rect.left(), min(x, rect.right() - self.width() + 1))
        y = max(rect.top(), min(y, rect.bottom() - self.height() + 1))
        self.move(x, y)

    def fit_workarea(self, rect):
        """Fit the runtime window without changing the saved size preference."""
        if not self.last_config or rect.isEmpty():
            return
        width = min(max(210, round(260 * self.last_config["avatar_scale"] / 100)), rect.width())
        chrome = 8 + (27 if not self.status.isHidden() else 0) + (129 if self.last_config["avatar_show_emotion_bars"] else 0)
        canvas_height = min(round(230 * self.last_config["avatar_scale"] / 100), max(1, rect.height() - chrome))
        self.canvas.setFixedHeight(canvas_height)
        self.setFixedSize(width, min(rect.height(), canvas_height + chrome))

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
                    self.drag_to(event.globalPosition().toPoint())
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and self.drag_origin is not None:
                self.drag_origin = None
                if self.dragged:
                    save_settings({"avatar_display": self.selected_screen_name}, self.home)
                    self.last_config["avatar_display"] = self.selected_screen_name
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

    def remember_speech_group(self):
        if sys.platform != "linux":
            return
        pid = self.speaker.processId()
        try:
            if pid > 1 and pid != os.getpgrp() and os.getpgid(pid) == pid:
                self.speaker_group = pid
        except (ProcessLookupError, PermissionError):
            pass

    def signal_speech_group(self, signum):
        if self.speaker_group is None:
            return False
        try:
            os.killpg(self.speaker_group, signum)
        except ProcessLookupError:
            pass
        except PermissionError:
            return False
        return True

    def stop_speech(self):
        self.speech_timeout.stop()
        self.speech_cancelled = True
        if self.speaker.state() != QProcess.ProcessState.NotRunning:
            self.remember_speech_group()
            if not self.signal_speech_group(signal.SIGTERM):
                self.speaker.terminate()
            if not self.speaker.waitForFinished(1000):
                self.signal_speech_group(signal.SIGKILL)
                self.speaker.kill()
                self.speaker.waitForFinished(1000)
        # A descendant can ignore TERM after the worker itself has exited.
        self.signal_speech_group(signal.SIGKILL)
        self.speaker_group = None

    def speech_finished(self, code, _status):
        self.speech_timeout.stop()
        self.signal_speech_group(signal.SIGKILL)
        self.speaker_group = None
        self.speaker.readAllStandardOutput()
        self.speaker.readAllStandardError()
        from ai_os.companion_state import publish_state
        publish_state("error" if code and not self.speech_cancelled else "idle", home=self.home)

    def open_settings(self) -> bool:
        process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("AI_OS_HOME", str(self.home))
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments(["-m", "ai_os.hub_launcher"])
        try:
            result = process.startDetached()
            success = result[0] if isinstance(result, tuple) else result
        except (OSError, RuntimeError):
            success = False
        process.deleteLater()
        if not success:
            self.settings_launch_error_until = time.monotonic() + 10
            self.status.setText("Settings could not start; run regenos-settings from a desktop terminal.")
            self.status.show()
        return bool(success)

    def notify_control(self, text):
        self.control_notice, self.control_notice_until = text, time.monotonic() + 10
        self.status.setText(text)
        self.status.setToolTip(text)
        self.status.show()
        self.status.repaint()

    def confirm_sensor_start(self, title, text):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Question)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def set_listening(self, enabled):
        try:
            config = load_raw_config(self.home)
            if enabled and not config["always_listening_enabled"]:
                if not (config["wake_word_enabled"] or config["conversation_listening_enabled"]):
                    self.notify_control("Choose wake-word or conversation listening in Voice settings first.")
                    return False
                mode = "wake-word detection" if config["wake_word_enabled"] else "continuous conversation listening without a wake word"
                if not self.confirm_sensor_start("Enable microphone listening?",
                    "Enable " + mode + " using the saved local voice settings? Nearby speech may be captured. "
                    "Recognized requests follow the saved memory and command-permission policy. "
                    "The current speaker filter is not command or login authorization. "
                    "The core must already be running; this does not start or change a service. "
                    "You can disable listening from this menu at any time."):
                    return False
                if load_raw_config(self.home) != config:
                    self.notify_control("Settings changed during approval; review and start the microphone again.")
                    return False
            save_settings({"always_listening_enabled": bool(enabled)}, self.home, human_confirmed=True)
            self.refresh()
            self.notify_control("Microphone enabled in settings; check Voice status for capture readiness." if enabled
                                else "Microphone stop requested; saved listening is off.")
            return True
        except (OSError, ValueError, TypeError):
            self.notify_control("Microphone setting could not be changed; open Voice settings.")
            return False

    def set_screen_sharing(self, enabled):
        try:
            config = load_raw_config(self.home)
            if enabled and not config["screen_context_enabled"]:
                if not self.confirm_sensor_start("Enable local screen awareness?",
                    "Start the native screen-sharing selector? Only a screen you explicitly select is read locally. "
                    "Visible text is temporary, is not saved as memory, and cannot authorize actions. "
                    "Remote AI providers receive no screen context. Use Stop screen sharing or Pause to disable it."):
                    return False
                if load_raw_config(self.home) != config:
                    self.notify_control("Settings changed during approval; review and start screen sharing again.")
                    return False
            save_settings({"screen_context_enabled": bool(enabled)}, self.home, human_confirmed=True)
            if not enabled:
                self.screen_requested = False
                self.notify_control("Stopping screen sharing and clearing its local context…")
                self.stop_screen_reader()
            self.refresh()
            self.notify_control("Screen sharing requested; choose a screen in the desktop selector." if enabled
                                else "Screen sharing disabled.")
            return True
        except (OSError, ValueError, TypeError):
            self.notify_control("Screen-sharing setting could not be changed; open Companion settings.")
            return False

    def set_overlay_option(self, key, value):
        try:
            save_settings({key: value}, self.home)
            self.refresh()
        except (OSError, ValueError, TypeError):
            self.notify_control("Companion preference could not be saved.")

    def set_render_mode(self, mode):
        try:
            save_settings({"avatar_render_mode": mode}, self.home)
            self.refresh()
            self.notify_control("3D depth appearance selected (up to 24 frames/s)." if mode == "3d"
                                else "2D particles selected — lighter rendering.")
            return True
        except (OSError, ValueError, TypeError):
            self.notify_control("Hologram appearance could not be saved.")
            return False

    def build_context_menu(self):
        self.last_move = time.monotonic() + 30
        try:
            config = load_raw_config(self.home)
        except (OSError, ValueError, TypeError):
            config = self.last_config
        menu = QMenu(self)
        menu.addAction("Settings", self.open_settings)
        menu.addAction("Move out of the way", self.move_away)
        appearance = menu.addMenu("Hologram appearance")
        render_group = QActionGroup(appearance)
        render_group.setExclusive(True)
        selected_mode = config.get("avatar_render_mode", "2d") if config else "2d"
        for mode, label in (("2d", "2D particles — lighter"), ("3d", "3D depth appearance")):
            action = appearance.addAction(label)
            action.setCheckable(True)
            action.setChecked(mode == selected_mode)
            render_group.addAction(action)
            action.triggered.connect(lambda _checked=False, mode=mode: self.set_render_mode(mode))
        displays = menu.addMenu("Move to display")
        for index, screen in enumerate(QApplication.screens(), 1):
            name = screen.name()
            action = displays.addAction(f"{index}: {name.replace(chr(38), chr(38)*2)}")
            action.setCheckable(True)
            action.setChecked(screen is self.preferred_screen())
            action.triggered.connect(lambda _checked=False, name=name: self.move_to_screen(name))
        for key, label in (("avatar_show_emotion_bars", "Debug emotion bars"), ("avatar_show_status", "Debug mood/activity label"), ("avatar_auto_move", "Move away from pointer")):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(config.get(key, False) if config else False)
            action.toggled.connect(lambda value, key=key: self.set_overlay_option(key, value))
        menu.addAction("Stop proactive speech", lambda: (save_settings({"proactive_speech_enabled": False}, self.home, human_confirmed=True), self.stop_speech()))
        sharing = bool(config and config.get("screen_context_enabled"))
        menu.addAction("Stop screen sharing" if sharing else "Start screen sharing…",
                       lambda: self.set_screen_sharing(not sharing))
        listening = bool(config and config.get("always_listening_enabled"))
        menu.addAction("Stop microphone" if listening else "Start microphone…",
                       lambda: self.set_listening(not listening))
        menu.addAction("Revoke all access grants", lambda: revoke_all(self.home))
        menu.addAction(
            "Hide companion", lambda: self.set_overlay_option("avatar_enabled", False)
        )
        menu.addAction("Quit companion", QApplication.instance().quit)
        return menu

    def contextMenuEvent(self, event) -> None:
        menu = self.build_context_menu()
        menu.exec(event.globalPos())
        menu.deleteLater()

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
    parser = argparse.ArgumentParser(description="REgenOS native companion")
    flags = parser.add_mutually_exclusive_group()
    flags.add_argument("--show", action="store_true", help="Reveal the companion even when saved as hidden")
    flags.add_argument("--status", action="store_true", help="Report saved visibility and current display geometry without activating the companion")
    args = parser.parse_args()
    if args.show:
        save_settings({"avatar_enabled": True}, AI_OS_HOME)
    # XWayland allows explicit corner positioning; Qt Wayland clients cannot place themselves.
    if sys.platform == "linux" and os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(["regenos-companion"])
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    app.setStyle("Fusion")
    app.setApplicationName("regenos-companion")
    app.setDesktopFileName("regenos-companion")
    from ai_os.brand_assets import brand_icon
    app.setWindowIcon(brand_icon())
    app.setQuitOnLastWindowClosed(False)
    if args.status:
        result = placement_report()
        print(json.dumps(result, ensure_ascii=True))
        return 0 if result["ok"] else 1
    overlay = None

    def activate():
        if overlay is not None:
            overlay.reveal_if_enabled()

    instance = LocalInstance(AI_OS_HOME, "regenos-companion")
    if not instance.acquire(activate):
        return 0
    overlay = AvatarOverlay()
    app.aboutToQuit.connect(overlay.timer.stop)
    app.aboutToQuit.connect(overlay.stop_screen_reader)
    app.aboutToQuit.connect(overlay.stop_speech)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
