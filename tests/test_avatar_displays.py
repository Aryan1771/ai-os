from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QRect, QEvent, Qt
from PySide6.QtWidgets import QApplication

from ai_os.avatar_overlay import AvatarOverlay
from ai_os.config import load_raw_config
from ai_os.settings_store import save_settings


class Screen:
    def __init__(self, name, rect):
        self._name, self.rect = name, rect
        self.availableGeometryChanged = SimpleNamespace(connect=lambda callback: None)
        self.geometryChanged = SimpleNamespace(connect=lambda callback: None)
    def name(self):
        return self._name
    def availableGeometry(self):
        return self.rect


@pytest.fixture
def overlay(tmp_path):
    app = QApplication.instance() or QApplication(['display-test'])
    save_settings({'avatar_enabled': False}, tmp_path)
    widget = AvatarOverlay(tmp_path)
    widget.timer.stop()
    yield widget
    widget.close()
    app.processEvents()


def screens(monkeypatch):
    available = [Screen('internal', QRect(0, 0, 1920, 1080)),
                 Screen('external', QRect(-2560, -360, 2560, 1440))]
    monkeypatch.setattr(QApplication, 'screens', lambda: available)
    monkeypatch.setattr(QApplication, 'primaryScreen', lambda: available[0])
    monkeypatch.setattr(QApplication, 'screenAt', lambda point: next(
        (s for s in available if s.rect.contains(point)), None))
    return available


def test_drag_crosses_old_screen_boundary_and_persists_target(overlay, monkeypatch):
    available = screens(monkeypatch)
    def event(kind, point):
        return SimpleNamespace(type=lambda: kind, button=lambda: Qt.MouseButton.LeftButton,
                               globalPosition=lambda: SimpleNamespace(toPoint=lambda: point))
    start = overlay.pos() + QPoint(20, 20)
    overlay.eventFilter(overlay.canvas, event(QEvent.Type.MouseButtonPress, start))
    overlay.eventFilter(overlay.canvas, event(QEvent.Type.MouseMove, QPoint(-1600, 200)))
    assert overlay.x() < 0 and available[1].rect.contains(overlay.geometry())
    overlay.eventFilter(overlay.canvas, event(QEvent.Type.MouseButtonRelease, QPoint(-1600, 200)))
    assert load_raw_config(overlay.home)['avatar_display'] == 'external'
    position = overlay.pos()
    overlay.refresh()
    assert overlay.pos() == position  # Own config save must not snap the drag back.


def test_menu_selection_places_on_target_and_missing_monitor_falls_back(overlay, monkeypatch):
    available = screens(monkeypatch)
    assert overlay.move_to_screen('external')
    assert available[1].rect.contains(overlay.geometry())
    assert not overlay.move_to_screen('not-connected')
    available.pop()
    overlay.place()
    assert available[0].rect.contains(overlay.geometry())
    assert load_raw_config(overlay.home)['avatar_display'] == 'external'
    available.append(Screen('external', QRect(-2560, -360, 2560, 1440)))
    overlay.screen_added(available[1])
    assert available[1].rect.contains(overlay.geometry())
