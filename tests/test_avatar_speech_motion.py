"""Persistent particle mouth cadence and bounded persona preferences."""
import os
from copy import deepcopy

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication

from ai_os.companion_persona import mood_guidance
from ai_os.config import DEFAULT_CONFIG
from ai_os.native_widgets import CompanionCanvas
from ai_os.pixel_engine import PixelEngine, speech_mouth_frame


def test_mouth_cadence_is_bounded_and_changes_material_without_new_particles():
    assert {speech_mouth_frame(n * .12) for n in range(12)} == {0, 1, 2}
    assert speech_mouth_frame(float("nan")) == speech_mouth_frame(-1) == 0
    engine = PixelEngine()
    engine.set_form("core", {}, mouth_open=0)
    identities = [id(pixel) for pixel in engine.pixels]
    closed = [pixel.material for pixel in engine.pixels]
    engine.set_form("core", {}, mouth_open=2)
    assert identities == [id(pixel) for pixel in engine.pixels]
    assert closed != [pixel.material for pixel in engine.pixels]


def test_speaking_restores_task_shape_and_respects_disabled_motion():
    app = QApplication.instance() or QApplication(["mouth-motion-test"])
    canvas = CompanionCanvas()
    config = deepcopy(DEFAULT_CONFIG)
    state = {"phase": "speaking", "shape": "gear", "emotions": {}, "pixels": None}
    canvas.set_state(state, config)
    canvas.speech_elapsed = .24
    canvas.update_form()
    assert canvas.mouth_frame == 2
    config["avatar_animation_enabled"] = False
    canvas.set_state(state, config)
    assert canvas.mouth_frame == 0
    canvas.set_state(state | {"phase": "working"}, config)
    assert canvas.mouth_frame is None
    canvas.timer.stop()
    canvas.close()
    app.processEvents()


def test_mood_changes_style_without_permissions_facts_or_claiming_consciousness():
    config = deepcopy(DEFAULT_CONFIG)
    config["avatar_reactivity"] = 0
    config["avatar_emotions"] = {key: 0 for key in config["avatar_emotions"]}
    config["avatar_emotions"]["joy"] = 100
    joyful = mood_guidance(config, {"phase": "idle", "emotions": {}})
    config["avatar_emotions"]["joy"] = 0
    config["avatar_emotions"]["focus"] = 100
    focused = mood_guidance(config, {"phase": "idle", "emotions": {}})
    assert "appreciation and enthusiasm" in joyful and "organize the answer" in focused
    assert "never facts, tool selection, permission" in focused
    assert "simulated mood" in focused
