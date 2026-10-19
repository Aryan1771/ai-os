"""Public diagnostic codes contain no transcript, command output or private paths."""
import subprocess

import requests


class VoicePipelineError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def diagnostic(exc, phase):
    if isinstance(exc, VoicePipelineError):
        return exc.code, str(exc)
    if isinstance(exc, requests.Timeout):
        return "model_timeout", "Model reply timed out. Check local model load and context size."
    if isinstance(exc, requests.ConnectionError):
        return "model_connection", "Cannot reach the configured model service. Check AI connection readiness."
    if isinstance(exc, requests.HTTPError):
        return "model_http", "Model service rejected the request. Check the selected installed model and provider settings."
    if isinstance(exc, subprocess.TimeoutExpired):
        return "speech_timeout" if phase == "speaking" else "capture_timeout", "Voice subprocess timed out; check readiness and selected audio devices."
    if phase == "speaking":
        return "speech_failed", "Reply generation finished, but speech failed. Check Piper voice assets and PipeWire playback."
    if phase == "thinking":
        return "reasoning_failed", "Speech reached the assistant, but processing failed. Check model readiness, busy requests and runtime configuration."
    return "capture_failed", "Microphone or wake detection failed. Check the PipeWire input, Whisper model and wake configuration."
