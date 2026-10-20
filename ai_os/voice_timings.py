"""Optional per-turn numeric measurements. Never log or persist voice timings."""
from __future__ import annotations

import math
import time

TIMING_KEYS = frozenset({
    "speech_detection_wait_seconds", "capture_seconds", "captured_audio_seconds",
    "ending_silence_audio_seconds", "speaker_filter_seconds", "stt_seconds",
    "synthesis_seconds", "playback_seconds", "capture_and_stt_seconds",
    "synthesis_and_playback_seconds", "model_seconds", "model_load_seconds",
    "model_prompt_eval_seconds", "model_eval_seconds", "total_seconds",
})
MAX_TIMING_SECONDS = 3600


def valid_seconds(value):
    return type(value) in {int, float} and 0 <= value <= MAX_TIMING_SECONDS and math.isfinite(value)


def public_timings(metrics):
    """Fixed numeric fields only, including when a worker failed partway through."""
    if type(metrics) is not dict:
        return {}
    return {key: round(value, 3) for key, value in metrics.items()
            if key in TIMING_KEYS and valid_seconds(value)}


def record_timing(metrics, key, seconds, *, accumulate=False):
    if type(metrics) is not dict or key not in TIMING_KEYS or not valid_seconds(seconds):
        return
    if accumulate:
        previous = metrics.get(key, 0)
        seconds += previous if valid_seconds(previous) else 0
    if valid_seconds(seconds):
        metrics[key] = round(seconds, 3)


def elapsed_timing(metrics, key, started, *, accumulate=False):
    if type(metrics) is dict and type(started) in {int, float}:
        record_timing(metrics, key, time.monotonic() - started, accumulate=accumulate)
