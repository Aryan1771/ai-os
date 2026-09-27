"""Synthetic OCR check; --status reports live readiness without printing screen text."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from ai_os.config import AI_OS_HOME
from ai_os.screen_context import read_observation, Observation, socket_path


def synthetic_model_check(text):
    from ai_os.ai_os_core import ask_screen
    from ai_os.settings_store import save_settings
    with tempfile.TemporaryDirectory(prefix="regenos-screen-check-") as directory:
        home = Path(directory)
        save_settings({"screen_context_enabled": True, "memory_enabled": False},
                      home, human_confirmed=True)
        done = threading.Event()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            path = socket_path(home)
            server.bind(str(path))
            path.chmod(0o600)
            server.listen(2)
            server.settimeout(0.2)
            def serve():
                while not done.is_set():
                    try:
                        connection, _ = server.accept()
                    except TimeoutError:
                        continue
                    with connection:
                        observation = Observation()
                        observation.update(text)
                        connection.sendall(json.dumps(observation.snapshot()).encode())
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            try:
                answer = ask_screen("Which four-digit test number is on my screen?", home)
                return "4729" in answer
            finally:
                done.set()
                thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--model", action="store_true", help="Also test synthetic OCR through local Ollama; no real capture")
    args = parser.parse_args()
    if args.status:
        observation = read_observation(AI_OS_HOME)
        print(json.dumps({"fresh_observation": bool(observation),
                          "text_characters": len(observation.get("text", ""))}))
        return 0 if observation else 1
    app = QApplication([])
    image = QImage(1000, 240, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont("DejaVu Sans", 30))
    painter.drawText(40, 100, "REgenOS local screen test 4729")
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    result = subprocess.run(["tesseract", "stdin", "stdout", "-l", "eng", "--psm", "11"],
                            input=bytes(buffer.data()), capture_output=True, timeout=8, shell=False)
    passed = result.returncode == 0 and b"4729" in result.stdout and b"local screen test" in result.stdout
    print(json.dumps({"synthetic_ocr": passed, "platform": app.platformName()}))
    if passed and args.model:
        passed = synthetic_model_check(result.stdout.decode("utf-8", errors="replace"))
        print(json.dumps({"synthetic_screen_model": passed}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
