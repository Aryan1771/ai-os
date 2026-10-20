"""Synthetic comparison safety and metrics; tests never run audio/model programs."""
import json
from pathlib import Path
import subprocess
import wave
from types import SimpleNamespace

import pytest

from ai_os import voice_model_comparison as comparison
from ai_os.services.stt import TranscriptionResult


@pytest.fixture(autouse=True)
def no_real_programs(monkeypatch):
    monkeypatch.setattr(comparison, "run_bounded", lambda *args, **kwargs: pytest.fail("Unexpected real subprocess"))


@pytest.fixture
def assets(tmp_path, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    base = models / "ggml-base.bin"
    base.write_bytes(b"lmggsynthetic model, never inferred")
    voices = {}
    for language in comparison.PHRASES:
        model = models / (language + ".onnx")
        model.write_bytes(b"synthetic voice, never inferred")
        Path(str(model) + ".json").write_text(json.dumps({"language": {"code": language + "_test"},
                                                         "audio": {"sample_rate":22050}}))
        voices[language] = model
    config = SimpleNamespace(whisper_model=base, piper_model=voices["en"], piper_hindi_model=voices["hi"])
    monkeypatch.setattr(comparison, "load_config", lambda _: config)
    monkeypatch.setattr(comparison, "installed_executables", lambda: "/synthetic/venv/piper")

    class NoGpu:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def report(self): return {"sample_count":0,"sampled_peak_mib_by_device":[]}

    monkeypatch.setattr(comparison, "GpuSamples", NoGpu)
    return tmp_path, config


def write_audio(path, rate=16000):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(b"\x01\x00" * rate)


def fake_execution(monkeypatch, *, fail_stage=None):
    calls, directories = [], []

    def execute(argv, directory, deadline, timeout=35):
        calls.append(argv)
        directories.append(directory)
        assert directory.stat().st_mode & 0o777 == 0o700
        if "--input_file" in argv:
            if fail_stage == "piper":
                raise comparison.ComparisonError("A synthetic failure")
            source = Path(argv[argv.index("--input_file") + 1])
            assert source.read_text() in (*comparison.PHRASES.values(), *comparison.ADDITIONAL_HINDI)
            assert source.stat().st_mode & 0o777 == 0o600
            write_audio(Path(argv[argv.index("--output_file") + 1]), 22050)
            return ""
        if argv[0] == "/usr/bin/ffmpeg":
            write_audio(Path(argv[-1]))
            return ""
        if fail_stage == "stt":
            raise comparison.ComparisonError("A synthetic failure")
        language = argv[argv.index("--language") + 1]
        mode = argv[argv.index("--mode") + 1]
        accepted = language == "en" or mode == "script_hint"
        return json.dumps({"accepted":accepted,"detected_language":language if mode == "match" else None,"backend":"cpu",
                           "error_code":"" if accepted else "transcription_script_mismatch",
                           "correctness":{"normalized_exact_match":accepted,"word_error_rate":0 if accepted else None,
                                          "character_error_rate":0 if accepted else None}})

    monkeypatch.setattr(comparison, "execute", execute)
    return calls, directories


def test_metrics_preserve_hindi_marks_and_normalize_case_and_punctuation():
    assert comparison.correctness("Hello, world!", "hello world.") == {
        "normalized_exact_match":True,"word_error_rate":0,"character_error_rate":0}
    assert comparison.correctness("नमस्ते।", "नमस्ते!")["normalized_exact_match"]
    assert not comparison.correctness("नमस्ते", "नमसत")["normalized_exact_match"]
    assert comparison.correctness("one two three", "one four")["word_error_rate"] == .6667


def test_complete_comparison_uses_fixed_phrases_no_mic_playback_or_settings_changes(assets, monkeypatch):
    home, config = assets
    sentinel = home / "config.json"
    sentinel.write_text("private settings must not be changed")
    calls, directories = fake_execution(monkeypatch)
    result = comparison.compare(home=home, script_hint=True)
    assert result["ok"] and result["synthetic_only"]
    assert result["microphone_opened"] is result["audible_playback"] is result["settings_changed"] is result["downloads"] is False
    assert len(result["results"]) == 5
    assert len(result["synthesis"]) == 2
    assert result["results"][2]["error_code"] == "transcription_script_mismatch"
    assert result["results"][2]["correctness"]["word_error_rate"] is None
    assert not any(directory.exists() for directory in directories)
    assert not any("pw-record" in arg or "pw-play" in arg for call in calls for arg in call)
    assert sentinel.read_text() == "private settings must not be changed"
    assert config.whisper_model.name == "ggml-base.bin"
    assert len(result["whisper_models"][0]["sha256"]) == 64


def test_additional_hindi_phrases_are_fixed_numbered_samples(assets, monkeypatch):
    home, _ = assets
    calls, _directories = fake_execution(monkeypatch)
    result = comparison.compare(home=home, additional_hindi=True)
    assert len(result["synthesis"]) == 5 and len(result["results"]) == 10
    assert {row["sample"] for row in result["results"] if row["language"] == "hi"} == {0,1,2,3}
    assert [row["reference"] for row in result["synthesis"] if row["language"] == "hi"] == [comparison.PHRASES["hi"], *comparison.ADDITIONAL_HINDI]
    assert all("--sample" in call for call in calls if "--worker" in call)


@pytest.fixture
def local_cli(assets):
    import hashlib

    home, _ = assets
    workspace = home / "build/whisper-cpp-v1.9.5-cuda-d1be6fde-synthetic"
    workspace.mkdir(parents=True, mode=0o700)
    executable = workspace / "build/bin/whisper-cli"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"\x7fELFsynthetic executable: never run")
    executable.chmod(0o755)
    manifest = {"schema":1,"source_url":"https://github.com/ggml-org/whisper.cpp",
                "source_tag":"v1.9.5","source_commit":comparison.CUDA_SOURCE_COMMIT,
                "whisper_cli":str(executable),"whisper_cli_sha256":hashlib.sha256(executable.read_bytes()).hexdigest()}
    manifest_path = workspace / "regenos-build.json"
    manifest_path.write_text(json.dumps(manifest))
    manifest_path.chmod(0o600)
    return executable, manifest_path


