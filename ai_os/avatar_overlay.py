from __future__ import annotations

import math
import webbrowser
from tkinter import Canvas, Tk

from ai_os.config import load_config


class AvatarOverlay:
    """Small, local desktop companion overlay; replace its drawing with final mascot art later."""

    def __init__(self) -> None:
        self.config = load_config()
        self.root = Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "#000001")
        size = round(112 * self.config.avatar_scale / 100)
        self.canvas = Canvas(self.root, width=size, height=size, bg="#000001", highlightthickness=0)
        self.canvas.pack()
        self.size = size
        self.tick = 0
        self.canvas.bind("<Button-1>", lambda _event: webbrowser.open("http://127.0.0.1:8765"))
        self._place()
        self._animate()

    def _place(self) -> None:
        margin = 28
        self.root.update_idletasks()
        width, height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = margin if "left" in self.config.avatar_corner else width - self.size - margin
        y = margin if "top" in self.config.avatar_corner else height - self.size - margin
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")

    def _animate(self) -> None:
        self.canvas.delete("all")
        center = self.size / 2
        bob = math.sin(self.tick / 12) * 4 if self.config.avatar_animation_enabled else 0
        scale = self.size / 112
        accent = self.config.avatar_accent
        self.canvas.create_oval(18 * scale, (20 + bob) * scale, 94 * scale, (96 + bob) * scale, fill="#13211f", outline=accent, width=max(2, round(3 * scale)))
        self.canvas.create_arc(25 * scale, (27 + bob) * scale, 87 * scale, (89 + bob) * scale, start=200, extent=140, style="arc", outline=accent, width=max(2, round(3 * scale)))
        eye_y = (52 + bob) * scale
        self.canvas.create_oval(38 * scale, eye_y, 47 * scale, (61 + bob) * scale, fill="#e9fff5", outline="")
        self.canvas.create_oval(65 * scale, eye_y, 74 * scale, (61 + bob) * scale, fill="#e9fff5", outline="")
        self.canvas.create_line(48 * scale, (76 + bob) * scale, 64 * scale, (76 + bob) * scale, fill=accent, width=max(2, round(2 * scale)))
        self.tick += 1
        self.root.after(60, self._animate)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    config = load_config()
    if not config.avatar_enabled:
        return 0
    AvatarOverlay().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
