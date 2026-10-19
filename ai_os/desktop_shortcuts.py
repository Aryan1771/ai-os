"""Reviewed GNOME custom shortcuts for fixed native REgenOS applications.

This is a same-user native settings helper, never a model tool or authentication
boundary. Proposals inspect only; apply/revert require explicit human confirmation.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import time
import uuid

from ai_os.config import AI_OS_HOME

MEDIA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM = MEDIA + ".custom-keybinding"
LIST_KEY = "custom-keybindings"
ROOT = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
SCHEMAS = ("org.gnome.desktop.wm.keybindings", "org.gnome.shell.keybindings",
           "org.gnome.mutter.keybindings", "org.gnome.mutter.wayland.keybindings", MEDIA)
TARGETS = (("settings", "REgenOS Settings", "a", "ai_os.hub_launcher", ()),
           ("chat", "REgenOS Chat", "c", "ai_os.quick_chat", ()),
           ("companion", "REgenOS Companion", "r", "ai_os.avatar_overlay", ("--show",)))
MAX_OUTPUT = 65536
MAX_PATHS = 128
ROLLBACK = ("Restore the previous REgenOS shortcut values from a private backup and remove only "
            "the paths this operation added. Preserve unrelated current shortcuts; refuse if "
            "REgenOS bindings were edited afterwards. GNOME's existing Super shortcuts stay unchanged.")


class ShortcutError(ValueError):
    """Fixed public error; never include raw GSettings output or custom commands."""


class Backend:
    def __init__(self):
        self.deadline = time.monotonic() + 12

    def run(self, *arguments):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ShortcutError("Shortcut inspection timed out; retry from the GNOME desktop.")
        try:
            result = subprocess.run(["/usr/bin/gsettings", *arguments],
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                    timeout=min(2, remaining), shell=False, check=False)
        except (OSError, subprocess.SubprocessError):
            raise ShortcutError("GNOME settings are unavailable or timed out. Run from the desktop session.") from None
        if result.returncode or len(result.stdout) > MAX_OUTPUT:
            raise ShortcutError("GNOME settings could not be inspected or changed. No raw settings output is displayed.")
        return result.stdout.strip()

    def get(self, schema, key, kind):
        return parse_variant(self.run("get", schema, key), kind)

    def set(self, schema, key, value):
        self.run("set", schema, key, repr(value))


def parse_variant(raw, kind):
    if not isinstance(raw, str) or len(raw) > MAX_OUTPUT:
        raise ShortcutError("GNOME returned an invalid or excessive shortcut value.")
    value = raw.strip()
    if value.startswith("@as "):
        value = value[4:]
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError, TypeError, RecursionError):
        raise ShortcutError("GNOME returned an unsupported shortcut value.") from None
    valid = (isinstance(parsed, str) and len(parsed) <= 8192 if kind is str
             else isinstance(parsed, list) and len(parsed) <= MAX_PATHS
             and all(isinstance(item, str) and len(item) <= 8192 for item in parsed))
    if not valid:
        raise ShortcutError("GNOME returned an invalid or excessive shortcut value.")
    return parsed


def _is_gnome():
    return "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":")


def _trusted_bindings(home):
    python = Path(sys.executable).absolute()
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ShortcutError("The current REgenOS Python interpreter is unavailable.")
    bindings = []
    for identifier, label, letter, module, extra in TARGETS:
        argv = ("/usr/bin/env", "AI_OS_HOME=" + str(Path(home).expanduser().absolute()),
                str(python), "-m", module, *extra)
        bindings.append({"id": identifier, "label": label, "accelerator": "<Super><Alt>" + letter,
                         "command": shlex.join(argv), "path": ROOT + "regenos-" + identifier + "/"})
    return bindings


def _accelerator(value):
    aliases = {"mod4": "super", "mod1": "alt", "control": "ctrl", "primary": "ctrl"}
    if not isinstance(value, str):
        return None
    modifiers = re.findall(r"<([^>]+)>", value)
    key = re.sub(r"<[^>]+>", "", value).casefold()
    if not modifiers and "+" in key:
        parts = key.split("+")
        modifiers, key = parts[:-1], parts[-1]
    return tuple(sorted({aliases.get(mod.casefold(), mod.casefold()) for mod in modifiers})), key


def _path(value):
    return (isinstance(value, str) and len(value) <= 512
            and re.fullmatch(r"/(?:[A-Za-z0-9_-]+/){1,24}", value) is not None)


def _snapshot(backend, bindings):
    available = set(backend.run("list-schemas").splitlines())
    if MEDIA not in available:
        raise ShortcutError("GNOME custom keyboard shortcuts are unavailable in this session.")
    paths = backend.get(MEDIA, LIST_KEY, list)
    if len(set(paths)) != len(paths) or not all(_path(path) for path in paths):
        raise ShortcutError("The existing custom shortcut list is unsupported; preserve it and inspect it manually.")
    builtin = []
    for schema in SCHEMAS:
        if schema not in available:
            continue
        for line in backend.run("list-recursively", schema).splitlines():
            parts = line.split(None, 2)
            if len(parts) != 3:
                raise ShortcutError("GNOME returned an invalid shortcut inventory.")
            _, key, raw = parts
            if key == LIST_KEY:
                continue
            try:
                values = parse_variant(raw, list if raw.startswith(("[", "@as")) else str)
            except ShortcutError:
                continue  # Numeric/toggle settings are not accelerators.
            builtin.extend((schema + ":" + key, value) for value in (values if isinstance(values, list) else [values]))
    custom = [(path, backend.get(CUSTOM + ":" + path, "binding", str)) for path in paths]
    owned = {binding["path"]: {key: backend.get(CUSTOM + ":" + binding["path"], key, str)
                                 for key in ("name", "binding", "command")} for binding in bindings}
    return {"paths": paths, "builtin": builtin, "custom": custom, "owned": owned}


def _revision(snapshot, bindings):
    return hashlib.sha256(json.dumps([snapshot, bindings], sort_keys=True).encode()).hexdigest()


def _proposal(home, backend):
    bindings = _trusted_bindings(home)
    snapshot = _snapshot(backend, bindings)
    conflicts = []
    desired_paths = {binding["path"] for binding in bindings}
    for binding in bindings:
        wanted = _accelerator(binding["accelerator"])
        builtin_conflict = any(_accelerator(value) == wanted for _, value in snapshot["builtin"])
        custom_conflict = any(path not in desired_paths and _accelerator(value) == wanted
                              for path, value in snapshot["custom"])
        previous = snapshot["owned"][binding["path"]]
        desired = {"name": binding["label"], "binding": binding["accelerator"], "command": binding["command"]}
        occupied = any(previous.values()) and previous != desired
        if builtin_conflict or custom_conflict or occupied:
            conflicts.append({"id": binding["id"], "accelerator": binding["accelerator"],
                              "reason": "An existing shortcut or reserved REgenOS path conflicts; it will not be overwritten."})
    applied = all(binding["path"] in snapshot["paths"] and snapshot["owned"][binding["path"]] == {
        "name": binding["label"], "binding": binding["accelerator"], "command": binding["command"]}
                  for binding in bindings)
    return ({"ok": not conflicts, "supported": True, "session": "GNOME", "bindings": bindings,
             "conflicts": conflicts, "custom_shortcut_count": len(snapshot["paths"]),
             "revision": _revision(snapshot, bindings), "already_applied": applied,
             "rollback": ROLLBACK, "scope": "GNOME custom bindings only; application/extension shortcuts may require physical verification."}, snapshot)


def propose_shortcuts(home=AI_OS_HOME):
    if not _is_gnome():
        return {"ok": False, "supported": False, "session": "other", "message": "These shortcuts require an active GNOME desktop; no settings were changed."}
    try:
        return _proposal(Path(home), Backend())[0]
    except (ShortcutError, OSError):
        return {"ok": False, "supported": True, "session": "GNOME", "message": "GNOME shortcut inventory is unavailable or unsupported. No settings were changed."}


def _private_directory(home):
    directory = Path(home) / "backups" / "desktop-shortcuts"
    for path in (Path(home), Path(home) / "backups", directory):
        if not path.exists() and not path.is_symlink():
            path.mkdir(mode=0o700)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or path.is_symlink():
            raise ShortcutError("The private shortcut backup directory is unavailable.")
    if directory.stat().st_mode & 0o077:
        raise ShortcutError("The shortcut backup directory must be private before applying changes.")
    return directory


@contextmanager
def _lock(home):
    import fcntl
    directory = _private_directory(home)
    descriptor = os.open(directory / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ShortcutError("The private shortcut lock is unavailable.")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ShortcutError("Another shortcut change is active; retry after it completes.") from None
        yield directory
    finally:
        os.close(descriptor)


def _write_backup(directory, snapshot, bindings):
    identifier = uuid.uuid4().hex
    target = directory / (identifier + ".json")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump({"version": 1, "previous_paths": snapshot["paths"], "previous": snapshot["owned"],
                   "bindings": bindings}, stream, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())
    return identifier


def _restore(backend, record, *, partial=False):
    bindings = record["bindings"]
    added = {binding["path"] for binding in bindings if binding["path"] not in record["previous_paths"]}
    for binding in bindings:
        schema = CUSTOM + ":" + binding["path"]
        previous = record["previous"][binding["path"]]
        desired = {"name": binding["label"], "binding": binding["accelerator"], "command": binding["command"]}
        current = {key: backend.get(schema, key, str) for key in previous}
        if any(current[key] != desired[key] and (not partial or current[key] != previous[key]) for key in previous):
            raise ShortcutError("REgenOS shortcuts changed after installation; rollback refused to preserve those edits.")
    current_paths = backend.get(MEDIA, LIST_KEY, list)
    if len(set(current_paths)) != len(current_paths) or not all(_path(path) for path in current_paths):
        raise ShortcutError("The current shortcut list is unsupported; no rollback was attempted.")
    if not partial and any(binding["path"] not in current_paths for binding in bindings):
        raise ShortcutError("REgenOS shortcut membership changed; rollback refused to preserve those edits.")
    restored_paths = [path for path in current_paths if path not in added]
    backend.set(MEDIA, LIST_KEY, restored_paths)
    for binding in bindings:
        schema = CUSTOM + ":" + binding["path"]
        for key, value in record["previous"][binding["path"]].items():
            backend.set(schema, key, value)
    if backend.get(MEDIA, LIST_KEY, list) != restored_paths:
        raise ShortcutError("Shortcut rollback readback did not match; keep the private backup for manual recovery.")
    for binding in bindings:
        schema = CUSTOM + ":" + binding["path"]
        if any(backend.get(schema, key, str) != value
               for key, value in record["previous"][binding["path"]].items()):
            raise ShortcutError("Shortcut rollback readback did not match; keep the private backup for manual recovery.")


def apply_shortcuts(proposal, home=AI_OS_HOME, *, human_confirmed=False):
    if human_confirmed is not True:
        return {"ok": False, "message": "Native human confirmation is required before changing shortcuts."}
    if not _is_gnome():
        return {"ok": False, "message": "An active GNOME desktop is required; no settings were changed."}
    try:
        with _lock(home) as directory:
            backend = Backend()
            current, snapshot = _proposal(home, backend)
            if (not isinstance(proposal, dict) or not current["ok"]
                    or proposal != current):
                return {"ok": False, "message": "Shortcut proposal changed or conflicts exist. Review a fresh proposal; no settings were changed."}
            if current["already_applied"]:
                return {"ok": True, "already_applied": True, "message": "The reviewed shortcuts are already installed; no values changed."}
            identifier = _write_backup(directory, snapshot, current["bindings"])
            record = {"previous_paths": snapshot["paths"], "previous": snapshot["owned"], "bindings": current["bindings"]}
            try:
                for binding in current["bindings"]:
                    schema = CUSTOM + ":" + binding["path"]
                    for key, value in (("name", binding["label"]), ("command", binding["command"]), ("binding", binding["accelerator"])):
                        backend.set(schema, key, value)
                # The native review cannot freeze GNOME's unrelated editors.
                # Never replace a custom-path list changed since the snapshot;
                # partial recovery merges against its current value instead.
                if backend.get(MEDIA, LIST_KEY, list) != snapshot["paths"]:
                    raise ShortcutError("The custom shortcut list changed during installation.")
                paths = snapshot["paths"] + [binding["path"] for binding in current["bindings"] if binding["path"] not in snapshot["paths"]]
                backend.set(MEDIA, LIST_KEY, paths)
                checked, _ = _proposal(home, Backend())
                if not checked["ok"] or not checked["already_applied"]:
                    raise ShortcutError("Shortcut readback did not match.")
            except (ShortcutError, OSError):
                try:
                    _restore(Backend(), record, partial=True)
                    rollback_ok = True
                except (ShortcutError, OSError):
                    rollback_ok = False
                return {"ok": False, "backup_id": identifier, "rollback_ok": rollback_ok,
                        "message": "Shortcut changes failed. Previous values were restored." if rollback_ok else "Shortcut changes failed and automatic recovery was incomplete. Keep the private backup and review desktop settings."}
            return {"ok": True, "backup_id": identifier, "message": "GNOME shortcut values passed readback. Verify the three shortcuts physically.", "rollback": ROLLBACK}
    except (ShortcutError, OSError):
        return {"ok": False, "message": "Shortcut changes could not start safely. No settings were changed."}


def revert_shortcuts(backup_id, home=AI_OS_HOME, *, human_confirmed=False):
    if human_confirmed is not True:
        return {"ok": False, "message": "Native human confirmation is required before reverting shortcuts."}
    if not _is_gnome() or not isinstance(backup_id, str) or re.fullmatch(r"[0-9a-f]{32}", backup_id) is None:
        return {"ok": False, "message": "A valid private backup and active GNOME desktop are required."}
    try:
        with _lock(home) as directory:
            descriptor = os.open(directory / (backup_id + ".json"), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 131072:
                    raise ShortcutError("The shortcut backup is not a valid private file.")
                record = json.load(stream)
            bindings = _trusted_bindings(home)
            if (not isinstance(record, dict) or record.get("version") != 1 or record.get("bindings") != bindings
                    or not isinstance(record.get("previous_paths"), list) or len(record["previous_paths"]) > MAX_PATHS
                    or not all(_path(path) for path in record["previous_paths"])
                    or set(record.get("previous", {})) != {binding["path"] for binding in bindings}):
                raise ShortcutError("The shortcut backup does not match these native applications.")
            for binding in bindings:
                previous = record["previous"][binding["path"]]
                desired = {"name": binding["label"], "command": binding["command"], "binding": binding["accelerator"]}
                if not isinstance(previous, dict) or set(previous) != set(desired) or previous not in (
                    {"name": "", "command": "", "binding": ""}, desired,
                ):
                    raise ShortcutError("The shortcut backup contains unsupported values.")
            _restore(Backend(), record)
        return {"ok": True, "message": "REgenOS shortcuts reverted; unrelated current shortcuts were preserved."}
    except (ShortcutError, OSError, ValueError, TypeError, KeyError):
        return {"ok": False, "message": "Rollback was unavailable or refused because REgenOS bindings changed. Preserve the backup and inspect desktop settings."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("propose", "apply", "revert"), required=True)
    parser.add_argument("--home", type=Path, default=AI_OS_HOME)
    args = parser.parse_args()
    if args.action == "propose":
        result = propose_shortcuts(args.home)
    else:
        try:
            raw = sys.stdin.buffer.read(32769)
            if len(raw) > 32768:
                raise ValueError
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError
            if args.action == "apply":
                result = apply_shortcuts(request.get("proposal"), args.home,
                                         human_confirmed=request.get("confirmed") is True)
            else:
                result = revert_shortcuts(request.get("backup_id"), args.home,
                                          human_confirmed=request.get("confirmed") is True)
        except (OSError, ValueError, TypeError):
            result = {"ok": False, "message": "Invalid bounded native shortcut request; no settings were changed."}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