def test_verified_local_cli_is_explicit_and_never_saved_as_runtime_selection(assets, local_cli, monkeypatch):
    home, _ = assets
    executable, _manifest = local_cli
    calls, _directories = fake_execution(monkeypatch)
    result = comparison.compare(home=home, whisper_cli=executable)
    assert result["whisper_cli"]["kind"] == "verified_local_cuda_build"
    assert result["whisper_cli"]["source_commit"] == comparison.CUDA_SOURCE_COMMIT
    assert all(call[call.index("--whisper-cli")+1] == str(executable) for call in calls if "--worker" in call)
    assert not (home / "config.json").exists()


@pytest.mark.parametrize("tamper", ["binary", "manifest", "permissions", "script"])
def test_tampered_cli_candidate_is_rejected_before_execution(assets, local_cli, monkeypatch, tamper):
    home, _ = assets
    executable, manifest = local_cli
    calls, _directories = fake_execution(monkeypatch)
    if tamper == "binary":
        executable.write_bytes(b"\x7fELFdifferent binary")
    elif tamper == "manifest":
        manifest.write_text(json.dumps({"schema":1,"source_commit":"unreviewed"}))
    elif tamper == "permissions":
        executable.chmod(0o777)
    else:
        executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    with pytest.raises(comparison.ComparisonError):
        comparison.compare(home=home, whisper_cli=executable)
    assert not calls


def test_arbitrary_cli_location_is_not_an_allowed_command_candidate(assets):
    import time

    home, _ = assets
    with pytest.raises(comparison.ComparisonError):
        comparison.validated_cli(Path("/usr/bin/bash"), home, time.monotonic()+2)


@pytest.mark.parametrize("stage", ["piper", "stt"])
def test_subprocess_failure_removes_all_temporary_audio(assets, monkeypatch, stage):
    home, _ = assets
    _, directories = fake_execution(monkeypatch, fail_stage=stage)
    with pytest.raises(comparison.ComparisonError):
        comparison.compare(home=home)
    assert directories and not any(directory.exists() for directory in directories)


@pytest.mark.parametrize("name", ["../../etc/shadow", "models/../private.bin", "models/ggml-secret.txt"])
def test_outside_and_credential_like_paths_are_rejected_before_model_read(assets, name):
    home, _ = assets
    with pytest.raises(comparison.ComparisonError):
        comparison.installed_asset(home / name, home, suffix=".bin", maximum=10000)


def test_model_and_model_directory_symlinks_are_rejected(assets):
    home, config = assets
    symlink = home / "models/ggml-linked.bin"
    symlink.symlink_to(config.whisper_model)
    with pytest.raises(comparison.ComparisonError, match="symlinks"):
        comparison.installed_asset(symlink, home, suffix=".bin", maximum=10000)
    nested = home / "models/nested"
    nested.symlink_to(home / "models", target_is_directory=True)
    with pytest.raises(comparison.ComparisonError, match="symlinks"):
        comparison.installed_asset(nested / config.whisper_model.name, home, suffix=".bin", maximum=10000)


def test_misnamed_nonmodel_file_is_rejected_before_hash_or_execution(assets, monkeypatch):
    home, config = assets
    config.whisper_model.write_bytes(b"SYNTHETIC_PRIVATE_NONMODEL_CONTENT")
    monkeypatch.setattr(comparison, "digest", lambda *args: pytest.fail("Do not hash a nonmodel file"))
    with pytest.raises(comparison.ComparisonError) as failure:
        comparison.compare(home=home)
    assert "SYNTHETIC_PRIVATE" not in str(failure.value)


