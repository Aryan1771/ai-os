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
    | {"/etc/default/grub", "/etc/mkinitcpio.conf", "/proc/cmdline"}
)
PUBLIC_CONFIGS = ("/proc/cmdline", "/etc/default/grub", "/etc/mkinitcpio.conf")
MOUNT_TARGETS = ("/", *ROOTS)
IMAGE_PATHS = frozenset(root + "/" + name for root in
                        (*ROOTS, *(root + "/EFI/Linux" for root in ROOTS)) for name in IMAGE_NAMES)
PRESET_NAMES = frozenset({"default", "fallback", "recovery"})
MAX_MENU_ENTRIES = 64
UKI_PATH = "/boot/EFI/Linux/arch-linux.efi"


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
    except subprocess.TimeoutExpired:
        if process is not None:
            _kill(process)
        return None, "", "", "limit"
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
    allowed = {"/", "/EFI/Linux", *ROOTS, *(root + "/EFI/Linux" for root in ROOTS)}
    return value if parent in allowed else None


def _parse_config(text, images, classes):
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("menuentry ", "submenu ", "title ")):
            try:
                words = shlex.split(stripped, comments=True)
            except ValueError:
                words = []
            kind = _menu_class(words[1]) if len(words) > 1 else "unknown"
            if kind != "unknown":
                classes.add(kind)
        match = re.match(r"(?:linux(?:efi)?|initrd(?:efi)?|chainloader|efi)\s+(.+)$", stripped)
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


def _read_status(code, stderr, issue):
    if issue == "limit":
        return "budget_exhausted"
    if code == 0:
        return "readable"
    lower = stderr.lower()
    if "permission denied" in lower or "operation not permitted" in lower:
        return "permission_denied"
    if "no such file or directory" in lower:
        return "not_found"
    if "not a directory" in lower:
        return "not_directory"
    return "unavailable"


def _flags(tokens):
    return {"quiet": "quiet" in tokens, "splash": "splash" in tokens,
            "plymouth_disabled": any(token == "plymouth.enable=0" or
                                     token.startswith("disablehooks=") and
                                     "plymouth" in token.split("=", 1)[1].split(",")
                                     for token in tokens)}


def _cmdline(text):
    result = {"status": "unknown", "boot_image_present": False,
              "recognized_boot_image": None, "flags": None}
    try:
        tokens = shlex.split(text)
    except ValueError:
        return result
    images = [token.split("=", 1)[1] for token in tokens if token.startswith("BOOT_IMAGE=")]
    result.update(status="recognized", boot_image_present=bool(images),
                  recognized_boot_image=_safe_image(images[-1]) if images else None,
                  flags=_flags(tokens))
    return result


def _preset(path, text):
    """Interpret literal declarations only; never source/eval executable presets."""
    enabled, outputs, kernel, unknown = None, {}, None, False
    # Multiline literal PRESETS arrays are common. Other shell syntax is unknown.
    clean = []
    for line in text.splitlines():
        if not line.lstrip().startswith("#"):
            clean.append(line)
    body = "\n".join(clean)
    arrays = list(re.finditer(r"(?m)^\s*PRESETS\s*=\s*\(([^)]*)\)\s*(?:#[^\n]*)?$", body))
    declarations = re.findall(r"(?m)^\s*PRESETS\s*(?:\+?=)", body)
    if len(arrays) == 1 and len(declarations) == 1:
        try:
            values = shlex.split(arrays[0].group(1), comments=True)
        except ValueError:
            values = []
        if values and len(values) <= 8 and all(value in PRESET_NAMES for value in values):
            enabled = list(dict.fromkeys(values))
    if enabled is None:
        unknown = True
    if re.search(r"(?m)^\s*(?:PRESETS\s*\[|unset\s+PRESETS\b|declare\s|typeset\s)", body):
        enabled, unknown = None, True
    for line in clean:
        if re.match(r"\s*(?:source\s|\.\s|eval\s|if\s|for\s|while\s|case\s|until\s|function\s|\w+\s*\(\))", line):
            unknown = True
            enabled = None
        match = re.match(r"\s*(ALL_kver|(?:default|fallback|recovery)_(?:image|uki))\s*=\s*(.+)$", line)
        if not match:
            continue
        key = match.group(1)
        try:
            tokens = shlex.split(match.group(2), comments=True)
        except ValueError:
            tokens = []
        image = _safe_image(tokens[0]) if len(tokens) == 1 else None
        if image not in IMAGE_PATHS:
            unknown = True
            image = None
        if key == "ALL_kver":
            kernel = image
        else:
            name, kind = key.split("_", 1)
            outputs[key] = {"preset": name, "kind": "uki" if kind == "uki" else "initramfs",
                            "path": image}
    for output in outputs.values():
        output["enabled"] = output["preset"] in enabled if enabled is not None else None
    return {"path": path, "parse_status": "partial_or_custom" if unknown else "literal_declarations",
            "enabled_presets": enabled, "kernel_image": kernel,
            "outputs": list(outputs.values()), "bootability_verified": False}


