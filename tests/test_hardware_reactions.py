"""Synthetic hotplug and speech ownership; no actual devices or audio."""

import json
import sys
import threading
import wave
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from ai_os import hardware_reactions as hardware
from ai_os.companion_state import publish_state, read_state
from ai_os.device_context import DisplayTracker
from ai_os.speech_lease import speech_lease


@pytest.fixture
def rig(tmp_path, monkeypatch):
    settings = {"hardware_notifications_enabled": True, "hardware_speech_enabled": True,
                "speech_enabled": True, "speech_emotion_enabled": True, "whisper_language": "en"}
    spoken, stopped = [], []
    hooks = SimpleNamespace(speak=None)

    class Speaker:
        def __init__(self, *args, **kwargs):
            pass

        def speak_text(self, text):
            spoken.append(text)
            if hooks.speak:
                hooks.speak(text)

        def stop(self):
            stopped.append(True)

    monkeypatch.setattr(hardware, "SpeechQueue", Speaker)
    monkeypatch.setattr(hardware, "load_raw_config", lambda home: settings.copy())
    monkeypatch.setattr(hardware, "load_config", lambda home: SimpleNamespace(
        piper_model=tmp_path / "synthetic-model.onnx", piper_hindi_model=None, piper_length_scale=1.0,
    ))
    return SimpleNamespace(home=tmp_path, settings=settings, spoken=spoken, stopped=stopped, hooks=hooks)


def test_busy_reactions_wait_then_speak_and_restore_armed_phase(rig):
    reactions = hardware.HardwareReactions(rig.home)
    reactions.enqueue("Oh, a USB device is connected.", rig.settings)
    publish_state("listening", home=rig.home)
    reactions.dispatch(rig.settings)
    assert not rig.spoken and len(reactions.pending) == 1
    publish_state("armed", home=rig.home)
    reactions.dispatch(rig.settings)
    assert rig.spoken == ["Oh, a USB device is connected."]
    assert len(reactions.pending) == 0 and rig.stopped == [True]
    assert read_state(rig.home)["phase"] == "armed"
    assert json.loads((rig.home / "run/hardware-event.json").read_text())["pending_count"] == 0


def test_language_change_discards_queued_text_in_previous_language(rig):
    reactions = hardware.HardwareReactions(rig.home)
    reactions.enqueue("Synthetic English announcement", rig.settings)
    rig.settings["whisper_language"] = "hi"
    reactions.dispatch(rig.settings)
    assert not rig.spoken and not reactions.pending


def test_busy_queue_is_bounded_deduplicated_and_expires(rig):
    clock = [100.0]
    reactions = hardware.HardwareReactions(rig.home, clock=lambda: clock[0])
    publish_state("thinking", home=rig.home)
    reactions.enqueue("Synthetic event 0", rig.settings)
    reactions.enqueue("Synthetic event 0", rig.settings)
    assert len(reactions.pending) == 1
    for index in range(1, 10):
        clock[0] += 1
        reactions.enqueue(f"Synthetic event {index}", rig.settings)
    assert [item.text for item in reactions.pending] == [f"Synthetic event {i}" for i in range(2, 10)]
    clock[0] += 61
    publish_state("idle", home=rig.home)
    reactions.dispatch(rig.settings)
    assert not reactions.pending and not rig.spoken


@pytest.mark.parametrize("disabled", ["hardware_notifications_enabled", "hardware_speech_enabled", "speech_enabled"])
def test_revocation_discards_pending_reactions(rig, disabled):
    reactions = hardware.HardwareReactions(rig.home)
    reactions.enqueue("Synthetic event", rig.settings)
    rig.settings[disabled] = False
    reactions.dispatch(rig.settings)
    assert not reactions.pending and not rig.spoken


def test_saved_revocation_is_rechecked_after_lease_acquisition(rig):
    reactions = hardware.HardwareReactions(rig.home)
    reactions.enqueue("Synthetic event", rig.settings)
    old_snapshot = rig.settings.copy()
    rig.settings["hardware_speech_enabled"] = False
    reactions.dispatch(old_snapshot)
    assert not reactions.pending and not rig.spoken


