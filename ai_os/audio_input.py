"""Trusted local microphone routing; discovery is metadata-only, never capture."""
from __future__ import annotations

import json
import os
import re
import selectors
import subprocess
import time
import unicodedata
from dataclasses import dataclass

from ai_os.services.voice_errors import VoicePipelineError

MAX_DUMP_BYTES = 4 * 1024 * 1024
MAX_DUMP_NODES = 4096
MAX_INPUTS = 128
DISCOVERY_SECONDS = 4
DUMP_PROGRAM = "/usr/bin/pw-dump"
DUMP_ARGUMENTS = ["--no-colors"]
_TARGET = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,254}", re.ASCII)
_FIXED_TARGET_PROPERTIES = json.dumps({
    "node.dont-fallback": True,
    "node.dont-reconnect": True,
    "node.dont-move": True,
}, separators=(",", ":"))


class AudioInputError(VoicePipelineError):
    """A public error without backend output, device text or private identifiers."""

    def __init__(self, message):
        super().__init__("input_unavailable", message)


@dataclass(frozen=True)
class InputDevice:
    target: str
    label: str


def validate_input_target(value: object) -> str:
    """Persist stable node names, never transient IDs, aliases or CLI syntax."""
    if value == "" and isinstance(value, str):
        return value
    if not isinstance(value, str) or not _TARGET.fullmatch(value) or value == "auto":
        raise ValueError("Choose the system default or a supported microphone from Refresh inputs.")
    return value


def _label(value: object) -> str:
    if not isinstance(value, str):
        return "Microphone input"
    # Node descriptions are untrusted peripheral text, displayed only locally.
    text = "".join(char for char in value[:512]
                   if not unicodedata.category(char).startswith("C"))
    return " ".join(text.split())[:160] or "Microphone input"


def parse_input_devices(payload: bytes | str) -> tuple[InputDevice, ...]:
    if not isinstance(payload, (bytes, str)):
        raise AudioInputError("Microphone input discovery returned an invalid response.")
    try:
        size = len(payload.encode("utf-8")) if isinstance(payload, str) else len(payload)
    except UnicodeError as exc:
        raise AudioInputError("Microphone input discovery returned an invalid response.") from exc
    if size > MAX_DUMP_BYTES:
        raise AudioInputError("Microphone input discovery exceeded its size limit.")
    try:
        nodes = json.loads(payload)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AudioInputError("Microphone input discovery returned an invalid response.") from exc
    if not isinstance(nodes, list) or len(nodes) > MAX_DUMP_NODES:
        raise AudioInputError("Microphone input discovery exceeded its node limit.")
    inputs = {}
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") != "PipeWire:Interface:Node":
            continue
        info = node.get("info")
        props = info.get("props") if isinstance(info, dict) else None
        if not isinstance(props, dict) or props.get("media.class") != "Audio/Source":
            continue
        try:
            target = validate_input_target(props.get("node.name"))
        except ValueError:
            continue
        if not target or target.endswith(".monitor") or props.get("stream.monitor") in (True, "true"):
            continue
        if target in inputs:
            raise AudioInputError("Microphone input names are ambiguous; discovery was not accepted.")
        inputs[target] = InputDevice(target, _label(props.get("node.description")))
        if len(inputs) > MAX_INPUTS:
            raise AudioInputError("Microphone input discovery exceeded its input limit.")
    return tuple(sorted(inputs.values(), key=lambda item: (item.label.casefold(), item.target)))


def _run_inventory() -> bytes:
    """One trusted child stays in its caller's group for voice-task cancellation."""
    argv = [DUMP_PROGRAM, *DUMP_ARGUMENTS]
    process = subprocess.Popen(argv, cwd="/", stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               shell=False, start_new_session=False, bufsize=0)
    output = bytearray()
    deadline = time.monotonic() + DISCOVERY_SECONDS
    try:
        if process.stdout is None:
            raise AudioInputError("Microphone input discovery did not provide a response.")
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, DISCOVERY_SECONDS)
                for key, _events in selector.select(min(.1, remaining)):
                    part = os.read(key.fileobj.fileno(), 4096)
                    if not part:
                        selector.unregister(key.fileobj)
                        continue
                    if len(output) + len(part) > MAX_DUMP_BYTES:
                        raise AudioInputError("Microphone input discovery exceeded its size limit.")
                    output.extend(part)
        process.wait(timeout=max(.01, deadline - time.monotonic()))
        if process.returncode:
            raise AudioInputError("Microphone input discovery failed. Check PipeWire and refresh inputs.")
        return bytes(output)
    finally:
        if process.poll() is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        process.wait(timeout=2)
        if process.stdout is not None:
            process.stdout.close()


def discover_input_devices() -> tuple[InputDevice, ...]:
    try:
        payload = _run_inventory()
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioInputError("Microphone input discovery is unavailable or timed out.") from exc
    return parse_input_devices(payload)


def recorder_arguments(target: str = "", *, sample_rate: int = 16000,
                       checked_inputs: tuple[InputDevice, ...] | None = None) -> list[str]:
    """Pin routing after discovery; native async callers pass their current scan."""
    try:
        target = validate_input_target(target)
    except ValueError as exc:
        raise AudioInputError("The saved microphone selection is invalid. Choose an input in Voice settings.") from exc
    if type(sample_rate) is not int or not 1 <= sample_rate <= 192000:
        raise ValueError("Invalid microphone sample rate.")
    args = ["--raw", "--format", "s16", "--rate", str(sample_rate), "--channels", "1"]
    if target:
        devices = discover_input_devices() if checked_inputs is None else checked_inputs
        if target not in {item.target for item in devices}:
            raise AudioInputError("The selected microphone is unavailable. Reconnect it or choose another input; no fallback was used.")
        args.extend(["--target", target, "--properties", _FIXED_TARGET_PROPERTIES])
    return [*args, "-"]
