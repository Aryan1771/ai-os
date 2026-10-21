"""Explicit one-shot input with the same bounded speech endpointing as listening."""
import os
import subprocess
import tempfile
import time
from collections import deque
from pathlib import Path

from ai_os.companion_state import publish_state
from ai_os.services.listener import AlwaysListeningService
from ai_os.services.stt import TranscriptionResult, WhisperCppTranscriber
from ai_os.voice_timings import elapsed_timing
from ai_os.voice_progress import ProgressReporter


def capture_once(config, *, return_result=False, metrics=None, on_progress=None):
    from ai_os.audio_input import recorder_arguments
    from ai_os.speaker_filter import filter_utterance
    match_language = getattr(config, "reply_language_mode", "selected") == "match"
    transcriber = WhisperCppTranscriber(config.whisper_cli, config.whisper_model,
                                       language="auto" if match_language else config.whisper_language,
                                       **({"detect_language": True} if match_language else {}))
    ready, reason = transcriber.availability()
    if not ready:
        raise RuntimeError(reason)
    progress = ProgressReporter(on_progress)

    def recording_complete():
        from ai_os.services.voice_errors import VoicePipelineError
        if type(listener.stop_recorder()) is not int:
            raise VoicePipelineError("capture_failed", "Could not confirm the recorder stopped; no request was submitted.")
        publish_state("transcribing", home=config.home)
        progress.emit("microphone_off")

    with tempfile.TemporaryDirectory(prefix="regenos-mic-", dir=os.environ.get("AI_OS_VOICE_TMP")) as directory:
        listener = AlwaysListeningService(
            run_dir=Path(directory), transcriber=transcriber, on_transcript=lambda _: None,
            require_wake_word=False, command_seconds=config.voice_command_seconds,
            silence_seconds=config.voice_silence_seconds,
            max_utterance_seconds=config.voice_max_utterance_seconds,
            on_activity=lambda phase: publish_state(phase, home=config.home),
            speaker_filter=lambda path: filter_utterance(path, config.home),
            on_capture_complete=recording_complete, on_progress=on_progress,
        )
        progress.emit("checking_input")
        listener._process = subprocess.Popen(
            ["/usr/bin/pw-record", *recorder_arguments(getattr(config, "voice_input_target", ""))],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, bufsize=0, shell=False,
        )
        waiting_started = time.monotonic()
        deadline = waiting_started + config.voice_command_seconds
        preroll = deque(maxlen=5)
        speech_frames = 0
        waiting = True
        try:
            publish_state("listening", home=config.home)
            progress.emit("waiting_for_speech")
            while time.monotonic() < deadline:
                audio = listener._read_audio(2560)
                if len(audio) != 2560:
                    break
                preroll.append(audio)
                speech_frames = speech_frames + 1 if listener.has_speech(audio) else 0
                if speech_frames >= 3:
                    progress.emit("capturing", captured_seconds=len(b"".join(preroll)) / 32000,
                                  silence_seconds=0, required_silence_seconds=config.voice_silence_seconds)
                    elapsed_timing(metrics, "speech_detection_wait_seconds", waiting_started)
                    waiting = False
                    text = listener._capture_and_transcribe(
                        b"".join(preroll), 2560,
                        **({"metrics": metrics} if metrics is not None else {}),
                    ).strip()
                    if text:
                        return (TranscriptionResult(True, text, detected_language=getattr(
                            listener, "last_transcription_language", None
                        )) if return_result else text)
                    if getattr(listener, "last_capture_error", None) is not None:
                        raise listener.last_capture_error
                    break
            raise RuntimeError("No speech recognized. Check input level and selected language.")
        finally:
            if waiting:
                elapsed_timing(metrics, "speech_detection_wait_seconds", waiting_started)
            listener.stop()
