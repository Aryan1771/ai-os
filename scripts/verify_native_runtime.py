"""Show temporary native windows and make one synthetic local chat request.

Run from the checkout using the existing project venv in a graphical session.
Uses temporary settings and memory; never starts continuous listening.
"""

import json
import os
import tempfile
from pathlib import Path


def main():
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("This smoke check requires X11 or XWayland")
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    with tempfile.TemporaryDirectory(prefix="regenos-native-check-") as directory:
        os.environ["AI_OS_HOME"] = directory
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        from ai_os.avatar_overlay import AvatarOverlay
        from ai_os.native_settings import SettingsWindow

        home = Path(directory)
        (home / "config.json").write_text(json.dumps({
            "avatar_enabled": True, "always_listening_enabled": False,
            "wake_word_enabled": False, "speech_enabled": False,
            "hardware_auto_adapt": False, "memory_enabled": False,
        }))
        app = QApplication([])
        window = SettingsWindow(home, launch_companion=False)
        overlay = AvatarOverlay(home)
        window.show()
        outcome = {"ok": False}

        def finish():
            outcome.update(
                ok=window.conversation.status.text().startswith("Reply received"),
                pages=window.pages.count(), platform=app.platformName(),
                companion_visible=overlay.isVisible(),
            )
            window.conversation.cancel()
            overlay.close()
            window.close()
            app.quit()

        window.conversation.process.finished.connect(lambda *_: QTimer.singleShot(1000, finish))
        window.conversation.input.setPlainText("Reply with one short greeting.")
        QTimer.singleShot(500, window.conversation.send)
        QTimer.singleShot(120_000, finish)
        app.exec()
        print(json.dumps(outcome))
        return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
