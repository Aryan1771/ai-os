"""Synthetic speaker vectors only: these are not real voice-accuracy measurements."""
import json
import math
import os
import stat
import wave

import pytest

from ai_os import speaker_identity as speaker


def vector(index=0):
    result = [0.0] * 32
    result[index] = 1.0
    return result


def write_config(home, **values):
    (home / "config.json").write_text(json.dumps(values), encoding="utf-8")


def enrollment(model, encoder=None):
    result = speaker.Enrollment(speaker.model_digest(model), encoder=encoder)
    for _ in range(4):
        result.add(vector())
    return result


@pytest.fixture
def model(tmp_path):
    path = tmp_path / "speaker.onnx"
    path.write_bytes(b"fake model; tests inject embeddings")
    return path


def test_requires_separate_held_out_verification_and_private_atomic_profile(tmp_path, model):
    session = enrollment(model)
    with pytest.raises(speaker.SpeakerError, match="separate"):
        session.save(tmp_path)
    assert session.verify(vector())
    session.save(tmp_path)
    path = speaker.profile_path(tmp_path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    data = speaker.load_profile(tmp_path)
    assert set(data) == {"version", "model_sha256", "samples", "embedding"}
    assert data["embedding"] == vector()
    assert list(path.parent.iterdir()) == [path]


def test_mismatching_samples_not_added_or_verified(tmp_path, model):
    session = speaker.Enrollment(speaker.model_digest(model))
    session.add(vector())
    with pytest.raises(speaker.SpeakerError, match="differs"):
        session.add(vector(1))
    assert len(session.samples) == 1
    for _ in range(3):
        session.add(vector())
    assert not session.verify(vector(1))
    with pytest.raises(speaker.SpeakerError):
        session.save(tmp_path)
    assert not speaker.profile_path(tmp_path).exists()


@pytest.mark.parametrize("values", [[0] * 32, [float("nan")] * 32, [float("inf")] * 32,
                                   [1] * 8, [1] * 2049])
def test_rejects_malformed_embeddings(values):
    with pytest.raises(speaker.SpeakerError):
        speaker.normalized(values)


def test_dimension_mismatch_rejected():
    with pytest.raises(speaker.SpeakerError, match="dimensions"):
        speaker.similarity(vector(), [1] * 64)


def test_disabled_filter_does_not_load_backend_or_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(speaker, "encoder_for", lambda _: pytest.fail("must not load"))
    assert speaker.speaker_allowed(tmp_path / "absent.wav", tmp_path)[0]


def test_enabled_missing_configuration_fails_closed(tmp_path):
    write_config(tmp_path, speaker_recognition_enabled=True)
    allowed, reason = speaker.speaker_allowed(tmp_path / "private-recording.wav", tmp_path)
    assert not allowed
    assert str(tmp_path) not in reason


def test_enabled_matches_rejects_and_rejects_changed_model(tmp_path, model, monkeypatch):
    session = enrollment(model)
    session.verify(vector())
    session.save(tmp_path)
    write_config(tmp_path, speaker_recognition_enabled=True, speaker_model=str(model), speaker_threshold=.75)
    monkeypatch.setattr(speaker, "encoder_for", lambda _: lambda audio: vector())
    assert speaker.speaker_allowed(tmp_path / "unused.wav", tmp_path)[0]
    monkeypatch.setattr(speaker, "encoder_for", lambda _: lambda audio: vector(1))
    assert not speaker.speaker_allowed(tmp_path / "unused.wav", tmp_path)[0]
    model.write_bytes(b"different model")
    monkeypatch.setattr(speaker, "encoder_for", lambda _: pytest.fail("changed model must block before backend"))
    assert not speaker.speaker_allowed(tmp_path / "unused.wav", tmp_path)[0]


def test_enabled_backend_exception_fails_closed(tmp_path, model, monkeypatch):
    session = enrollment(model)
    session.verify(vector())
    session.save(tmp_path)
    write_config(tmp_path, speaker_recognition_enabled=True, speaker_model=str(model))
    monkeypatch.setattr(speaker, "encoder_for", lambda _: (_ for _ in ()).throw(RuntimeError("private details")))
    allowed, reason = speaker.speaker_allowed(tmp_path / "private.wav", tmp_path)
    assert not allowed
    assert "private details" not in reason


def test_no_silent_threshold_bypass(tmp_path, model, monkeypatch):
    session = enrollment(model)
    session.verify(vector())
    session.save(tmp_path)
    monkeypatch.setattr(speaker, "encoder_for", lambda _: pytest.fail("invalid threshold"))
    for threshold in (-1, 1.1, float("nan"), "no"):
        write_config(tmp_path, speaker_recognition_enabled=True, speaker_model=str(model), speaker_threshold=threshold)
        assert not speaker.speaker_allowed(tmp_path / "unused.wav", tmp_path)[0]


def test_rejects_profile_symlink_public_permissions_and_malformed_file(tmp_path, model):
    session = enrollment(model)
    session.verify(vector())
    session.save(tmp_path)
    path = speaker.profile_path(tmp_path)
    os.chmod(path, 0o644)
    with pytest.raises(speaker.SpeakerError):
        speaker.load_profile(tmp_path)
    path.unlink()
    outside = tmp_path / "private-target"
    outside.write_text("not valid", encoding="utf-8")
    path.symlink_to(outside)
    with pytest.raises(speaker.SpeakerError):
        speaker.load_profile(tmp_path)
    speaker.delete_profile(tmp_path)
    assert outside.exists()
    path.write_text("{}", encoding="utf-8")
    os.chmod(path, 0o600)
    with pytest.raises(speaker.SpeakerError):
        speaker.load_profile(tmp_path)


def test_rejects_storage_symlink_without_writing_outside(tmp_path, model):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (tmp_path / "data").symlink_to(outside, target_is_directory=True)
    session = enrollment(model)
    session.verify(vector())
    with pytest.raises(speaker.SpeakerError):
        session.save(tmp_path)
    assert not list(outside.iterdir())


def test_no_profile_load_creates_directories(tmp_path):
    before = list(tmp_path.iterdir())
    with pytest.raises(speaker.SpeakerError):
        speaker.load_profile(tmp_path)
    assert list(tmp_path.iterdir()) == before


def test_injectable_encoder_only_commits_on_verified_success(tmp_path, model):
    def encoder(_):
        return vector()
    session = speaker.Enrollment(speaker.model_digest(model), encoder=encoder)
    for _ in range(4):
        session.add_audio(tmp_path / "synthetic.wav")
    assert session.verify(encoder(None))
    session.save(tmp_path)
    speaker.delete_profile(tmp_path)
    assert not speaker.profile_path(tmp_path).exists()
    assert not list(speaker.profile_path(tmp_path).parent.iterdir())


def test_read_audio_validates_format_silence_and_bounds(tmp_path):
    path = tmp_path / "sample.wav"
    def audio(rate=16000, channels=1, silent=False, seconds=2):
        import array
        data = array.array("h", (0 if silent else int(2000 * math.sin(i * .1))
                                 for i in range(rate * seconds)))
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(channels)
            stream.setsampwidth(2)
            stream.setframerate(rate)
            stream.writeframes(data.tobytes())
    audio()
    assert len(speaker.read_wave(path)) == 32000
    for kwargs in ({"rate":8000}, {"silent":True}, {"seconds":0}):
        audio(**kwargs)
        with pytest.raises(speaker.SpeakerError):
            speaker.read_wave(path)


def test_missing_optional_backend_never_downloads_or_fakes_embeddings(tmp_path, model, monkeypatch):
    monkeypatch.setattr(speaker, "backend_available", lambda: False)
    with pytest.raises(speaker.SpeakerError, match="missing"):
        speaker.SpeakerEncoder(model)