def _grub_defaults(text):
    result = {"configured_default": {"kind": "unknown"}, "timeout_style": "unknown",
              "configured_flags": {}, "active_entry_verified": False}
    for line in text.splitlines():
        match = re.match(r"\s*(GRUB_DEFAULT|GRUB_TIMEOUT_STYLE|GRUB_CMDLINE_LINUX(?:_DEFAULT)?)\s*=\s*(.+)$", line)
        if not match:
            continue
        key = match.group(1)
        try:
            values = shlex.split(match.group(2), comments=True)
        except ValueError:
            continue
        if len(values) != 1:
            continue
        value = values[0]
        if key == "GRUB_DEFAULT":
            result["configured_default"] = ({"kind": "static_ordinal", "ordinal": value}
                if re.fullmatch(r"\d{1,3}(?:>\d{1,3}){0,7}", value) else
                {"kind": "saved" if value == "saved" else "custom"})
        elif key == "GRUB_TIMEOUT_STYLE":
            result["timeout_style"] = value if value in {"menu", "hidden", "countdown"} else "custom"
        else:
            try:
                result["configured_flags"][key] = _flags(shlex.split(value))
            except ValueError:
                pass
    return result


def _hooks(text):
    known = {"base", "udev", "systemd", "autodetect", "microcode", "modconf", "kms",
             "keyboard", "keymap", "consolefont", "block", "filesystems", "fsck", "plymouth",
             "sd-vconsole", "sd-encrypt", "encrypt", "lvm2", "mdadm_udev", "resume"}
    matches = list(re.finditer(r"(?m)^\s*HOOKS\s*=\s*\(([^)]*)\)\s*(?:#[^\n]*)?$", text))
    declarations = re.findall(r"(?m)^\s*HOOKS\s*\+?=", text)
    if len(matches) != 1 or len(declarations) != 1:
        return {"parse_status": "unknown_or_custom", "known_hooks": None}
    try:
        values = shlex.split(matches[0].group(1), comments=True)
    except ValueError:
        return {"parse_status": "unknown_or_custom", "known_hooks": None}
    unknown = sum(value not in known for value in values)
    return {"parse_status": "partial_or_custom" if unknown else "literal_declarations",
            "known_hooks": [value for value in values if value in known],
            "unknown_hook_count": unknown, "plymouth_present": "plymouth" in values}


