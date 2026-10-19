"""Public diagnostic codes contain no transcript, command output or private paths."""
import subprocess

import requests

from ai_os.services.stt import STT_ERRORS


VOICE_MESSAGES = {
    **STT_ERRORS,
    "language_unknown": "Could not identify English or Hindi clearly. Choose a language or repeat the phrase; no action was submitted.",
    "speaker_rejected": "Voice did not pass the enrolled-speaker filter; no request was submitted. Check local enrollment or disable the filter in Voice settings.",
    "speaker_unavailable": "Speaker verification unavailable; no request submitted. Check local enrollment.",
    "speaker_timeout": "Speaker verification timed out; no request submitted. Check the local speaker model.",
    "voice_busy": "Another voice interaction is active. Please try again after it finishes.",
    "utterance_too_long": "Speech exceeded the maximum utterance duration before the ending pause. No request was submitted; please repeat in shorter parts.",
    "model_timeout": "Model reply timed out. Check local model load and context size.",
    "model_connection": "Cannot reach the configured model service. Check AI connection readiness.",
    "model_http": "Model service rejected the request. Check the selected installed model and provider settings.",
    "speech_timeout": "Voice subprocess timed out; check readiness and selected audio devices.",
    "capture_timeout": "Voice subprocess timed out; check readiness and selected audio devices.",
    "speech_failed": "Reply generation finished, but speech failed. Check Piper voice assets and PipeWire playback.",
    "reasoning_failed": "Speech reached the assistant, but processing failed. Check model readiness, busy requests and runtime configuration.",
    "capture_failed": "Microphone or wake detection failed. Check the PipeWire input, Whisper model and wake configuration.",
}


class VoicePipelineError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def diagnostic(exc, phase):
    if isinstance(exc, VoicePipelineError):
        code = exc.code if exc.code in VOICE_MESSAGES else "capture_failed"
        return code, VOICE_MESSAGES[code]
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
