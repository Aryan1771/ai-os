"""Latest metadata uses disposable roots and never records, speaks or reads logs."""
from __future__ import annotations

import json
import os
import signal
import stat
import sys

import pytest

from ai_os import voice_check_status as status
from ai_os import voice_diagnostics
from ai_os.services.voice_errors import VoicePipelineError


def file_path(home):
    return home / "run/private" / status.FILENAME


def test_latest_status_omits_text_private_fields_and_writes_private_atomic_snapshot(tmp_path):
    publisher = status.VoiceCheckStatus(tmp_path, "record")
    assert publisher.started_at is not None
    assert publisher.progress({"event": "voice_progress", "phase": "capturing", "silence_seconds": 1})
    assert publisher.publish("failed", code="PRIVATE", timings={
        "stt_seconds": .12345, "private": "PRIVATE", "model_seconds": float("nan")})
    result = status.read_status(tmp_path)
    assert result["status"] == "fresh" and result["action"] == "record"
    assert result["phase"] == "failed" and result["code"] == "capture_failed"
    assert result["timings"] == {"stt_seconds": .123}
    assert set(result) == status.FIELDS | {"status"} and "PRIVATE" not in json.dumps(result)
    assert stat.S_IMODE(file_path(tmp_path).stat().st_mode) == 0o600
    assert stat.S_IMODE(file_path(tmp_path).parent.stat().st_mode) == 0o700
    assert not list(file_path(tmp_path).parent.glob("*.tmp"))
    assert {item.name for item in file_path(tmp_path).parent.iterdir()} == {status.FILENAME, status.LOCKNAME}


def test_existing_runtime_permissions_are_preserved_and_only_private_child_is_added(tmp_path):
    tmp_path.chmod(0o755)
    (tmp_path / "run").mkdir(mode=0o755)
    publisher = status.VoiceCheckStatus(tmp_path, "play")
    assert publisher.started_at is not None
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o755
    assert stat.S_IMODE((tmp_path / "run").stat().st_mode) == 0o755
    assert status.read_status(tmp_path)["action"] == "play"


def test_superseded_worker_cannot_overwrite_new_check_even_if_wall_clock_equal(tmp_path, monkeypatch):
    monkeypatch.setattr(status.time, "time", lambda: 1000.0)
    first = status.VoiceCheckStatus(tmp_path, "record")
    second = status.VoiceCheckStatus(tmp_path, "play")
    assert second.started_at > first.started_at
    assert not first.publish("completed")
    assert second.publish("speaking")
    result = status.read_status(tmp_path, now=1000.0)
    assert result["phase"] == "speaking" and result["action"] == "play"


def test_reader_rejects_stale_future_or_invalid_time_without_returning_old_fields(tmp_path):
    status.VoiceCheckStatus(tmp_path, "record")
    updated = status.read_status(tmp_path)["updated_at"]
    assert status.read_status(tmp_path, now=updated + 181) == {"status": "stale"}
    assert status.read_status(tmp_path, now=updated - 2) == {"status": "unavailable"}
    assert status.read_status(tmp_path, now=float("nan")) == {"status": "unavailable"}
    assert status.read_status(tmp_path, max_age=500) == {"status": "unavailable"}


def test_reader_never_creates_missing_runtime_storage(tmp_path):
    assert status.read_status(tmp_path / "missing") == {"status": "unavailable"}
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("bad", ["malformed", "oversized", "unknown_fields", "bad_phase", "bad_timings"])
def test_reader_and_publisher_refuse_invalid_existing_file_without_exposing_or_replacing_it(tmp_path, bad):
    status.VoiceCheckStatus(tmp_path, "play")
    path = file_path(tmp_path)
    value = json.loads(path.read_bytes())
    if bad == "malformed":
        payload = b"PRIVATE INVALID JSON"
    elif bad == "oversized":
        payload = b"PRIVATE" * 1000
    else:
        if bad == "unknown_fields":
            value["transcript"] = "PRIVATE"
        elif bad == "bad_phase":
            value["phase"] = []
        else:
            value["timings"] = {"private": "PRIVATE"}
        payload = json.dumps(value).encode()
    path.write_bytes(payload)
    assert status.read_status(tmp_path) == {"status": "unavailable"}
    assert status.VoiceCheckStatus(tmp_path, "record").started_at is None
    assert path.read_bytes() == payload


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink", "directory", "fifo", "public"])
def test_metadata_file_must_be_owned_private_regular_single_link(tmp_path, unsafe):
    status.VoiceCheckStatus(tmp_path, "play")
    path = file_path(tmp_path)
    outside = tmp_path / "untouched"
    outside.write_bytes(b"PRIVATE outside data")
    if unsafe == "symlink":
        path.unlink()
        path.symlink_to(outside)
    elif unsafe == "hardlink":
        path.unlink()
        os.link(outside, path)
    elif unsafe == "directory":
        path.unlink()
        path.mkdir()
    elif unsafe == "fifo":
        path.unlink()
        os.mkfifo(path)
    else:
        path.chmod(0o644)
    assert status.read_status(tmp_path) == {"status": "unavailable"}
    assert status.VoiceCheckStatus(tmp_path, "record").started_at is None
    assert outside.read_bytes() == b"PRIVATE outside data"


