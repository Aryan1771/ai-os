"""Workarea recovery and child-process cleanup without screen/audio capture."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QProcess, QRect
from PySide6.QtWidgets import QApplication

from ai_os import avatar_overlay as avatar
from ai_os import conversation_widget as chat
from ai_os import quick_chat
from ai_os.config import load_raw_config
from ai_os.settings_store import save_settings


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["native-recovery-test"])


class Screen:
    def __init__(self, name, rect):
        self._name, self.rect = name, rect
        self.availableGeometryChanged = SimpleNamespace(connect=lambda _fn: None)
        self.geometryChanged = SimpleNamespace(connect=lambda _fn: None)

    def name(self):
        return self._name

    def availableGeometry(self):
        return self.rect


@pytest.fixture
def overlay(app, tmp_path, monkeypatch):
    available = [Screen("large", QRect(0, 0, 1920, 1080)),
                 Screen("small", QRect(-640, -200, 300, 340))]
    monkeypatch.setattr(QApplication, "screens", lambda *_args: available)
    monkeypatch.setattr(QApplication, "primaryScreen", lambda *_args: available[0])
    save_settings({"avatar_enabled": False}, tmp_path)
    window = avatar.AvatarOverlay(tmp_path)
    window.timer.stop()
    yield window, available
    window.close()
    app.processEvents()


@pytest.mark.parametrize("corner", ["top-left", "top-right", "bottom-left", "bottom-right"])
def test_largest_avatar_fits_small_negative_origin_workarea_without_changing_saved_scale(overlay, corner):
    window, available = overlay
    save_settings({"avatar_scale": 160, "avatar_corner": corner, "avatar_show_emotion_bars": True,
                   "avatar_display": "small"}, window.home)
    window.refresh()
    assert available[1].rect.contains(window.geometry())
    assert window.canvas.height() < round(230 * 1.6)
    assert load_raw_config(window.home)["avatar_scale"] == 160
    assert window.move_to_screen("large")
    assert available[0].rect.contains(window.geometry())
    assert window.canvas.height() == round(230 * 1.6)


def test_unrelated_saved_preferences_do_not_snap_manual_placement(overlay):
    window, available = overlay
    assert window.move_to_screen("large")
    window.move(440, 250)
    position = window.pos()
    save_settings({"theme": "ocean", "whisper_language": "hi"}, window.home)
    window.refresh()
    assert window.pos() == position
    assert available[0].rect.contains(window.geometry())


def test_read_only_placement_report_does_not_activate_capture_or_expose_other_config(overlay, monkeypatch):
    window, available = overlay
    path = window.home / "config.json"
    raw = json.loads(path.read_text())
    raw["avatar_display"] = "not-connected"
    raw["SYNTHETIC_PRIVATE_SETTING"] = "MUST_NOT_APPEAR"
    path.write_text(json.dumps(raw))
    before = path.read_bytes()
    report = avatar.placement_report(window.home)
    assert report["configured_visible"] is False
    assert report["configured_display_connected"] is False
    assert report["screens"][1] == {"name": available[1].name(), "available": [-640, -200, 300, 340]}
    assert "SYNTHETIC_PRIVATE" not in json.dumps(report) and "MUST_NOT_APPEAR" not in json.dumps(report)
    assert path.read_bytes() == before and not window.isVisible()


def test_status_cli_does_not_create_runtime_or_start_resident(app, tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"avatar_enabled": False, "avatar_display": "missing-display"}))
    environment = os.environ.copy()
    environment.update({"AI_OS_HOME": str(tmp_path), "QT_QPA_PLATFORM": "offscreen"})
    environment.pop("DISPLAY", None)
    environment.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run([sys.executable, "-m", "ai_os.avatar_overlay", "--status"],
                            env=environment, capture_output=True, text=True, timeout=10, check=True)
    report = json.loads(result.stdout)
    assert report["configured_visible"] is False and report["configured_display_connected"] is False
    assert report["platform"] == "offscreen"
    assert "does not prove" in report["message"]
    assert list(tmp_path.iterdir()) == [config]


@pytest.mark.parametrize("result", [(False, 0), "exception"])
def test_overlay_settings_launch_uses_same_runtime_and_reports_failure(overlay, monkeypatch, result):
    window, _available = overlay
    calls = []

    class Launcher(QProcess):
        def startDetached(self):
            calls.append((self.program(), self.arguments(), self.processEnvironment().value("AI_OS_HOME")))
            if result == "exception":
                raise RuntimeError("SYNTHETIC_PRIVATE_LAUNCH_ERROR")
            return result

    monkeypatch.setattr(avatar, "QProcess", Launcher)
    assert not window.open_settings()
    assert calls == [(sys.executable, ["-m", "ai_os.hub_launcher"], str(window.home))]
    assert "could not start" in window.status.text()
    assert "SYNTHETIC_PRIVATE" not in window.status.text()
    window.refresh()
    assert "Settings failed" in window.status.text() and not window.status.isHidden()


def test_quick_chat_settings_launch_exception_is_visible_and_sanitized(app, tmp_path, monkeypatch):
    class Launcher(QProcess):
        def startDetached(self):
            assert self.processEnvironment().value("AI_OS_HOME") == str(tmp_path)
            raise RuntimeError("SYNTHETIC_PRIVATE_LAUNCH_ERROR")

    monkeypatch.setattr(quick_chat, "QProcess", Launcher)
    window = quick_chat.QuickChatWindow(tmp_path)
    window.open_settings()
    assert "could not start" in window.conversation.status.text()
    assert "SYNTHETIC_PRIVATE" not in window.conversation.status.text()
    window.close()


@pytest.mark.parametrize("owner", ["avatar", "chat"])
@pytest.mark.parametrize("pid,group", [(0, 0), (1, 1), (991001, 991002)])
def test_cancel_never_signals_zero_or_unowned_group(app, tmp_path, monkeypatch, owner, pid, group):
    signalled = []
    terminated = []

    class Worker(QProcess):
        def state(self):
            return QProcess.ProcessState.Starting if pid == 0 else QProcess.ProcessState.Running

        def processId(self):
            return pid

        def terminate(self):
            terminated.append(True)

        def waitForFinished(self, _timeout):
            return True

    module = avatar if owner == "avatar" else chat
    monkeypatch.setattr(module.os, "getpgid", lambda _pid: group)
    monkeypatch.setattr(module.os, "killpg", lambda pgid, sig: signalled.append((pgid, sig)))
    if owner == "avatar":
        save_settings({"avatar_enabled": False}, tmp_path)
        window = avatar.AvatarOverlay(tmp_path)
        window.speaker = Worker(window)
        window.stop_speech()
    else:
        window = chat.ConversationWidget(tmp_path)
        window.process = Worker(window)
        assert window.cancel()
        window.grant_timer.stop()
    assert not signalled and terminated == [True]
    window.close()


def _alive(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
    except FileNotFoundError:
        return False


@pytest.mark.skipif(sys.platform != "linux", reason="Linux session-owned group cancellation")
@pytest.mark.parametrize("owner", ["avatar", "chat"])
def test_cancel_kills_term_ignoring_descendant_after_leader_exits(app, tmp_path, owner):
    if owner == "avatar":
        save_settings({"avatar_enabled": False}, tmp_path)
        window = avatar.AvatarOverlay(tmp_path)
        window.timer.stop()
        process, cancel = window.speaker, window.stop_speech
    else:
        window = chat.ConversationWidget(tmp_path)
        process, cancel = window.process, window.cancel
    marker, ready = tmp_path / "owned-child.json", tmp_path / "child-ready"
    child_code = ("import pathlib,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                  f"pathlib.Path({str(ready)!r}).write_text('ready');time.sleep(30)")
    root_code = ("import json,os,pathlib,subprocess,sys,time;"
                 f"child=subprocess.Popen([sys.executable,'-c',{child_code!r}]);"
                 f"pathlib.Path({str(marker)!r}).write_text(json.dumps([os.getpid(),child.pid]));time.sleep(30)")
    owned_group = None
    try:
        process.start(sys.executable, ["-c", root_code])
        assert process.waitForStarted(1500)
        pid = process.processId()
        assert pid > 1 and os.getpgid(pid) == pid != os.getpgrp()
        owned_group = pid
        deadline = time.monotonic() + 3
        while (not marker.exists() or not ready.exists()) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        root_pid, child_pid = json.loads(marker.read_text())
        assert ready.exists() and root_pid == owned_group and os.getpgid(child_pid) == owned_group
        cancel()
        deadline = time.monotonic() + 2
        while _alive(child_pid) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert process.state() == QProcess.ProcessState.NotRunning
        assert not _alive(child_pid)
    finally:
        if owned_group is not None and owned_group != os.getpgrp():
            try:
                os.killpg(owned_group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(1500)
        if owner == "chat":
            window.grant_timer.stop()
        window.close()