def _mount(text, requested):
    result = {"requested": requested, "status": "unrecognized", "target": None,
              "fstype": None, "total_bytes": None, "available_bytes": None, "read_only": None}
    try:
        rows = json.loads(text)["filesystems"]
    except (ValueError, TypeError, KeyError):
        return result
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return result
    row = rows[0]
    result["target"] = row.get("target") if row.get("target") in MOUNT_TARGETS else "other"
    result["exact_mount"] = result["target"] == requested
    result["fstype"] = row.get("fstype") if row.get("fstype") in {
        "ext4", "btrfs", "vfat", "xfs", "f2fs", "ext2", "ext3", "tmpfs", "overlay", "squashfs"} else "other"
    for source, target in (("size", "total_bytes"), ("avail", "available_bytes")):
        value = row.get(source)
        if type(value) is int and 0 <= value <= 2**64 - 1:
            result[target] = value
        elif isinstance(value, str) and re.fullmatch(r"\d{1,20}", value) and int(value) <= 2**64 - 1:
            result[target] = int(value)
    options = str(row.get("options", "")).split(",")
    result["read_only"] = True if "ro" in options else False if "rw" in options else None
    result["status"] = "metadata_only"
    return result


def _reported_images(text):
    """Keep only exact known paths in current sections, never defaults or EFI IDs."""
    section, stub_known, evidence = None, False, []
    for line in text.splitlines():
        stripped = line.strip()
        if line and not line[0].isspace() and stripped.endswith(":"):
            section = stripped if stripped in {"Current Boot Loader:", "Current Stub:"} else None
        if section == "Current Stub:" and stripped.startswith("Product:"):
            stub_known = stripped.split(":", 1)[1].strip().startswith("systemd-stub ")
        stub_field = section == "Current Stub:" and stub_known and stripped.startswith(("Stub:", "File:"))
        loader_field = section == "Current Boot Loader:" and stripped.startswith(("Loader:", "File:"))
        if stub_field or loader_field:
            value = stripped.split(":", 1)[1].strip()
            for marker in ("└─", "├─", "`-", "|-"):
                value = value.removeprefix(marker).strip()
            for root in ROOTS:
                value = value.replace(root + "//EFI/", root + "/EFI/", 1)
            path = _safe_image(value)
            loaders = {"/EFI/GRUB/grubx64.efi", "/EFI/grub/grubx64.efi",
                       "/EFI/systemd/systemd-bootx64.efi", "/EFI/BOOT/BOOTX64.EFI"}
            loaders |= {root + item for root in ROOTS for item in tuple(loaders)}
            if (path and path.endswith(".efi")) or loader_field and value in loaders:
                evidence.append({"source": "bootctl_current_stub" if stub_field else "bootctl_current_loader",
                                 "path": path or value,
                                 "confidence": ("reported_current_stub_not_disk_verified" if stub_field else
                                                "reported_bootloader_executable_not_selected_kernel")})
    return evidence[:4]


def _brace_change(line):
    quote, escaped, change = None, False, 0
    for char in line:
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#":
            break
        elif char == "{":
            change += 1
        elif char == "}":
            change -= 1
    return change, quote is not None


def _menu_class(title):
    lowered = title.casefold()
    if "fallback" in lowered:
        return "fallback"
    if "recovery" in lowered:
        return "recovery"
    if any(word in lowered for word in ("arch", "linux", "regenos")):
        return "normal"
    return "unknown"