def test_foreground_speech_lease_keeps_hardware_reaction_queued(rig):
    reactions = hardware.HardwareReactions(rig.home)
    reactions.enqueue("Synthetic event", rig.settings)
    with speech_lease(rig.home) as acquired:
        assert acquired
        reactions.dispatch(rig.settings)
        assert not rig.spoken and len(reactions.pending) == 1
    reactions.dispatch(rig.settings)
    assert rig.spoken == ["Synthetic event"]


def test_phase_change_during_lease_acquisition_prevents_hardware_speech(rig, monkeypatch):
    @contextmanager
    def raced_lease(home):
        publish_state("listening", home=home)
        yield True

    monkeypatch.setattr(hardware, "speech_lease", raced_lease)
    reactions = hardware.HardwareReactions(rig.home)
    reactions.enqueue("Synthetic event", rig.settings)
    reactions.dispatch(rig.settings)
    assert not rig.spoken and len(reactions.pending) == 1
    assert read_state(rig.home)["phase"] == "listening"


@pytest.mark.parametrize("new_phase", ["listening", "speaking"])
def test_hardware_speech_cleanup_preserves_newer_activity(rig, new_phase):
    newer = []
    rig.hooks.speak = lambda text: newer.append(publish_state(new_phase, "music", home=rig.home))
    reactions = hardware.HardwareReactions(rig.home)
    reactions.enqueue("Synthetic event", rig.settings)
    reactions.dispatch(rig.settings)
    saved = json.loads((rig.home / "run/avatar_state.json").read_text())
    assert saved == newer[0]
    assert rig.stopped == [True]


def test_corrupt_speech_output_reports_sanitized_error_and_releases_lease(rig):
    def fail(text):
        raise wave.Error("private synthetic backend diagnostic")

    rig.hooks.speak = fail
    reactions = hardware.HardwareReactions(rig.home)
    reactions.enqueue("Synthetic event", rig.settings)
    reactions.dispatch(rig.settings)
    saved = (rig.home / "run/hardware-event.json").read_text()
    assert "Hardware speech failed" in saved and "private synthetic" not in saved
    assert rig.stopped == [True] and read_state(rig.home)["phase"] == "idle"
    with speech_lease(rig.home) as acquired:
        assert acquired


def test_concurrent_hardware_dispatchers_never_play_over_each_other(rig):
    entered, release = threading.Event(), threading.Event()

    def hold_speech(text):
        entered.set()
        assert release.wait(5)

    rig.hooks.speak = hold_speech
    reactions = hardware.HardwareReactions(rig.home)
    reactions.enqueue("First synthetic event", rig.settings)
    reactions.enqueue("Second synthetic event", rig.settings)
    worker = threading.Thread(target=reactions.dispatch, args=(rig.settings,), daemon=True)
    worker.start()
    try:
        assert entered.wait(2)
        reactions.dispatch(rig.settings)
        assert rig.spoken == ["First synthetic event"]
        assert len(reactions.pending) == 1
    finally:
        release.set()
        worker.join(timeout=2)
    assert not worker.is_alive()


def test_device_reactions_use_fixed_localized_categories_only():
    assert "USB device" in hardware.device_reaction("add", "usb", "usb_device")
    assert "यूएसबी" in hardware.device_reaction("add", "usb", "usb_device", "hi")
    assert hardware.device_reaction("add", "usb", "untrusted device instruction") is None
    assert hardware.device_reaction("run arbitrary text", "usb", "usb_device") is None
    assert hardware.device_reaction("add", "drm", "") is None


def connector(root, name, modes):
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "status").write_text("connected")
    (directory / "edid").write_bytes(b"")
    (directory / "modes").write_text(modes)
    return directory