def test_worker_never_returns_transcript_and_preserves_rejection(assets, tmp_path, monkeypatch):
    home, config = assets
    directory = home / "regenos-model-compare-synthetic"
    directory.mkdir(mode=0o700)
    path = directory / "hi-16k.wav"
    write_audio(path)

    class Transcriber:
        def __init__(self, executable, model, **kwargs):
            assert kwargs["detect_language"] and kwargs["timeout_sec"] == 40

        def transcribe_file(self, audio):
            assert audio == path
            return TranscriptionResult(False, "", error_code="transcription_script_mismatch")

    monkeypatch.setattr(comparison, "WhisperCppTranscriber", Transcriber)
    monkeypatch.setenv("AI_OS_VOICE_TMP", "previous-value")
    result = comparison.worker(config.whisper_model, path, "hi", "match", home)
    assert not result["accepted"] and result["correctness"]["word_error_rate"] is None
    assert "text" not in result and "transcript" not in result


def test_worker_rejects_noncomparison_or_public_audio_directory(assets):
    home, config = assets
    directory = home / "recordings"
    directory.mkdir()
    path = directory / "en-16k.wav"
    write_audio(path)
    with pytest.raises(comparison.ComparisonError):
        comparison.worker(config.whisper_model, path, "en", "selected", home)
    directory.rename(home / "regenos-model-compare-public")
    public = home / "regenos-model-compare-public"
    public.chmod(0o755)
    with pytest.raises(comparison.ComparisonError):
        comparison.worker(config.whisper_model, public / path.name, "en", "selected", home)


def test_numbered_worker_scores_its_own_additional_phrase(assets, monkeypatch):
    home, config = assets
    directory = home / "regenos-model-compare-numbered"
    directory.mkdir(mode=0o700)
    path = directory / "hi-2-16k.wav"
    write_audio(path)

    class Transcriber:
        last_backend = "cpu"

        def __init__(self, *args, **kwargs):
            pass

        def transcribe_file(self, _audio):
            return TranscriptionResult(True, comparison.ADDITIONAL_HINDI[1], detected_language="hi")

    monkeypatch.setattr(comparison, "WhisperCppTranscriber", Transcriber)
    monkeypatch.setenv("AI_OS_VOICE_TMP", "previous-value")
    result = comparison.worker(config.whisper_model, path, "hi", "match", home, sample=2)
    assert result["accepted"] and result["correctness"]["normalized_exact_match"]
    assert result["backend"] == "cpu"


@pytest.mark.parametrize("transcript, accepted", [(comparison.PHRASES["hi"], True),
                                                  ("یہ ایک جملہ ہے", False),
                                                  ("यह ایک جملہ ہے", False)])
def test_isolated_hint_is_fixed_context_and_preserves_runtime_script_guard(assets, monkeypatch, transcript, accepted):
    home, config = assets
    directory = home / "regenos-model-compare-hint"
    directory.mkdir(mode=0o700)
    path = directory / "hi-16k.wav"
    write_audio(path)

    def run(argv, **kwargs):
        assert argv[argv.index("--prompt")+1] == comparison.HINDI_HINT
        assert comparison.PHRASES["hi"] not in argv
        assert "-tr" not in argv and kwargs["shell"] is False
        assert kwargs["stdin"] == kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.PIPE
        report = Path(argv[argv.index("-of")+1] + ".json")
        report.write_text(json.dumps({"model":{"multilingual":True},"transcription":[{"text":transcript}]}))
        return SimpleNamespace(returncode=0, stderr=b"whisper_backend_init_gpu: no GPU found\n")

    monkeypatch.setattr(comparison.subprocess, "run", run)
    result = comparison.worker(config.whisper_model, path, "hi", "script_hint", home)
    assert result["accepted"] is accepted
    assert result["error_code"] == ("" if accepted else "transcription_script_mismatch")
    assert not (directory / "hint-result.json").exists()
    assert transcript not in json.dumps(result)


def test_gpu_report_is_device_wide_sequential_and_sampler_failure_is_not_a_pass():
    gpu = comparison.GpuSamples()
    gpu.samples = [[100,200],[150,190]]
    gpu.failures = 1
    report = gpu.report()
    assert report["sampled_peak_mib_by_device"] == [150,200]
    assert report["sampling_failures"] == 1
    assert "sequential" in report["scope"] and "simultaneous" in report["scope"]


def test_execute_timeout_never_exposes_raw_backend_output(tmp_path, monkeypatch):
    import time

    def fail(*args, **kwargs):
        assert kwargs["timeout"] <= 35 and kwargs["output_limit"] == 65536
        raise subprocess.TimeoutExpired(["private backend arguments"], 2, stderr="private stderr")

    monkeypatch.setattr(comparison, "run_bounded", fail)
    with pytest.raises(comparison.ComparisonError) as result:
        comparison.execute(["/synthetic/tool"], tmp_path, time.monotonic()+40)
    assert "private" not in str(result.value)
