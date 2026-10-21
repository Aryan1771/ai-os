"""Rasterize tracked vector artwork into a separate staging directory; no host edits."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import struct
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[1]
WORDMARK = "branding/regenos-wordmark.svg"
BOOT_NAME = "regenos-boot.bmp"
MANIFEST_NAME = "regenos-boot.manifest.json"
PNG_ASSETS = (
    ("branding/regenos-mark.svg", "regenos-mark.png", 512, 512),
    (WORDMARK, "regenos-wordmark.png", 144, 48),
    ("branding/wallpapers/lockscreen.svg", "lockscreen.png", 1920, 1080),
    ("branding/wallpapers/default.svg", "fallback-wallpaper.png", 1920, 1080),
)


def _bmp24(image):
    """Encode bottom-up, uncompressed BGR rows with deterministic zero padding."""
    from PySide6.QtGui import QImage

    image = image.convertToFormat(QImage.Format.Format_RGB888)
    width, height = image.width(), image.height()
    stride = (width * 3 + 3) & ~3
    if not width or not height or stride * height > 16 * 1024 * 1024:
        raise ValueError("Invalid boot bitmap dimensions")
    source = image.constBits()
    rows = []
    for y in range(height - 1, -1, -1):
        rgb = bytes(source[y * image.bytesPerLine():y * image.bytesPerLine() + width * 3])
        bgr = bytearray(width * 3)
        bgr[0::3], bgr[1::3], bgr[2::3] = rgb[2::3], rgb[1::3], rgb[0::3]
        rows.append(bytes(bgr) + b"\0" * (stride - width * 3))
    pixels = b"".join(rows)
    header = struct.pack("<2sIHHI", b"BM", 54 + len(pixels), 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(pixels), 0, 0, 0, 0)
    return header + dib + pixels


def _source(relative):
    path = REPO / relative
    if path.is_symlink():
        raise ValueError("Tracked artwork must not be a symlink")
    return path.read_bytes()


def _boot_payloads():
    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import QRectF, qVersion
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    source = _source(WORDMARK)
    # The boot artifact uses only the original outlines and local gradients.
    # Reject references/fonts rather than introducing a new runtime dependency.
    if len(source) > 65536 or b"<!" in source:
        # Ordinary XML comments are allowed; DTDs and entity declarations are not.
        cleaned = re.sub(rb"<!--[\s\S]*?-->", b"", source)
        if len(source) > 65536 or b"<!" in cleaned:
            raise ValueError("Boot artwork must be a small self-contained SVG")
    allowed = {"svg", "title", "desc", "defs", "linearGradient", "stop", "g", "path", "circle"}
    attributes = {"width", "height", "viewBox", "fill", "id", "x1", "y1", "x2", "y2",
                  "gradientUnits", "offset", "stop-color", "transform", "d", "stroke",
                  "stroke-width", "stroke-linecap", "stroke-linejoin", "opacity", "cx", "cy", "r"}
    root = ElementTree.fromstring(source)
    for node in root.iter():
        if (node.tag.removeprefix("{http://www.w3.org/2000/svg}") not in allowed
                or any(key not in attributes for key in node.attrib)
                or any("url(" in value.lower()
                       and not re.fullmatch(r"url\(#[A-Za-z_][A-Za-z0-9_.:-]*\)", value)
                       for value in node.attrib.values())):
            raise ValueError("Boot artwork must use local vector outlines only")
    renderer = QSvgRenderer(source)
    if not renderer.isValid():
        raise ValueError("Invalid tracked boot vector")
    image = QImage(566, 167, QImage.Format.Format_RGB888)
    image.fill(0)
    painter = QPainter(image)
    try:
        renderer.render(painter, QRectF(32.5, 0, 501, 167))
    finally:
        painter.end()
    bmp = _bmp24(image)
    manifest = {
        "schema": 1, "product": "REgenOS", "kind": "uki-splash-artwork",
        "source": {"path": WORDMARK, "sha256": hashlib.sha256(source).hexdigest()},
        "renderer": {"pyside": pyside_version, "qt": qVersion()},
        "output": {"path": BOOT_NAME, "sha256": hashlib.sha256(bmp).hexdigest(),
                   "bytes": len(bmp), "format": "BMP", "width": 566, "height": 167,
                   "bits_per_pixel": 24, "compression": "BI_RGB", "background": "#000000",
                   "wordmark_bounds": {"x": 32.5, "y": 0, "width": 501, "height": 167}},
        "boot_tested": False,
    }
    return {BOOT_NAME: bmp, MANIFEST_NAME: (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()}


def _png_payloads():
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    payloads = {}
    for source, name, width, height in PNG_ASSETS:
        renderer = QSvgRenderer(_source(source))
        if not renderer.isValid():
            raise ValueError(f"Invalid tracked vector: {source}")
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        try:
            renderer.render(painter)
        finally:
            painter.end()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise RuntimeError(f"Could not encode {name}")
        payloads[name] = bytes(buffer.data())
    return payloads


def _write_staging(output, payloads):
    if any(Path(name).name != name or name in {"", ".", ".."} for name in payloads):
        raise ValueError("Artifact names must be simple filenames")
    output = Path(os.path.abspath(output))
    for path in (output, *output.parents):
        if path.is_symlink():
            raise ValueError("Staging paths must not contain symlinks")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Select a new or empty staging directory; nothing was overwritten")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, data in payloads.items():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(output / name, flags, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "wb") as target:
            target.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--boot-splash", action="store_true",
                        help="Render only the boot BMP and manifest; default remains the four PNG assets")
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    existing_app = QGuiApplication.instance()
    app = existing_app or QGuiApplication([])
    try:
        payloads = _boot_payloads() if args.boot_splash else _png_payloads()
        _write_staging(args.output, payloads)
        for name in payloads:
            print(name)
    except (OSError, ValueError, ElementTree.ParseError) as error:
        parser.error(str(error))
    finally:
        if existing_app is None:
            app.quit()


if __name__ == "__main__":
    main()
