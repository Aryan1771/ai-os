"""Rasterize tracked vector artwork into a separate staging directory; no host edits."""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication([])
    repo = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=True)
    for source, name, width, height in (
        ("branding/regenos-mark.svg", "regenos-mark.png", 512, 512),
        ("branding/regenos-wordmark.svg", "regenos-wordmark.png", 144, 48),
        ("branding/wallpapers/lockscreen.svg", "lockscreen.png", 1920, 1080),
        ("branding/wallpapers/default.svg", "fallback-wallpaper.png", 1920, 1080),
    ):
        target = args.output / name
        if target.exists() or target.is_symlink():
            parser.error(f"Refusing to overwrite {name}; select a new staging directory")
        renderer = QSvgRenderer(str(repo / source))
        if not renderer.isValid():
            raise RuntimeError(f"Invalid tracked vector: {source}")
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        if not image.save(str(target), "PNG"):
            raise RuntimeError(f"Could not save {name}")
        print(name)
    app.quit()


if __name__ == "__main__":
    main()
