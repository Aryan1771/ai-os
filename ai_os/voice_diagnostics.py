"""Explicit native voice checks; no actions, stored conversation or remote model."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
import signal
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit

import requests

from ai_os.config import AI_OS_HOME, load_config, load_raw_config
from ai_os.voice_timings import elapsed_timing, public_timings, record_timing
from ai_os.voice_progress import ProgressReporter, progress_message, public_progress

PHRASES = {
    "en": "Hello. Your REgenOS voice check is ready.",
    "hi": "नमस्ते। मैं आपकी बात सुनने के लिए तैयार हूँ।",
}


def local_endpoint(config):
    endpoint = urlsplit(config.ollama_url)
    if (
        config.ai_provider != "ollama"
        or endpoint.scheme != "http"
        or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError("The voice check requires local Ollama.")
    return urlunsplit((endpoint.scheme, endpoint.netloc, "/api/chat", "", ""))


def local_reply(text, language, home, *, metrics=None):
    """One bounded, tool-free turn. Never use the private conversation harness."""
    from ai_os.hardware_profile import inference_slot, runtime_policy

    config = load_config(home)
    url = local_endpoint(config)
    from ai_os.companion_persona import mood_guidance
    from ai_os.companion_state import read_state

    presentation = load_raw_config(home)
    if language not in PHRASES or not isinstance(text, str) or not 1 <= len(text) <= 8000:
        raise ValueError("The voice check needs clear English or Hindi speech.")
    prompt = (
        "You are RE, a warm desktop companion. This is a voice diagnostic with no tools, "
        "memory or computer actions. Reply naturally to the current utterance in one or two "
        "sentences, at most 35 words. Never claim to have opened, deleted, changed or executed anything. "
        + (
            "Reply only in Hindi using Devanagari."
            if language == "hi"
            else "Reply only in English."
        )
    )
    prompt += mood_guidance(presentation, read_state(home))
    policy = runtime_policy(home)
    if policy and not policy.get("ready"):
        raise ValueError("The configured model did not pass local hardware admission.")
    options = dict(policy["options"] if policy else {"num_ctx": config.model_context_tokens})
    options.update(
        num_ctx=min(options.get("num_ctx", config.model_context_tokens), 4096),
        num_predict=96,
        temperature=0.3,
    )
    deadline = time.monotonic() + 40
    with inference_slot(home), requests.Session() as session:
        session.trust_env = False
        with session.post(
            url,
            json={
                "model": policy["model"] if policy else config.ollama_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                "options": options,
            },
            timeout=(3, 35),
            allow_redirects=False,
            stream=True,
        ) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("The local model did not return a direct reply.")
            payload = bytearray()
            for part in response.iter_content(4096):
                payload.extend(part)
                if len(payload) > 65536 or time.monotonic() > deadline:
                    raise ValueError("The local reply exceeded its time or size limit.")
    value = json.loads(payload)
    if not isinstance(value, dict) or not isinstance(value.get("message"), dict):
        raise ValueError("The local model returned an invalid reply.")
    message = value["message"]
    reply = message.get("content")
    if (
        message.get("tool_calls")
        or message.get("function_call")
        or not isinstance(reply, str)
        or not reply.strip()
        or len(reply) > 2000
    ):
        raise ValueError("The local model did not return a short spoken reply.")
    # Structured tool proposals must never be spoken as if executed.
    try:
        structured = json.loads(reply)
    except ValueError:
        structured = None
    if isinstance(structured, (dict, list)) or reply.lstrip().startswith("```"):
        raise ValueError("Computer actions are unavailable during the voice check.")
    if metrics is not None:
        for name in ("load_duration", "prompt_eval_duration", "eval_duration"):
            duration = value.get(name)
            if type(duration) is int and 0 <= duration <= 1_000_000_000_000:
                metrics[name.replace("_duration", "_seconds")] = round(duration / 1e9, 3)
    return reply.strip()


def check_voice(action, language, *, home=AI_OS_HOME, human_confirmed=False, metrics=None,
                on_progress=None):
    """Trusted local UI only. A microphone click is not permission for any tool."""
    if human_confirmed is not True:
        raise PermissionError("Explicit local approval is required for each voice check.")
    if action not in {"play", "record"} or language not in {"auto", "en", "hi"}:
        raise ValueError("Unsupported voice check.")
    progress = ProgressReporter(on_progress)
    progress.emit("preparing")
    from ai_os.companion_state import publish_state
    from ai_os.services.voice_input import capture_once
    from ai_os.services.voice_errors import VoicePipelineError
    from ai_os.speech_lease import speech_lease
    from ai_os.speech_queue import SpeechQueue

    raw = load_raw_config(home)
    config = load_config(home)
    if action == "record" and raw["always_listening_enabled"]:
        raise PermissionError(
            "Disable continuous listening before recording a separate voice check."
        )
    if action == "record" and not config.speech_enabled:
        raise PermissionError("Enable spoken replies before testing the complete voice loop.")
    if action == "record":
        local_endpoint(config)
    started = time.monotonic()
    with speech_lease(home) as acquired:
        if not acquired:
            raise VoicePipelineError(
                "voice_busy", "Another voice interaction is active. Try again when it finishes."
            )
        timings = metrics if type(metrics) is dict else {}
        timings.clear()
        phase = "listening"
        try:
            transcript = ""
            actual_language = "en" if language == "auto" else language
            if action == "record":
                config = replace(
                    config,
                    whisper_language=actual_language,
                    reply_language_mode="match" if language == "auto" else "selected",
                    voice_command_seconds=8,
                    voice_max_utterance_seconds=20,
                )
                capture_started = time.monotonic()
                try:
                    recognized = capture_once(config, return_result=True, metrics=timings,
                                              **({"on_progress": on_progress} if on_progress is not None else {}))
                finally:
                    elapsed_timing(timings, "capture_and_stt_seconds", capture_started)
                actual_language = recognized.detected_language if language == "auto" else language
                if actual_language not in PHRASES or not recognized.ok:
                    raise VoicePipelineError(
                        "language_unknown",
                        "Could not identify English or Hindi clearly. No action was submitted.",
                    )
                transcript = recognized.text
                publish_state("thinking", home=home)
                progress.emit("thinking")
                phase = "thinking"
                model_started = time.monotonic()
                model_metrics = {}
                try:
                    reply = local_reply(transcript, actual_language, home, metrics=model_metrics)
                finally:
                    elapsed_timing(timings, "model_seconds", model_started)
                    for key in ("load_seconds", "prompt_eval_seconds", "eval_seconds"):
                        record_timing(timings, "model_" + key, model_metrics.get(key))
            else:
                reply = PHRASES[actual_language]
            # Re-read revocation before output; explicit playback-only tests are
            # allowed while ordinary Speak replies is off, as in the existing test.
            if action == "record" and not load_raw_config(home)["speech_enabled"]:
                raise PermissionError("Spoken replies were disabled; playback was cancelled.")
            publish_state("speaking", home=home)
            progress.emit("speaking")
            phase = "speaking"
            playback_started = time.monotonic()
            try:
                SpeechQueue(
                    config.piper_model,
                    hindi_model=config.piper_hindi_model,
                    length_scale=config.piper_length_scale,
                ).speak_text(reply, metrics=timings)
            finally:
                elapsed_timing(timings, "synthesis_and_playback_seconds", playback_started)
            result = {
                "ok": True,
                "transcript": transcript,
                "reply": reply,
                "language": actual_language,
                "message": "Playback completed. Only you can confirm audibility and whether the reply matched what you said.",
            }
        except Exception as exc:
            from ai_os.services.voice_errors import diagnostic

            code, message = diagnostic(exc, phase)
            raise VoicePipelineError(code, message) from None
        finally:
            elapsed_timing(timings, "total_seconds", started)
            sanitized = public_timings(timings)
            timings.clear()
            timings.update(sanitized)
            publish_state("idle", home=home)
    return {**result, "timings": public_timings(timings)}


def create_dialog(home=AI_OS_HOME, parent=None):
    """Lazy Qt import keeps the worker independent of graphical/audio activation."""
    from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
    )

    class VoiceCheckDialog(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle("REgenOS — guided voice check")
            self.resize(680, 540)
            self.process = None
            self.worker_group = None
            self.temporary = None
            self.output = bytearray()
            self.output_bytes = 0
            layout = QVBoxLayout(self)
            notice = QLabel(
                "Uses saved settings. Nothing records until you enable consent and click Record & reply. "
                "Speak a short English or Hindi sentence, then wait for the saved ending pause. "
                "Maximum speech: 20 seconds. No computer actions, saved chat or remote AI. "
                "The transcript stays in this window; temporary audio is deleted after processing."
            )
            notice.setWordWrap(True)
            layout.addWidget(notice)
            self.language = QComboBox()
            for value, label in (
                ("auto", "Detect English / Hindi"),
                ("en", "English"),
                ("hi", "Hindi"),
            ):
                self.language.addItem(label, value)
            saved = load_raw_config(home)
            selected = (
                "auto" if saved["reply_language_mode"] == "match" else saved["whisper_language"]
            )
            self.language.setCurrentIndex(max(0, self.language.findData(selected)))
            layout.addWidget(self.language)
            self.consent = QCheckBox("Allow one microphone recording when I click Record && reply")
            layout.addWidget(self.consent)
            controls = QHBoxLayout()
            self.play = QPushButton("Play test voice")
            self.record = QPushButton("Record && reply")
            self.record.setObjectName("primary")
            self.record.setEnabled(False)
            self.stop = QPushButton("Stop")
            self.stop.setEnabled(False)
            for button in (self.play, self.record, self.stop):
                controls.addWidget(button)
            layout.addLayout(controls)
            self.status = QLabel(
                "Ready. Microphone off. Playback success does not prove you heard it."
            )
            self.status.setTextFormat(Qt.TextFormat.PlainText)
            self.status.setWordWrap(True)
            self.status.setAccessibleName("Voice check progress")
            self.status.setMinimumHeight(40)
            layout.addWidget(self.status)
            self.details = QPlainTextEdit()
            self.details.setReadOnly(True)
            self.details.setPlaceholderText(
                "The transcript, reply and timings appear here when the check finishes. "
                "The status above shows recording and processing progress. "
                "Nothing records until you allow it and click Record & reply."
            )
            layout.addWidget(self.details, 1)
            self.timer = QTimer(self)
            self.timer.setTimerType(Qt.TimerType.PreciseTimer)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(
                lambda: self.cancel("Voice check timed out; capture/playback stopped.")
            )
            self.consent.toggled.connect(
                lambda enabled: self.record.setEnabled(enabled and self.process is None)
            )
            self.play.clicked.connect(lambda: self.start("play"))
            self.record.clicked.connect(lambda: self.start("record"))
            self.stop.clicked.connect(
                lambda: self.cancel("Stopped. No request was submitted to computer tools.")
            )

        def start(self, action):
            if self.process is not None or action == "record" and not self.consent.isChecked():
                return
            self.output.clear()
            self.output_bytes = 0
            self.details.clear()
            try:
                self.temporary = tempfile.TemporaryDirectory(prefix="regenos-voice-check-")
            except OSError:
                self.status.setText(
                    "Private temporary storage is unavailable. No microphone recording started."
                )
                return
            try:
                self.start_worker(action)
            except (OSError, RuntimeError):
                self.cancel("Voice check could not start. No microphone request was submitted.")

        def remember_group(self):
            if self.process is not None and sys.platform == "linux":
                pid = self.process.processId()
                try:
                    if pid > 1 and pid != os.getpgrp() and os.getpgid(pid) == pid:
                        self.worker_group = pid
                except (ProcessLookupError, PermissionError):
                    pass

        def signal_group(self, signum):
            if self.worker_group is None:
                return False
            try:
                os.killpg(self.worker_group, signum)
            except ProcessLookupError:
                pass
            except PermissionError:
                return False
            return True

        def start_worker(self, action):
            process = QProcess(self)
            self.process = process
            if sys.platform == "linux":
                process.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
            env = QProcessEnvironment.systemEnvironment()
            env.insert("AI_OS_HOME", str(home))
            env.insert("AI_OS_VOICE_TMP", self.temporary.name)
            process.setProcessEnvironment(env)
            process.started.connect(self.remember_group)
            process.readyReadStandardOutput.connect(self.read_output)
            process.readyReadStandardError.connect(lambda: process.readAllStandardError())
            process.finished.connect(self.finished)
            process.errorOccurred.connect(
                lambda error: (
                    self.cancel("Voice check could not start.")
                    if error == QProcess.ProcessError.FailedToStart
                    else None
                )
            )
            self.play.setEnabled(False)
            self.record.setEnabled(False)
            self.language.setEnabled(False)
            self.consent.setEnabled(False)
            self.stop.setEnabled(True)
            self.status.setText(
                "Preparing the voice check. Microphone has not started yet."
                if action == "record"
                else "Playing the selected test voice. Microphone off."
            )
            self.timer.start(110000)
            process.start(
                sys.executable,
                [
                    "-m",
                    "ai_os.voice_diagnostics",
                    "--worker",
                    action,
                    "--language",
                    self.language.currentData(),
                    "--progress",
                    "--confirmed",
                ],
            )

        def read_output(self):
            if self.process is None:
                return
            data = bytes(self.process.readAllStandardOutput())
            self.output_bytes += len(data)
            self.output.extend(data)
            if self.output_bytes > 65536 or len(self.output) > 65536:
                self.cancel("Voice check returned too much data; stopped.")
                return
            while b"\n" in self.output:
                line, _separator, remainder = self.output.partition(b"\n")
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeError):
                    return  # Final-result parsing retains the existing failure path.
                if not isinstance(event, dict) or event.get("event") != "voice_progress":
                    return  # Preserve the unchanged final JSON for finished().
                event = public_progress(event)
                if event is None:
                    self.cancel("Voice check returned invalid progress; stopped.")
                    return
                self.output[:] = remainder
                self.status.setText(progress_message(event))

        def finished(self, code, _status):
            if self.process is None:
                return
            self.read_output()
            if self.process is None:
                return
            try:
                result = json.loads(self.output)
                if not isinstance(result, dict):
                    raise ValueError()
                if code == 0 and result.get("ok"):
                    details = (
                        "You: "
                        + str(result.get("transcript", ""))[:8000]
                        + "\n\nRE: "
                        + str(result.get("reply", ""))[:2000]
                    )
                else:
                    details = ""
                timings = public_timings(result.get("timings"))
                if timings:
                    details += (
                        "\n\nTiming in seconds. Audio durations overlap capture; do not add them to wall time.\n"
                        + json.dumps(timings, ensure_ascii=True)
                    )
                self.details.setPlainText(details.strip())
                self.status.setText(
                    str(result.get("message", "Voice check did not complete."))[:400]
                )
            except (ValueError, TypeError):
                self.status.setText("Voice check did not return a valid result. No tools were run.")
            self.release()

        def release(self):
            self.timer.stop()
            # The worker may already have exited while a child ignores TERM.
            # Only use the group verified when our fresh session was created.
            self.signal_group(signal.SIGKILL)
            self.worker_group = None
            if self.process is not None:
                self.process.deleteLater()
                self.process = None
            if self.temporary is not None:
                self.temporary.cleanup()
                self.temporary = None
            self.output.clear()
            self.output_bytes = 0
            self.play.setEnabled(True)
            self.consent.setEnabled(True)
            self.language.setEnabled(True)
            self.record.setEnabled(self.consent.isChecked())
            self.stop.setEnabled(False)

        def cancel(self, message):
            if self.process is not None:
                process = self.process
                process.blockSignals(True)
                if process.state() != QProcess.ProcessState.NotRunning:
                    self.remember_group()
                    if not self.signal_group(signal.SIGTERM):
                        process.terminate()
                    if not process.waitForFinished(2000):
                        if not self.signal_group(signal.SIGKILL):
                            process.kill()
                        process.waitForFinished(1500)
            self.release()
            self.status.setText(message)

        def done(self, result):
            self.cancel("Closed. Microphone off.")
            self.details.clear()
            super().done(result)

        def closeEvent(self, event):
            self.cancel("Closed. Microphone off.")
            self.details.clear()
            super().closeEvent(event)

    return VoiceCheckDialog()


def main():
    parser = argparse.ArgumentParser(description="Explicit REgenOS voice diagnostic")
    parser.add_argument("--worker", choices=("play", "record"))
    parser.add_argument("--language", choices=("auto", "en", "hi"), default="auto")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()
    if args.worker:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(130))
        timings = {}
        from ai_os.voice_check_status import VoiceCheckStatus
        status = (VoiceCheckStatus(Path(os.environ.get("AI_OS_HOME", str(AI_OS_HOME))).expanduser(), args.worker)
                  if args.confirmed is True else None)
        def emit_progress(event):
            event = public_progress(event)
            if event is not None:
                if status is not None:
                    status.progress(event)
                if args.progress:
                    print(json.dumps(event, ensure_ascii=True, allow_nan=False), flush=True)
        try:
            result = check_voice(args.worker, args.language, human_confirmed=args.confirmed, metrics=timings,
                                 **({"on_progress": emit_progress} if args.progress or status is not None else {}))
        except SystemExit:
            if status is not None:
                status.publish("cancelled", code="cancelled", timings=timings)
            raise
        except Exception as exc:
            from ai_os.services.voice_errors import diagnostic

            code, message = diagnostic(
                exc, "thinking" if isinstance(exc, requests.RequestException) else "listening"
            )
            if isinstance(exc, (ValueError, PermissionError)):
                code, message = (
                    "voice_check_unavailable",
                    "Check saved local voice settings, spoken replies and language. Disable continuous listening before a separate microphone test. No tools were run.",
                )
            result = {"ok": False, "code": code, "message": message, "timings": public_timings(timings)}
        if status is not None:
            status.publish("completed" if result["ok"] else "failed", code=result.get("code", ""),
                           timings=result.get("timings", timings))
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 0 if result["ok"] else 1
    from PySide6.QtWidgets import QApplication
    from ai_os.native_widgets import theme_stylesheet

    app = QApplication(["regenos-voice-check"])
    app.setStyle("Fusion")
    app.setStyleSheet(theme_stylesheet(load_raw_config()["theme"]))
    dialog = create_dialog()
    dialog.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
