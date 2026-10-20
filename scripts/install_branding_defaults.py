"""Staged REgenOS art/dconf installer. Default is a read-only, hash-bound plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

BACKUPS = "var/lib/regenos/branding-backups"
BACKGROUND = (b"[org/gnome/desktop/background]\n"
              b"picture-uri='file:///usr/share/regenos/wallpapers/default.png'\n"
              b"picture-uri-dark='file:///usr/share/regenos/wallpapers/default.png'\n"
              b"picture-options='zoom'\n")
LEGACY_GDM_LOGO = b"[org/gnome/login-screen]\nlogo='/usr/share/regenos/branding/regenos-mark.png'\n"
GDM_LOGO = b"[org/gnome/login-screen]\nlogo='/usr/share/regenos/branding/regenos-wordmark.png'\n"
GDM_ART = {
    "usr/share/regenos/branding/regenos-wordmark.svg": "branding/regenos-wordmark.svg",
    "usr/share/regenos/branding/regenos-wordmark.png": "branding/regenos-wordmark.png",
}
ART = {
    "usr/share/regenos/branding/regenos-mark.svg": "branding/regenos-mark.svg",
    "usr/share/regenos/branding/regenos-mark.png": "branding/regenos-mark.png",
    "usr/share/regenos/wallpapers/default.png": "branding/wallpapers/default.png",
    "usr/share/regenos/wallpapers/lockscreen.svg": "branding/wallpapers/lockscreen.svg",
    "usr/share/icons/hicolor/scalable/apps/regenos.svg": "branding/regenos-mark.svg",
}
OPTIONAL_LOCK = "usr/share/regenos/wallpapers/lockscreen.png"
PROFILES = {"etc/dconf/profile/user", "etc/dconf/profile/gdm"}
ALLOWED = set(ART) | set(GDM_ART) | {OPTIONAL_LOCK, "etc/dconf/db/regenos.d/90-background",
                                  "etc/dconf/db/gdm.d/90-regenos-logo"} | PROFILES
LIMIT = 32 * 1024 * 1024


class BrandingError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_path(root, relative=""):
    root = Path(os.path.abspath(root))
    if not root.is_dir():
        raise BrandingError("The explicit target root must already be a directory.")
    for part in [*reversed(root.parents), root]:
        if part.is_symlink():
            raise BrandingError("A target-root symlink requires manual review.")
    target = root / relative
    current = root
    for component in Path(relative).parts:
        if component in {"..", "."} or Path(relative).is_absolute():
            raise BrandingError("Invalid relative branding path.")
        current = current / component
        if current.is_symlink():
            raise BrandingError("A branding destination symlink requires manual review.")
        if current != target and current.exists() and not current.is_dir():
            raise BrandingError("A branding parent is not a directory.")
    return target


def read_file(path, limit=LIMIT):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise BrandingError("A branding input is not a bounded regular file.")
    with path.open("rb") as handle:
        value = handle.read(limit + 1)
    if len(value) > limit:
        raise BrandingError("A branding input exceeded its size bound.")
    return value


def snapshot(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"kind": "absent"}
    value = read_file(path)
    return {"kind": "file", "sha256": digest(value), "mode": stat.S_IMODE(info.st_mode),
            "uid": info.st_uid, "gid": info.st_gid, "mtime_ns": info.st_mtime_ns,
            "size": info.st_size, "inode": info.st_ino, "device": info.st_dev}


def merge_profile(original, stage):
    text = original.decode("utf-8")
    lines, added = text.splitlines(keepends=True), []

    def active():
        return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]

    def add(line, after=None):
        if line in active():
            return
        index = len(lines) if after is None else next(i + 1 for i, value in enumerate(lines) if value.strip() == after)
        if index and not lines[index - 1].endswith(("\n", "\r")):
            lines[index - 1] += "\n"
        lines.insert(index, line + "\n")
        added.append(line)

    if active() and active()[0] != "user-db:user":
        raise BrandingError("The dconf profile's first database needs separate review.")
    add("user-db:user")
    if stage == "desktop":
        add("system-db:regenos", "user-db:user")
    else:
        add("system-db:gdm", "user-db:user")
        add("file-db:/usr/share/gdm/greeter-dconf-defaults")
    return "".join(lines).encode(), added


def source_asset(repo, relative):
    path = checked_path(repo, relative)
    value = read_file(path)
    if path.suffix == ".png" and not value.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BrandingError("A reviewed PNG asset is invalid.")
    if path.suffix == ".svg" and b"<svg" not in value[:4096]:
        raise BrandingError("A reviewed SVG asset is invalid.")
    return value


def compact_wordmark(repo):
    """GNOME 51 loads natural dimensions: never install a square/oversize greeter."""
    result = {target: source_asset(repo, source) for target, source in GDM_ART.items()}
    for target, content in result.items():
        if target.endswith(".png"):
            if len(content) < 24 or content[12:16] != b"IHDR":
                raise BrandingError("The login wordmark needs a valid bounded PNG header.")
            width, height = int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")
        else:
            try:
                attributes = ET.fromstring(content).attrib
                width, height = float(attributes["width"]), float(attributes["height"])
            except (ET.ParseError, KeyError, ValueError):
                raise BrandingError("The login SVG needs explicit compact intrinsic dimensions.") from None
        if not (64 <= width <= 192 and 16 <= height <= 64 and 2.95 <= width / height <= 3.05):
            raise BrandingError("The login wordmark must be compact (at most 192×64, approximately 3:1); square/oversize logos can obscure authentication.")
    return result


def payloads(root, repo, stage):
    result, additions = {}, {}
    if stage == "desktop":
        if os.environ.get("DCONF_PROFILE") not in {None, "", "user"}:
            raise BrandingError("A DCONF_PROFILE override requires separate review.")
        result.update({name: source_asset(repo, source) for name, source in ART.items()})
        optional = Path(repo) / "branding/wallpapers/lockscreen.png"
        if optional.exists() or optional.is_symlink():
            result[OPTIONAL_LOCK] = source_asset(repo, "branding/wallpapers/lockscreen.png")
        result["etc/dconf/db/regenos.d/90-background"] = BACKGROUND
        profile = "etc/dconf/profile/user"
    elif stage == "gdm":
        logo = checked_path(root, "usr/share/regenos/branding/regenos-mark.png")
        if not logo.exists() or digest(read_file(logo)) != digest(source_asset(repo, "branding/regenos-mark.png")):
            raise BrandingError("Install the reviewed desktop art stage before the GDM logo stage.")
        result.update(compact_wordmark(repo))
        result["etc/dconf/db/gdm.d/90-regenos-logo"] = GDM_LOGO
        profile = "etc/dconf/profile/gdm"
    else:
        raise BrandingError("Choose the desktop or gdm stage.")
    path = checked_path(root, profile)
    original = read_file(path, 65536) if path.exists() else b""
    result[profile], additions[profile] = merge_profile(original, stage)
    return result, additions


def plan(root, repo, stage="desktop"):
    root = Path(os.path.abspath(root))
    data, additions = payloads(root, repo, stage)
    entries = []
    for relative, content in data.items():
        previous = snapshot(checked_path(root, relative))
        entries.append({"path": relative, "previous": previous, "installed_sha256": digest(content),
                        "installed_size": len(content), "added_profile_lines": additions.get(relative, [])})
    result = {"version": 1, "root": str(root), "stage": stage, "files": entries,
              "after_review": ["dconf update"],
              "notes": "Unlocked defaults only. No user keys, services, packages, authentication, boot or disks are changed. GDM is not restarted."}
    result["plan_sha256"] = digest(json.dumps(result, sort_keys=True).encode())
    return result


def atomic_write(path, content, mode=0o644, metadata=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".regenos-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        if metadata and os.geteuid() == 0:
            os.chown(temporary, metadata["uid"], metadata["gid"])
        os.replace(temporary, path)
        if metadata:
            os.utime(path, ns=(metadata["mtime_ns"], metadata["mtime_ns"]))
    finally:
        Path(temporary).unlink(missing_ok=True)


def manifest_write(backup, value):
    atomic_write(backup / "manifest.json", json.dumps(value, indent=2, sort_keys=True).encode(), 0o600)


def require_apply(root, human_confirmed):
    if human_confirmed is not True:
        raise BrandingError("Explicit apply/rollback confirmation is required.")
    root = Path(os.path.abspath(root))
    checked_path(root)
    if root == Path("/") and os.geteuid() != 0:
        raise BrandingError("The real system root requires UID 0 and separately reviewed approval.")
    return root


def restore_entry(root, backup, entry):
    path = checked_path(root, entry["path"])
    previous = entry["previous"]
    if previous["kind"] == "absent":
        path.unlink(missing_ok=True)
    else:
        original = read_file(checked_path(backup, "files/" + entry["path"]))
        if digest(original) != previous["sha256"]:
            raise BrandingError("An original backup failed its recorded checksum.")
        atomic_write(path, original, previous["mode"], previous)


def apply(root, repo, stage="desktop", *, expected_plan, human_confirmed=False):
    root = require_apply(root, human_confirmed)
    proposal = plan(root, repo, stage)
    if proposal["plan_sha256"] != expected_plan:
        raise BrandingError("The reviewed plan changed; inspect a fresh plan before applying.")
    data, _additions = payloads(root, repo, stage)
    if any(digest(data[entry["path"]]) != entry["installed_sha256"] for entry in proposal["files"]):
        raise BrandingError("Source art changed during planning.")
    base = checked_path(root, BACKUPS)
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    base.chmod(0o700)
    identifier = uuid.uuid4().hex
    backup = base / identifier
    backup.mkdir(mode=0o700)
    manifest = {"version": 1, "backup_id": identifier, "root": str(root), "stage": stage,
                "state": "applying", "files": proposal["files"]}
    for entry in manifest["files"]:
        path = checked_path(root, entry["path"])
        if snapshot(path) != entry["previous"]:
            raise BrandingError("A target changed before backup; no branding files were installed.")
        if entry["previous"]["kind"] == "file":
            original = read_file(path)
            if digest(original) != entry["previous"]["sha256"]:
                raise BrandingError("A target changed during backup.")
            atomic_write(backup / "files" / entry["path"], original, 0o600)
    manifest_write(backup, manifest)
    written = []
    try:
        # Recheck every destination before the first write, then again individually.
        if any(snapshot(checked_path(root, item["path"])) != item["previous"] for item in manifest["files"]):
            raise BrandingError("A target changed after backup.")
        for entry in manifest["files"]:
            path = checked_path(root, entry["path"])
            if snapshot(path) != entry["previous"]:
                raise BrandingError("A target changed during installation.")
            atomic_write(path, data[entry["path"]])
            entry["installed"] = snapshot(path)
            written.append(entry)
            manifest_write(backup, manifest)
        manifest["state"] = "applied"
        manifest_write(backup, manifest)
    except BaseException:  # noqa: BLE001 - recover owned writes even when interrupted.
        recovered = True
        for entry in reversed(written):
            try:
                if snapshot(checked_path(root, entry["path"])) != entry["installed"]:
                    recovered = False
                    continue
                restore_entry(root, backup, entry)
            except (OSError, ValueError):
                recovered = False
        manifest["state"] = "failed_recovered" if recovered else "failed_needs_review"
        manifest_write(backup, manifest)
        raise BrandingError("Apply did not complete. Inspect the private backup and recovery state: " + identifier) from None
    return {"ok": True, "backup_id": identifier, "stage": stage,
            "next": "Review and run dconf update separately; do not restart GDM."}


def profile_without_additions(current, original, additions):
    text = current.decode("utf-8")
    lines = text.splitlines(keepends=True)
    for added in additions:
        matches = [index for index, line in enumerate(lines) if line.strip() == added]
        if len(matches) != 1:
            raise BrandingError("Added dconf profile lines changed; rollback needs manual review.")
        lines.pop(matches[0])
    remaining = "".join(lines)
    # Allow additions, but never overwrite changed/deleted original profile lines.
    iterator = iter(remaining.splitlines())
    if not all(any(candidate == line for candidate in iterator) for line in original.decode("utf-8").splitlines()):
        raise BrandingError("Original dconf profile content changed; rollback needs manual review.")
    return remaining.encode()


def rollback(root, identifier, *, human_confirmed=False):
    root = require_apply(root, human_confirmed)
    if not re.fullmatch(r"[a-f0-9]{32}", identifier):
        raise BrandingError("Use a recorded branding backup ID.")
    backup = checked_path(root, BACKUPS + "/" + identifier)
    manifest = json.loads(read_file(checked_path(backup, "manifest.json"), 262144))
    if (manifest.get("version") != 1 or manifest.get("backup_id") != identifier
            or manifest.get("root") != str(root) or not isinstance(manifest.get("files"), list)):
        raise BrandingError("The branding backup manifest is invalid for this root.")
    if manifest.get("state") in {"rolled_back", "failed_recovered"}:
        return {"ok": True, "backup_id": identifier, "state": manifest["state"]}
    if manifest.get("stage") == "desktop":
        gdm = checked_path(root, "etc/dconf/db/gdm.d/90-regenos-logo")
        if gdm.exists() and read_file(gdm, 65536) in {GDM_LOGO, LEGACY_GDM_LOGO}:
            raise BrandingError("Roll back the GDM logo stage before changing its installed art dependency.")
    restorations = []
    for entry in manifest["files"]:
        relative = entry.get("path")
        if relative not in ALLOWED or not isinstance(entry.get("installed"), dict):
            raise BrandingError("The backup contains an unsupported or incomplete operation.")
        path = checked_path(root, relative)
        current = snapshot(path)
        original = b""
        if entry["previous"]["kind"] == "file":
            original = read_file(checked_path(backup, "files/" + relative))
            if digest(original) != entry["previous"]["sha256"]:
                raise BrandingError("An original backup failed its recorded checksum.")
        if current == entry["installed"]:
            restorations.append((entry, current, None))
        elif (relative in PROFILES and current["kind"] == "file" and entry.get("added_profile_lines")
              and all(current[key] == entry["installed"][key] for key in ("mode", "uid", "gid"))):
            if entry["previous"]["kind"] == "absent":
                raise BrandingError("A newly created dconf profile changed later; rollback needs manual review.")
            remaining = profile_without_additions(read_file(path, 65536), original, entry["added_profile_lines"])
            restorations.append((entry, current, remaining))
        else:
            raise BrandingError("A branded file changed later; rollback refused before overwriting anything.")
    for entry, expected, remaining in restorations:
        path = checked_path(root, entry["path"])
        if snapshot(path) != expected:
            raise BrandingError("A target changed during rollback; stop and inspect the private backup.")
        if remaining is None:
            restore_entry(root, backup, entry)
        else:
            atomic_write(path, remaining, expected["mode"], expected)
    manifest["state"] = "rolled_back"
    manifest_write(backup, manifest)
    return {"ok": True, "backup_id": identifier, "state": "rolled_back",
            "next": "Review and run dconf update separately."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--plan", action="store_true")
    actions.add_argument("--apply", action="store_true")
    actions.add_argument("--rollback", metavar="BACKUP_ID")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--stage", choices=("desktop", "gdm"), default="desktop")
    parser.add_argument("--expected-plan", metavar="SHA256")
    args = parser.parse_args()
    if (args.apply or args.rollback) and args.root is None:
        parser.error("writes require an explicit --root")
    if args.apply and not args.expected_plan:
        parser.error("--apply requires the reviewed --expected-plan SHA256")
    try:
        if args.rollback:
            result = rollback(args.root, args.rollback, human_confirmed=True)
        elif args.apply:
            result = apply(args.root, args.repo, args.stage, expected_plan=args.expected_plan, human_confirmed=True)
        else:
            result = plan(args.root or Path("/"), args.repo, args.stage)
        print(json.dumps(result, indent=2))
        return 0
    except BrandingError as exc:
        print(json.dumps({"ok": False, "message": str(exc)}))
        return 1
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"ok": False, "message": "Branding operation was refused or failed. Inspect the selected root, reviewed plan and private backup; no service or boot change was attempted."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