def _grub_entries(path, text, budget=None):
    """Bounded static declarations, never an interpreter or active-entry proof."""
    entries, frames, counts = [], [], {(): 0}
    depth, uncertain, truncated = 0, False, False
    function_depth = None
    conditional_depth = 0
    for line in text.splitlines():
        if budget is not None and time.monotonic() >= budget.deadline:
            truncated = True
            break
        stripped = line.strip()
        change, unclosed_quote = _brace_change(line)
        uncertain |= unclosed_quote
        if re.match(r"(?:function\s+\w+|\w+\s*\(\))\s*\{", stripped):
            function_depth = depth
        if re.match(r"(?:if|for|while|case|until)\b", stripped):
            conditional_depth += 1
        if re.match(r"(?:fi|done|esac)\b", stripped):
            conditional_depth = max(0, conditional_depth - 1)
        if re.match(r"(?:eval|configfile|source)\b", stripped):
            uncertain = True
        header = re.match(r"(menuentry|submenu)\s+(.+)$", stripped)
        if header:
            if conditional_depth or function_depth is not None or frames and frames[-1]["item"] is not None:
                uncertain = True
            if function_depth is None:
                try:
                    tokens = shlex.split(header.group(2), comments=True)
                except ValueError:
                    tokens = []
                if not tokens or "{" not in tokens or len(frames) >= 8:
                    uncertain = True
                else:
                    parent = tuple(frames[-1]["ordinal"]) if frames else ()
                    ordinal = parent + (counts.get(parent, 0),)
                    counts[parent] = ordinal[-1] + 1
                    counts[ordinal] = 0
                    item = {"ordinal": ">".join(map(str, ordinal)),
                            "ordinal_scope": "static_declarations_only", "class": _menu_class(tokens[0]),
                            "boot_form": "unknown", "images": [], "flags": None,
                            "custom_or_dynamic": bool(re.search(r"[$`]", tokens[0]))}
                    if header.group(1) == "menuentry":
                        if len(entries) >= MAX_MENU_ENTRIES:
                            truncated = True
                            break
                        entries.append(item)
                    if change > 0:
                        frames.append({"ordinal": ordinal, "base_depth": depth,
                                       "item": item if header.group(1) == "menuentry" else None})
                    elif header.group(1) == "menuentry" and re.search(r"\{\s*\S", stripped):
                        item["custom_or_dynamic"] = True
                        uncertain = True  # Inline command bodies are intentionally not interpreted.
        elif frames and frames[-1]["item"] is not None:
            item = frames[-1]["item"]
            command = re.match(r"(linux(?:efi)?|initrd(?:efi)?|chainloader|efi)\s+(.+)$", stripped)
            if command:
                try:
                    tokens = shlex.split(command.group(2), comments=True)
                except ValueError:
                    tokens = []
                name = command.group(1)
                candidates = tokens if name.startswith("initrd") else tokens[:1]
                images = [_safe_image(token) for token in candidates]
                if not candidates or any(image is None for image in images):
                    item["custom_or_dynamic"] = True
                if any(re.search(r"[$`]", token) for token in candidates):
                    item["custom_or_dynamic"] = True
                for image in images:
                    if image and image not in item["images"] and len(item["images"]) < 16:
                        item["images"].append(image)
                if name in {"chainloader", "efi"}:
                    item["boot_form"] = "chainloader"
                elif name.startswith("linux"):
                    item["boot_form"] = "linux_initrd"
                    item["flags"] = _flags(tokens[1:])
            elif re.match(r"(?:configfile|source|eval)\b", stripped):
                item["custom_or_dynamic"] = True
        depth += change
        if depth < 0:
            uncertain, depth = True, 0
        while frames and depth <= frames[-1]["base_depth"]:
            frames.pop()
        if function_depth is not None and depth <= function_depth:
            function_depth = None
    if frames or depth:
        uncertain = True
    return {"path": path, "entries": entries, "truncated": truncated,
            "ordinal_confidence": "unknown_custom_syntax" if uncertain else "static_declarations_only",
            "runtime_order_verified": False, "active_entry_verified": False}


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


def _image_metadata(path, text, status):
    row = {"path": path, "status": status, "kind": "unknown", "bytes": None,
           "bootability_verified": False}
    if text is None:
        return row
    parts = text.strip().split("|")
    if len(parts) != 2 or not re.fullmatch(r"\d{1,20}", parts[1]):
        row["status"] = "unrecognized_metadata"
        return row
    kinds = {"regular file": "regular", "regular empty file": "regular",
             "symbolic link": "symlink", "directory": "directory"}
    row["kind"] = kinds.get(parts[0], "other")
    row["bytes"] = int(parts[1]) if int(parts[1]) <= 2**64 - 1 else None
    return row


