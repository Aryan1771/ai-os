"""Render the actual Qt widgets offscreen, without launching desktop services."""

import argparse
import os
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ai_os.avatar_overlay import AvatarOverlay
from ai_os.native_settings import SettingsWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/images"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication(["regenos-preview"])
    app.setStyle("Fusion")
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
    if os.name == "nt" and font.is_file():
        QFontDatabase.addApplicationFont(str(font))
    with tempfile.TemporaryDirectory(prefix="regenos-preview-") as directory:
        home = Path(directory)
        window = SettingsWindow(home, launch_companion=False)
        window.show()
        QTest.qWait(900)
        window.grab().save(str(args.output / "native-settings.png"))
        window.resize(780, 570)
        window.navigation.setCurrentRow(1)
        app.processEvents()
        window.grab().save(str(args.output / "native-settings-compact.png"))
        overlay = AvatarOverlay(home)
        QTest.qWait(900)
        overlay.grab().save(str(args.output / "native-companion.png"))
        overlay.timer.stop()
        overlay.close()
        window.close()


if __name__ == "__main__":
    main()
