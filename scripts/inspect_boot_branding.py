#!/usr/bin/env python3
"""Read-only, sanitized boot-branding inventory; never mount or alter boot files."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import PurePosixPath
import re
import selectors
import shlex
import signal
import subprocess
import time

MAX_BYTES = 1024 * 1024
MAX_SECONDS = 10.0
ROOTS = ("/boot", "/efi", "/boot/efi")
DIRECTORIES = tuple(dict.fromkeys(
    ROOTS + tuple(root + suffix for root in ROOTS for suffix in
                  ("/loader", "/loader/entries", "/grub", "/EFI", "/EFI/Linux"))
    + ("/etc/mkinitcpio.d",)
))
KERNELS = ("linux", "linux-zen", "linux-lts", "linux-hardened", "linux-rt", "linux-rt-lts")
ENTRY_NAMES = frozenset(
    name + suffix + ".conf" for name in ("arch", "arch-linux", "regenos", *KERNELS)
    for suffix in ("", "-fallback", "-recovery")
)
KNOWN_DIRECTORIES = frozenset({"grub", "loader", "entries", "EFI", "Linux", "BOOT", "systemd", "GRUB", "Microsoft"})
IMAGE_NAMES = frozenset(
    {"intel-ucode.img", "amd-ucode.img"}
    | {"vmlinuz-" + kernel for kernel in KERNELS}
    | {"initramfs-" + kernel + suffix + ".img" for kernel in KERNELS for suffix in ("", "-fallback", "-recovery")}
    | {name + suffix + ".efi" for name in ("arch-linux", "regenos", *KERNELS)
       for suffix in ("", "-fallback", "-recovery")}
)
CONFIG_FILES = frozenset(
    {root + "/grub/grub.cfg" for root in ROOTS}
    | {root + "/loader/loader.conf" for root in ROOTS}
    | {root + "/loader/entries/" + name for root in ROOTS for name in ENTRY_NAMES}
    | {"/etc/mkinitcpio.d/" + kernel + ".preset" for kernel in KERNELS}
)


@dataclass
class Budget:
    deadline: float
    remaining: int = MAX_BYTES


def _kill(process):
    if process.pid <= 1:
        return
    try:
        if os.getpgid(process.pid) == process.pid and process.pid != os.getpgrp():
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except (ProcessLookupError, PermissionError):
        pass


def _read_command(argv, budget):
    """Drain both streams with one global byte/time budget; never print raw output."""
    if time.monotonic() >= budget.deadline or budget.remaining <= 0:
        return None, "", "", "limit"
    process = None
    try:
        # Keep the caller's session/controlling TTY for sudo's terminal timestamp,
        # while giving cleanup an owned process group. setsid() would drop it.
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, shell=False, start_new_session=False,
                                   **({"process_group": 0} if os.name == "posix" else {}),
                                   env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        output = {"out": bytearray(), "err": bytearray()}
        with selectors.DefaultSelector() as selector:
            for stream, key in ((process.stdout, "out"), (process.stderr, "err")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, key)
            while selector.get_map():
                left = budget.deadline - time.monotonic()
                if left <= 0:
                    _kill(process)
                    return None, "", "", "limit"
                for key, _ in selector.select(min(left, 0.1)):
                    chunk = os.read(key.fileobj.fileno(), min(65536, budget.remaining + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    budget.remaining -= len(chunk)
                    if budget.remaining < 0:
                        _kill(process)
                        return None, "", "", "limit"
                    output[key.data].extend(chunk)
            code = process.wait(timeout=max(0.001, budget.deadline - time.monotonic()))
        return code, output["out"].decode("utf-8", "replace"), output["err"].decode("utf-8", "replace"), ""
    except (OSError, subprocess.SubprocessError):
        if process is not None:
            _kill(process)
        return None, "", "", "unavailable"
    finally:
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if stream:
                    stream.close()
            try:
                process.wait(timeout=0.2)
            except subprocess.SubprocessError:
                _kill(process)


def _safe_image(value):
    value = re.sub(r"^\([^\n)]{1,128}\)", "", value)
    path = PurePosixPath(value)
    if (not value.startswith("/") or ".." in path.parts or path.name not in IMAGE_NAMES
            or str(path) != value):
        return None
    parent = str(path.parent)
    allowed = {"/", *ROOTS, *(root + "/EFI/Linux" for root in ROOTS)}
    return value if parent in allowed else None


def _parse_config(text, images, classes):
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("menuentry ", "submenu ", "title ")):
            lower = stripped.lower()
            if "fallback" in lower:
                classes.add("fallback")
            elif "recovery" in lower:
                classes.add("recovery")
            elif any(name in lower for name in ("arch", "linux", "regenos")):
                classes.add("normal")
        match = re.match(r"(?:linux(?:efi)?|initrd(?:efi)?|efi)\s+(.+)$", stripped)
        preset = re.match(r"(?:default|fallback|recovery)_(?:image|uki)\s*=\s*(.+)$", stripped)
        if match or preset:
            try:
                values = shlex.split((match or preset).group(1))
            except ValueError:
                continue
            for token in values:
                image = _safe_image(token)
                if image:
                    images.add(image)


def _loader_product(text):
    current = False
    for line in text.splitlines():
        if line.strip() == "Current Boot Loader:":
            current = True
        elif current and line and not line[0].isspace():
            current = False
        if current and line.strip().startswith("Product:"):
            product = line.split(":", 1)[1].strip().lower()
            for marker, known in (("systemd-boot", "systemd-boot"), ("grub", "GRUB"),
                                  ("refind", "rEFInd"), ("limine", "Limine")):
                if marker in product:
                    return known
    return "unknown"


def _sudo_failure(stderr):
    """Categorize known C-locale failures without exposing arbitrary sudo output."""
    text = stderr.lower()
    groups = (
        ("authentication_required", ("a password is required", "authentication is required",
                                     "authentication failure", "a terminal is required",
                                     "no tty present", "no valid timestamp")),
        ("policy_denied", ("not allowed to execute", "not in the sudoers",
                           "not allowed to run sudo", "may not run sudo",
                           "not permitted to execute")),
        ("execution_unavailable", ("must be owned by uid 0", "must be setuid root",
                                   "effective uid is not 0", '"no new privileges" flag is set',
                                   "no new privileges flag is set", "unable to initialize policy plugin",
                                   "error initializing audit plugin", "no valid sudoers sources found")),
    )
    for category, markers in groups:
        if any(marker in text for marker in markers):
            return category
    return None


def inspect(*, sudo=False):
    budget = Budget(time.monotonic() + MAX_SECONDS)
    result = {"read_only": True, "sudo_requested": sudo, "loader_product": "unknown",
              "recognized_directories": [], "listed_images": [], "referenced_images": [],
              "menu_entry_classes": [], "fallback_images": [], "readable_presets": [],
              "limitations": ["Only fixed recognized filenames are inspected; unknown/custom paths are omitted.",
                              "Bootability, active kernel entry, free ESP space and recovery are not verified."]}
    listed, referenced, classes, directories, presets = set(), set(), set(), set(), set()
    stopped = False

    def run(command):
        nonlocal stopped
        if stopped:
            return None
        argv = (["/usr/bin/sudo", "-n", "--"] if sudo else []) + command
        code, out, err, issue = _read_command(argv, budget)
        sudo_failure = _sudo_failure(err) if sudo and code != 0 else None
        if sudo_failure:
            result["status"] = "sudo_unavailable"
            result["sudo_reason"] = sudo_failure
            stopped = True
        elif issue == "limit":
            result["status"] = "budget_exhausted"
            stopped = True
        return out if code == 0 else None

    boot = run(["/usr/bin/bootctl", "--no-pager", "status"])
    if boot is not None:
        result["loader_product"] = _loader_product(boot)
    configs = {root + suffix for root in ROOTS for suffix in ("/grub/grub.cfg", "/loader/loader.conf")}
    for directory in DIRECTORIES:
        if stopped:
            break
        text = run(["/usr/bin/ls", "--color=never", "--file-type", "-1", "--", directory])
        if text is None:
            continue
        directories.add(directory)
        for name in text.splitlines():
            if name in IMAGE_NAMES:
                listed.add(directory + "/" + name)
            if name.endswith("/") and name[:-1] in KNOWN_DIRECTORIES:
                directories.add(directory + "/" + name[:-1])
            if directory.endswith("/loader/entries") and name in ENTRY_NAMES:
                configs.add(directory + "/" + name)
            if directory == "/etc/mkinitcpio.d" and name in {kernel + ".preset" for kernel in KERNELS}:
                configs.add(directory + "/" + name)
    for path in sorted(configs):
        if stopped:
            break
        if path not in CONFIG_FILES:
            continue
        text = run(["/usr/bin/cat", "--", path])
        if text is not None:
            _parse_config(text, referenced, classes)
            if path.endswith(".preset"):
                presets.add(path)
    result.update(recognized_directories=sorted(directories), listed_images=sorted(listed),
                  referenced_images=sorted(referenced), menu_entry_classes=sorted(classes),
                  fallback_images=sorted(path for path in listed if "fallback" in PurePosixPath(path).name),
                  readable_presets=sorted(presets))
    result.setdefault("status", "partial_inventory")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sudo", action="store_true", help="Use only sudo -n; never request a password")
    args = parser.parse_args()
    try:
        result = inspect(sudo=args.sudo)
    except Exception:
        result = {"read_only": True, "status": "inspection_unavailable",
                  "message": "Boot inspection could not complete. No boot settings were changed."}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