def _kernel_inspection(text, running_release):
    result = {"parse_status": "unrecognized", "image_type": None, "kernel_version": None,
              "running_version_matches": None, "os_family": "unknown",
              "embedded_cmdline_present": None, "embedded_flags": None,
              "booted_file_identity_verified": False}
    if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        return result
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or len(lines) > 8:
        return result
    values = {}
    for line in lines:
        match = re.fullmatch(r"(Kernel Type|Cmdline|Version|OS):(?: (.*))?", line)
        if not match or match[1] in values:
            return result
        values[match[1]] = match[2] or ""
    kind = values.get("Kernel Type")
    if kind not in {"uki", "addon", "pe", "unknown"}:
        return result
    version = values.get("Version")
    if version is not None and not re.fullmatch(r"[0-9][0-9A-Za-z.+_-]{0,100}", version):
        return result
    flags = None
    if "Cmdline" in values:
        try:
            flags = _flags(shlex.split(values["Cmdline"]))
        except ValueError:
            return result
    family = {"Arch Linux": "arch", "REgenOS": "regenos", "REgenOS Preview": "regenos"}.get(values.get("OS"), "unknown")
    result.update(parse_status="recognized_metadata", image_type=kind, kernel_version=version,
                  running_version_matches=version == running_release if version and running_release else None,
                  os_family=family, embedded_cmdline_present="Cmdline" in values,
                  embedded_flags=flags)
    return result


def _splash_headers(text):
    result = {"parse_status": "unrecognized", "present": None, "bytes": None,
              "rendering_verified": False}
    if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        return result
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    expected = re.escape(UKI_PATH) + r":\s+file format pei-x86-64"
    if (len(lines) not in {3, 5} or not re.fullmatch(expected, lines[0])
            or lines[1] != "Sections:"
            or not re.fullmatch(r"Idx\s+Name\s+Size\s+VMA\s+LMA\s+File off\s+Algn", lines[2])):
        return result
    if len(lines) == 3:
        result.update(parse_status="recognized_metadata", present=False)
        return result
    # A partial row or an unknown trailer is not evidence of absence. Accept only
    # the complete selected-section format; never export addresses or raw flags.
    flags = lines[4].split(", ")
    known_flags = {"CONTENTS", "ALLOC", "LOAD", "RELOC", "READONLY", "CODE", "DATA",
                   "ROM", "DEBUGGING", "NEVER_LOAD", "EXCLUDE", "SORT_ENTRIES", "LINK_ONCE_DISCARD"}
    if not flags or len(flags) != len(set(flags)) or any(flag not in known_flags for flag in flags):
        return result
    match = re.fullmatch(r"\d{1,3}\s+\.splash\s+([0-9a-fA-F]{1,8})\s+[0-9a-fA-F]{1,16}\s+"
                         r"[0-9a-fA-F]{1,16}\s+[0-9a-fA-F]{1,16}\s+2\*\*\d{1,2}", lines[3])
    if match:
        result.update(parse_status="recognized_metadata", present=True, bytes=int(match[1], 16))
    return result


