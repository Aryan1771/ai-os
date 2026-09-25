import json
import math
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from ai_os import ai_os_core as core
from ai_os.companion_state import emotion_levels, publish_state, read_state, validate_pixels
from ai_os.config import DEFAULT_CONFIG, atomic_json
from ai_os.pixel_engine import FORMS, PixelEngine, target_pixels
from ai_os.security.consent_broker import ConsentDecision
from ai_os.settings_store import save_settings


@pytest.mark.parametrize(
    "pixels",
    [
        [],
        ["." * 25] * 4,
        ["####"] * 25,
        ["####", "###", "####", "####"],
        ["eval"] * 4,
        ["...."] * 4,
    ],
)
def test_model_pixels_reject_invalid_or_executable_content(pixels):
    assert validate_pixels(pixels) is None


def test_custom_form_and_emotions_reach_state_without_executable_fields(tmp_path):
    pixels = [".##.", "####", "#oo#", ".**."]
    publish_state(
        "reply",
        home=tmp_path,
        avatar={"pixels": pixels, "emotions": {"joy": 150, "calm": -4}, "command": "rm -rf /"},
    )
    state = read_state(tmp_path)
    assert state["pixels"] == pixels
    assert state["emotions"] == {"joy": 100, "calm": 0}
    assert "command" not in state


def test_stale_or_partial_state_falls_back_to_idle(tmp_path):
    state = publish_state("thinking", "code", home=tmp_path)
    assert read_state(tmp_path, now=state["updated_at"] + 200)["phase"] == "idle"
    (tmp_path / "run" / "avatar_state.json").write_text('{"partial":', encoding="utf-8")
    assert read_state(tmp_path)["phase"] == "idle"


def test_concurrent_snapshot_writers_leave_complete_json(tmp_path):
    path = tmp_path / "state.json"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda value: atomic_json(path, {"value": value}), range(30)))
    assert isinstance(json.loads(path.read_text())["value"], int)
    assert not list(tmp_path.glob("*.tmp"))


def test_emotional_reactivity_respects_zero_and_full_baseline():
    config = deepcopy(DEFAULT_CONFIG)
    state = {"phase": "working", "emotions": {}}
    config["avatar_reactivity"] = 0
    assert emotion_levels(state, config) == config["avatar_emotions"]
    config["avatar_reactivity"] = 100
    assert emotion_levels(state, config)["focus"] == 95


def test_pixels_travel_and_settle_without_replacing_particle_objects():
    engine = PixelEngine()
    engine.set_form("core", {})
    engine.advance(0.02, animate=False)
    ids = {id(pixel) for pixel in engine.pixels}
    start = [(pixel.x, pixel.y) for pixel in engine.pixels]
    engine.set_form("heart", {})
    assert ids == {id(pixel) for pixel in engine.pixels}
    engine.advance(0.02, motion=0)
    assert start != [(pixel.x, pixel.y) for pixel in engine.pixels]
    for _ in range(160):
        engine.advance(0.02, motion=0)
    assert all(math.isfinite(pixel.x) and abs(pixel.x - pixel.tx) < 0.02 for pixel in engine.pixels)
    assert any(not pixel.active and pixel.opacity < 0.01 for pixel in engine.pixels)


def test_all_forms_fit_the_rendering_lattice_and_expressions_change():
    for form in FORMS:
        pixels = target_pixels(form, {})
        assert 0 < len(pixels) <= 24 * 24
        assert max(abs(x) for x, _, _ in pixels) <= 12
    assert target_pixels("core", {"joy": 80}) != target_pixels("core", {"concern": 80})


def test_model_reply_metadata_does_not_get_spoken():
    reply, metadata = core.parse_visual_reply('{"reply":"Hello","avatar":{"shape":"heart"}}')
    assert reply == "Hello"
    assert metadata["shape"] == "heart"
    assert core.parse_visual_reply("Plain legacy reply") == ("Plain legacy reply", {})


def test_tool_activity_and_failure_are_published(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "ask_ollama", lambda *_args: '{"tool":"job","arguments":{}}')
    phases = []
    original = core.publish_state

    def capture(phase, *args, **kwargs):
        phases.append(phase)
        return original(phase, *args, **kwargs)

    monkeypatch.setattr(core, "publish_state", capture)
    response = core.handle_user_text("work", {"job": lambda: {"ok": False}}, home=tmp_path)
    assert phases == ["thinking", "working", "error"]
    assert "could not" in core.spoken_response(response)


def test_model_cannot_approve_its_own_process_action(monkeypatch):
    monkeypatch.setattr(core, "request_cli_consent", lambda _request: ConsentDecision.DENIED)
    calls = []
    result = core.execute_tool(
        "terminate_process",
        {"pid": 10, "approve": True},
        {"terminate_process": lambda **kwargs: calls.append(kwargs)},
    )
    assert not result["ok"]
    assert calls == []


def test_unlocking_settings_requires_confirmation_and_unchanged_values_do_not(tmp_path):
    with pytest.raises(PermissionError):
        save_settings({"sandbox_lock_settings": False}, tmp_path)
    save_settings({"always_listening_enabled": False, "theme": "light"}, tmp_path)
    assert (
        save_settings({"sandbox_lock_settings": False}, tmp_path, human_confirmed=True)[
            "sandbox_lock_settings"
        ]
        is False
    )


def test_settings_validate_before_writing_and_support_local_compatible_models(tmp_path):
    saved = save_settings(
        {
            "ai_provider": "openai_compatible",
            "ollama_url": "http://127.0.0.1:8080/v1/chat/completions",
        },
        tmp_path,
        human_confirmed=True,
    )
    assert saved["allow_external_apis"] is False
    before = (tmp_path / "config.json").read_bytes()
    with pytest.raises(ValueError):
        save_settings({"avatar_accent": "invalid", "theme": "light"}, tmp_path)
    assert (tmp_path / "config.json").read_bytes() == before


def test_speech_activity_keeps_model_form_and_clears_on_finish(monkeypatch):
    from ai_os.speech_queue import SpeechQueue

    events = []
    speech = SpeechQueue(on_activity=lambda *event: events.append(event))
    spoken = []

    def speak(text):
        assert speech.is_speaking()
        spoken.append(text)
        speech.stop()

    monkeypatch.setattr(speech, "speak_text", speak)
    speech.enqueue("Hello.", avatar={"shape": "heart"})
    speech.run_forever()
    assert spoken == ["Hello."]
    assert events == [("speaking", "Hello.", {"shape": "heart"}), ("idle", "", None)]
    assert not speech.is_speaking()