def test_late_monitor_capabilities_are_announced_and_reconnect_is_familiar(tmp_path):
    root = tmp_path / "drm"
    connector(root, "card0-eDP-1", "1920x1080\n")
    tracker = DisplayTracker(tmp_path, root)
    external = connector(root, "card0-HDMI-A-1", "")
    assert "new monitor" in tracker.poll()[0]
    (external / "modes").write_text("1920x1080\n3840x2160\n")
    notice = tracker.poll()[0]
    assert "details are ready" in notice and "supports 3840 by 2160" in notice and "4K" in notice
    assert tracker.poll() == []
    (external / "status").write_text("disconnected")
    assert tracker.poll() == []
    (external / "status").write_text("connected")
    assert "back" in tracker.poll()[0]
    assert "HDMI" not in tracker.path.read_text()


def test_transient_missing_modes_do_not_erase_historical_monitor_capabilities(tmp_path):
    root = tmp_path / "drm"
    external = connector(root, "card0-HDMI-A-1", "3840x2160\n")
    tracker = DisplayTracker(tmp_path, root)
    (external / "modes").write_text("")
    tracker.poll()
    assert any(specs["width"] == 3840 for specs in tracker.known.values())


def fake_monitor(monkeypatch, callback):
    monitor = SimpleNamespace(start=lambda: None, poll=callback)
    module = SimpleNamespace(Context=object, Monitor=SimpleNamespace(from_netlink=lambda context: monitor))
    monkeypatch.setitem(sys.modules, "pyudev", module)


def test_monitor_periodic_poll_recovers_late_capabilities_without_another_event(rig, monkeypatch):
    root = rig.home / "drm"
    connector(root, "card0-eDP-1", "1920x1080\n")
    monkeypatch.setattr(hardware, "DisplayTracker", lambda home: DisplayTracker(home, root))
    stop = threading.Event()
    calls = [0]
    external = []

    def poll(timeout):
        calls[0] += 1
        if calls[0] == 1:
            external.append(connector(root, "card0-HDMI-A-1", ""))
            return SimpleNamespace(action="change", subsystem="drm", device_type="")
        if calls[0] == 2:
            (external[0] / "modes").write_text("3840x2160\n")
        if calls[0] >= 4:
            stop.set()
        return None

    monkeypatch.setattr(hardware, "time", SimpleNamespace(
        monotonic=lambda: calls[0] * 0.5, time=lambda: 1800000000.0,
    ))
    fake_monitor(monkeypatch, poll)
    hardware.watch_devices(rig.home, stop)
    assert len(rig.spoken) == 2
    assert "new monitor" in rig.spoken[0]
    assert "supports 3840 by 2160" in rig.spoken[1] and "4K" in rig.spoken[1]


def test_enable_monitoring_baselines_before_the_next_hotplug(rig, monkeypatch):
    root = rig.home / "drm"
    connector(root, "card0-eDP-1", "1920x1080\n")
    monkeypatch.setattr(hardware, "DisplayTracker", lambda home: DisplayTracker(home, root))
    rig.settings["hardware_notifications_enabled"] = False
    stop, calls = threading.Event(), [0]

    def poll(timeout):
        calls[0] += 1
        if calls[0] == 1:
            rig.settings["hardware_notifications_enabled"] = True
        elif calls[0] == 2:
            connector(root, "card0-HDMI-A-1", "3840x2160\n")
            return SimpleNamespace(action="change", subsystem="drm", device_type="")
        else:
            stop.set()
        return None

    fake_monitor(monkeypatch, poll)
    hardware.watch_devices(rig.home, stop)
    assert len(rig.spoken) == 1 and "new monitor" in rig.spoken[0]


def test_disabled_monitoring_does_not_read_display_state_or_speak(rig, monkeypatch):
    def forbidden(home):
        raise AssertionError("Display facts must not be read while disabled")

    monkeypatch.setattr(hardware, "DisplayTracker", forbidden)
    rig.settings["hardware_notifications_enabled"] = False
    stop, calls = threading.Event(), [0]

    def poll(timeout):
        calls[0] += 1
        if calls[0] > 1:
            stop.set()
        return SimpleNamespace(action="add", subsystem="usb", device_type="usb_device")

    fake_monitor(monkeypatch, poll)
    hardware.watch_devices(rig.home, stop)
    assert not rig.spoken and not (rig.home / "data/private/known-displays.json").exists()