def inspect_uki(*, sudo=False):
    """Opt-in metadata reads of exactly one fixed UKI; no extraction or rewriting."""
    budget = Budget(time.monotonic() + MAX_SECONDS)
    result = {"read_only": True, "mode": "uki", "image_path": UKI_PATH,
              "sudo_requested": sudo, "running_kernel_release": None, "checks": [],
              "kernel_inspection": _kernel_inspection("", None), "splash": _splash_headers(""),
              "active_entry_verified": False, "recovery_boot_verified": False}
    stopped = False

    def run(command, name, *, public=False):
        nonlocal stopped
        if stopped:
            return None
        elevated = sudo and not public
        argv = (["/usr/bin/sudo", "-n", "--"] if elevated else []) + command
        code, out, err, issue = _read_command(argv, budget)
        result["checks"].append({"check": name, "status": _read_status(code, err, issue)})
        failure = _sudo_failure(err) if elevated and code != 0 else None
        if failure:
            result.update(status="sudo_unavailable", sudo_reason=failure)
            stopped = True
        elif issue == "limit":
            result["status"] = "budget_exhausted"
            stopped = True
        return out if code == 0 and not issue else None

    release = run(["/usr/bin/uname", "-r"], "running_release", public=True)
    if release is not None and re.fullmatch(r"[0-9][0-9A-Za-z.+_-]{0,100}\n?", release):
        result["running_kernel_release"] = release.strip()
    kernel = run(["/usr/bin/bootctl", "--no-pager", "kernel-inspect", UKI_PATH], "kernel_metadata")
    if kernel is not None:
        result["kernel_inspection"] = _kernel_inspection(kernel, result["running_kernel_release"])
    headers = run(["/usr/bin/objdump", "--section-headers", "--section=.splash", "--", UKI_PATH], "splash_headers")
    if headers is not None:
        result["splash"] = _splash_headers(headers)
    complete = (result["kernel_inspection"]["parse_status"] == "recognized_metadata"
                and result["splash"]["parse_status"] == "recognized_metadata")
    result.setdefault("status", "metadata_inspected" if complete else "partial_inventory")
    return result


