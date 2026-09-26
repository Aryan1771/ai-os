"""Build the author's Windows cursor artwork into a native Xcursor theme."""

from __future__ import annotations

import argparse
import configparser
import shutil
import struct
import tempfile
from io import StringIO
from pathlib import Path

THEME = "REgenOS-Cool"
ROLES = {
    "Cool_cursor.cur": ("left_ptr", "default", "arrow", "top_left_arrow"),
    "Cool_hand.cur": ("hand2", "pointer", "hand1", "pointing_hand"),
    "Cool_text.cur": ("xterm", "text", "ibeam"),
    "Cool_plus.cur": ("crosshair", "cross", "tcross", "cell"),
    "Cool_horizontal.cur": (
        "sb_h_double_arrow",
        "ew-resize",
        "e-resize",
        "w-resize",
        "col-resize",
        "h_double_arrow",
        "size_hor",
    ),
    "Cool_vertical.cur": (
        "sb_v_double_arrow",
        "ns-resize",
        "n-resize",
        "s-resize",
        "row-resize",
        "v_double_arrow",
        "size_ver",
    ),
    "Cool_rdiagonal.cur": (
        "size_bdiag",
        "nesw-resize",
        "ne-resize",
        "sw-resize",
        "fd_double_arrow",
        "bottom_left_corner",
        "top_right_corner",
    ),
    "Cool_ldiagonal.cur": (
        "size_fdiag",
        "nwse-resize",
        "nw-resize",
        "se-resize",
        "bd_double_arrow",
        "bottom_right_corner",
        "top_left_corner",
    ),
    "Cool_busy.ani": ("watch", "wait", "progress", "left_ptr_watch"),
    # Windows-specific roles are retained without assigning misleading Linux semantics.
    "Cool_Select.cur": ("question_arrow", "help", "whats_this", "left_ptr_help"),
    "Cool_Location.cur": ("regenos-location",),
    "Cool_Person.cur": ("regenos-person",),
}


def validate_xcursor(blob: bytes) -> None:
    """Reject truncated conversion output before publishing a theme."""
    if len(blob) < 16:
        raise ValueError("Truncated Xcursor header")
    magic, header, version, count = struct.unpack_from("<4sIII", blob)
    if magic != b"Xcur" or header != 16 or version != 0x10000 or not count:
        raise ValueError("Invalid Xcursor header")
    if count > (len(blob) - 16) // 12:
        raise ValueError("Truncated Xcursor table")
    images = 0
    for index in range(count):
        kind, size, offset = struct.unpack_from("<III", blob, 16 + index * 12)
        if kind != 0xFFFD0002:
            continue
        if offset < 16 + count * 12 or offset + 36 > len(blob):
            raise ValueError("Invalid Xcursor image offset")
        fields = struct.unpack_from("<9I", blob, offset)
        length, image_kind, nominal, _, width, height, hx, hy, _ = fields
        if (
            length != 36
            or image_kind != kind
            or nominal != size
            or not 0 < width <= 32767
            or not 0 < height <= 32767
            or hx >= width
            or hy >= height
            or offset + length + width * height * 4 > len(blob)
        ):
            raise ValueError("Invalid Xcursor image or hotspot")
        images += 1
    if not images:
        raise ValueError("Xcursor contains no images")


def convert_cursor(path: Path) -> bytes:
    # The established converter preserves ANI frame delays and CUR hotspots.
    from win2xcur.parser import open_blob
    from win2xcur.writer import to_x11

    return to_x11(open_blob(path.read_bytes()).frames)


def build_theme(source: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    missing = [name for name in ROLES if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing cursor artwork: " + ", ".join(missing))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cursor-build-", dir=output.parent) as temporary:
        stage = Path(temporary) / THEME
        cursors = stage / "cursors"
        cursors.mkdir(parents=True)
        for filename, names in ROLES.items():
            data = convert_cursor(source / filename)
            validate_xcursor(data)
            for name in names:
                (cursors / name).write_bytes(data)
        (stage / "index.theme").write_text(
            "[Icon Theme]\nName=REgenOS Cool\n"
            "Comment=Original REgenOS cursor artwork by Aryan\n"
            "Inherits=Adwaita\nExample=left_ptr\n",
            encoding="utf-8",
        )
        for filename in ("README.md", "LICENSE.txt"):
            if (source / filename).is_file():
                shutil.copy2(source / filename, stage / filename)
        stage.rename(output)


def write_backed_up(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + ".regenos-backup")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
    ) as handle:
        temporary = Path(handle.name)
        handle.write(contents)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_preferences(config_root: Path, data_root: Path | None, theme: str = THEME) -> None:
    if not theme or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- ." for c in theme
    ):
        raise ValueError("Invalid cursor theme name")
    for version in ("gtk-3.0", "gtk-4.0"):
        path = config_root / version / "settings.ini"
        parser = configparser.ConfigParser(interpolation=None)
        if path.exists():
            parser.read(path, encoding="utf-8")
        if not parser.has_section("Settings"):
            parser.add_section("Settings")
        parser.set("Settings", "gtk-cursor-theme-name", theme)
        parser.set("Settings", "gtk-cursor-theme-size", "32")
        buffer = StringIO()
        parser.write(buffer)
        write_backed_up(path, buffer.getvalue())
    if data_root is not None:
        write_backed_up(
            data_root / "icons/default/index.theme", f"[Icon Theme]\nInherits={theme}\n"
        )
    write_backed_up(
        config_root / "environment.d/60-regenos-cursor.conf",
        f'XCURSOR_THEME="{theme}"\nXCURSOR_SIZE=32\n',
    )
    write_backed_up(
        config_root / "hypr/regenos-cursor.conf",
        f"env = XCURSOR_THEME,{theme}\nenv = XCURSOR_SIZE,32\n"
        "cursor {\n    enable_hyprcursor = false\n}\n",
    )
    write_backed_up(
        config_root / "regenos/cursor.Xresources", f"Xcursor.theme: {theme}\nXcursor.size: 32\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        build_theme(args.source, args.output)
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(1, f"Cursor build failed: {exc}\n")
    print(f"Built {THEME}: {args.output}")


if __name__ == "__main__":
    main()