@pytest.mark.parametrize("unsafe", ["runtime_symlink", "run_symlink", "private_symlink", "private_public", "run_writable", "foreign_owner"])
def test_directory_safety_refuses_symlinks_or_unsafe_permissions_without_chmod(tmp_path, monkeypatch, unsafe):
    home = tmp_path / "runtime"
    home.mkdir()
    (home / "run").mkdir()
    (home / "run/private").mkdir(mode=0o700)
    outside = tmp_path / "outside"
    outside.mkdir()
    if unsafe.endswith("symlink"):
        target = {"runtime_symlink": home, "run_symlink": home / "run",
                  "private_symlink": home / "run/private"}[unsafe]
        target.rename(tmp_path / "preserved")
        target.symlink_to(outside, target_is_directory=True)
    elif unsafe == "private_public":
        (home / "run/private").chmod(0o755)
    elif unsafe == "run_writable":
        (home / "run").chmod(0o777)
    else:
        original = os.getuid()
        monkeypatch.setattr(status.os, "getuid", lambda: original + 1)
    assert status.VoiceCheckStatus(home, "record").started_at is None
    assert status.read_status(home) == {"status": "unavailable"}
    assert not list(outside.iterdir())
    if unsafe == "private_public":
        assert stat.S_IMODE((home / "run/private").stat().st_mode) == 0o755


def test_existing_symlink_lock_blocks_writes_without_following_target(tmp_path):
    first = status.VoiceCheckStatus(tmp_path, "play")
    before = file_path(tmp_path).read_bytes()
    outside = tmp_path / "outside"
    outside.write_bytes(b"PRIVATE untouched")
    lock = file_path(tmp_path).with_name(status.LOCKNAME)
    lock.unlink()
    lock.symlink_to(outside)
    assert not first.publish("speaking")
    assert file_path(tmp_path).read_bytes() == before and outside.read_bytes() == b"PRIVATE untouched"


def test_reader_handles_storage_errors_without_printing_private_exception(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(status.os, "open", lambda *_a, **_k: (_ for _ in ()).throw(OSError("PRIVATE path")))
    assert status.read_status(tmp_path) == {"status": "unavailable"}
    assert status.VoiceCheckStatus(tmp_path, "play").started_at is None
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("progress", [False, True])
@pytest.mark.parametrize("outcome", ["success", "failure", "cancelled"])
def test_confirmed_worker_publishes_metadata_for_old_and_new_ui_without_changing_stdout(
    tmp_path, monkeypatch, capsys, progress, outcome,
):
    monkeypatch.setenv("AI_OS_HOME", str(tmp_path))
    monkeypatch.setattr(voice_diagnostics.signal, "signal", lambda *_args: None)

    def check(*_args, on_progress=None, **_kwargs):
        on_progress({"event": "voice_progress", "phase": "transcribing"})
        assert status.read_status(tmp_path)["phase"] == "transcribing"
        if outcome == "cancelled":
            raise SystemExit(130)
        if outcome == "failure":
            raise VoicePipelineError("utterance_too_long", "PRIVATE")
        return {"ok": True, "message": "Done", "transcript": "PRIVATE", "reply": "PRIVATE",
                "timings": {"stt_seconds": 1.2, "private": "PRIVATE"}}

    monkeypatch.setattr(voice_diagnostics, "check_voice", check)
    argv = ["voice_diagnostics", "--worker", "record", "--confirmed"]
    monkeypatch.setattr(sys, "argv", argv + (["--progress"] if progress else []))
    if outcome == "cancelled":
        with pytest.raises(SystemExit):
            voice_diagnostics.main()
    else:
        assert voice_diagnostics.main() == (0 if outcome == "success" else 1)
    result = status.read_status(tmp_path)
    assert result["phase"] == {"success": "completed", "failure": "failed", "cancelled": "cancelled"}[outcome]
    assert "PRIVATE" not in json.dumps(result) and result["action"] == "record"
    output = capsys.readouterr().out.splitlines()
    assert len(output) == (int(progress) + int(outcome != "cancelled"))


def test_unconfirmed_worker_never_creates_status(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AI_OS_HOME", str(tmp_path))
    monkeypatch.setattr(voice_diagnostics.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(voice_diagnostics, "check_voice", lambda *_a, **_k: (_ for _ in ()).throw(PermissionError()))
    monkeypatch.setattr(sys, "argv", ["voice_diagnostics", "--worker", "play"])
    assert voice_diagnostics.main() == 1
    assert not (tmp_path / "run").exists()
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_reader_prints_only_sanitized_snapshot_without_recording(tmp_path, monkeypatch, capsys):
    status.VoiceCheckStatus(tmp_path, "play")
    expected = status.read_status(tmp_path)
    monkeypatch.setattr(status, "read_status", lambda: expected)
    monkeypatch.setattr(signal, "signal", lambda *_args: pytest.fail("No worker activation"))
    assert status.main() == 0
    assert json.loads(capsys.readouterr().out) == expected