def inspect(*, sudo=False):
    budget = Budget(time.monotonic() + MAX_SECONDS)
    result = {"read_only": True, "sudo_requested": sudo, "loader_product": "unknown",
              "recognized_directories": [], "listed_images": [], "referenced_images": [],
              "menu_entry_classes": [], "fallback_images": [], "readable_presets": [],
              "read_statuses": [], "mounts": [], "presets": [], "grub_configs": [],
              "image_files": [], "running_kernel_release": None, "current_boot": {},
              "current_image_evidence": [], "active_entry": {"status": "unknown"},
              "recovery_boot_verified": False,
              "limitations": ["Only fixed recognized filenames are inspected; unknown/custom paths are omitted.",
                              "Static menu ordinals/defaults are not proof of the selected runtime entry.",
                              "Reported current stub paths are firmware reports, not on-disk identity or recovery proof."]}
    listed, referenced, classes, directories, presets = set(), set(), set(), set(), set()
    stopped, sudo_stopped = False, False

    def run(command, *, public=False, path=None, kind="check"):
        nonlocal stopped, sudo_stopped
        if stopped or sudo_stopped and not public:
            return None
        elevated = sudo and not public
        argv = (["/usr/bin/sudo", "-n", "--"] if elevated else []) + command
        code, out, err, issue = _read_command(argv, budget)
        status = _read_status(code, err, issue)
        if path is not None:
            result["read_statuses"].append({"path": path, "kind": kind, "status": status})
        sudo_failure = _sudo_failure(err) if elevated and code != 0 else None
        if sudo_failure:
            result["status"] = "sudo_unavailable"
            result["sudo_reason"] = sudo_failure
            sudo_stopped = True
        elif issue == "limit":
            result["status"] = "budget_exhausted"
            stopped = True
        return out if code == 0 else None

    release = run(["/usr/bin/uname", "-r"], public=True)
    if release is not None and re.fullmatch(r"[0-9][0-9A-Za-z.+_-]{0,100}\n?", release):
        result["running_kernel_release"] = release.strip()
    for target in MOUNT_TARGETS:
        text = run(["/usr/bin/findmnt", "--json", "--bytes", "--target", target,
                    "--output", "TARGET,FSTYPE,SIZE,AVAIL,OPTIONS"], public=True)
        if text is not None:
            result["mounts"].append(_mount(text, target))
        else:
            result["mounts"].append({"requested": target, "status": "unavailable"})
    for path in PUBLIC_CONFIGS:
        text = run(["/usr/bin/cat", "--", path], public=True, path=path, kind="public_config")
        if text is None:
            continue
        if path == "/proc/cmdline":
            result["current_boot"] = _cmdline(text)
        elif path == "/etc/default/grub":
            result["grub_defaults"] = _grub_defaults(text)
        else:
            result["initramfs_hooks"] = _hooks(text)
    for kernel in KERNELS:
        path = "/etc/mkinitcpio.d/" + kernel + ".preset"
        text = run(["/usr/bin/cat", "--", path], public=True, path=path, kind="preset")
        if text is not None:
            presets.add(path)
            parsed = _preset(path, text)
            result["presets"].append(parsed)
            if parsed["kernel_image"]:
                referenced.add(parsed["kernel_image"])
            referenced.update(item["path"] for item in parsed["outputs"] if item["path"])
    boot = run(["/usr/bin/bootctl", "--no-pager", "status"])
    if boot is not None:
        result["loader_product"] = _loader_product(boot)
        result["current_image_evidence"] = _reported_images(boot)
    result["bootctl_status"] = ("readable" if boot is not None else
                                "sudo_unavailable" if sudo_stopped else "unavailable")
    configs = {root + suffix for root in ROOTS for suffix in ("/grub/grub.cfg", "/loader/loader.conf")}
    for directory in DIRECTORIES:
        if stopped or sudo_stopped:
            break
        text = run(["/usr/bin/ls", "--color=never", "--file-type", "-1", "--", directory],
                   path=directory, kind="directory")
        if text is None:
            continue
        directories.add(directory)
        for name in text.splitlines():
            if name in IMAGE_NAMES and directory + "/" + name in IMAGE_PATHS:
                listed.add(directory + "/" + name)
            if name.endswith("/") and name[:-1] in KNOWN_DIRECTORIES:
                directories.add(directory + "/" + name[:-1])
            if directory.endswith("/loader/entries") and name in ENTRY_NAMES:
                configs.add(directory + "/" + name)
    for path in sorted(configs):
        if stopped or sudo_stopped:
            break
        if path not in CONFIG_FILES:
            continue
        text = run(["/usr/bin/cat", "--", path], path=path, kind="boot_config")
        if text is not None:
            _parse_config(text, referenced, classes)
            if path.endswith("/grub.cfg"):
                parsed = _grub_entries(path, text, budget)
                result["grub_configs"].append(parsed)
                referenced.update(image for entry in parsed["entries"] for image in entry["images"])
    candidates = (listed | referenced | {
        "/boot/vmlinuz-linux", "/boot/vmlinuz-linux-zen", "/boot/initramfs-linux.img",
        "/boot/initramfs-linux-zen.img", "/boot/EFI/Linux/arch-linux.efi",
        "/boot/EFI/Linux/arch-linux-fallback.efi"}) & IMAGE_PATHS
    for path in sorted(candidates):
        if stopped or sudo_stopped:
            break
        text = run(["/usr/bin/stat", "--format=%F|%s", "--", path], path=path, kind="image")
        status = result["read_statuses"][-1]["status"]
        result["image_files"].append(_image_metadata(path, text, status))
    fallback = [row["path"] for row in result["image_files"]
                if row["status"] == "readable" and row["kind"] == "regular" and row["bytes"]
                and "fallback" in PurePosixPath(row["path"]).name]
    result.update(recognized_directories=sorted(directories), listed_images=sorted(listed),
                  referenced_images=sorted(referenced), menu_entry_classes=sorted(classes),
                  fallback_images=sorted(fallback),
                  readable_presets=sorted(presets))
    result.setdefault("status", "partial_inventory")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sudo", action="store_true", help="Use only sudo -n; never request a password")
    parser.add_argument("--uki", action="store_true", help="Only inspect the fixed Arch UKI's sanitized metadata")
    args = parser.parse_args()
    try:
        result = inspect_uki(sudo=args.sudo) if args.uki else inspect(sudo=args.sudo)
    except Exception:
        result = {"read_only": True, "status": "inspection_unavailable",
                  "message": "Boot inspection could not complete. No boot settings were changed."}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
