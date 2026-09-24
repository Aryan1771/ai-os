from __future__ import annotations

import json
import math
import tkinter as tk

from ai_os.config import load_config


SHAPES = {
    "core": ["....###....", "..#######..", ".#########.", "###########", "###########", "###########", ".#########.", "..#######..", "....###...."],
    "heart": ["..##...##..", ".####.####.", "###########", "###########", ".#########.", "..#######..", "...#####...", "....###....", ".....#....."],
    "music": [".......##..", ".......##..", ".......##..", "..#######..", "..##....##..", "..##....##..", "..##........", "..##........", ".###........"],
    "code": ["...........", "...##...##..", "..##.....##..", ".##.......##.", "##.........##", "##.........##", ".##.......##.", "..##.....##..", "...##...##.."],
    "idea": ["....###....", "..#######..", ".##.....##.", "##.......##", "##.......##", ".##.....##.", "..#######..", "....###....", "....###...."],
    "cloud": ["...........", "....###....", "..#######..", ".#########.", "###########", "###########", ".#########.", "...........", "..........."],
}

EMOTIONS = {
    "happy": "..##.....##..\n..##.....##..\n.............\n...#######...",
    "sad": "..##.....##..\n..##.....##..\n.............\n.....###.....",
    "curious": "..##.....##..\n..##.....##..\n.....#.......\n....#####....",
    "listening": "..##.....##..\n..##.....##..\n.............\n....#####....",
    "calm": "..##.....##..\n..##.....##..\n.............\n.....###.....",
}


def _target_points(shape: str, emotion: str, columns: int = 15, rows: int = 15) -> list[tuple[float, float]]:
    pattern = SHAPES.get(shape, SHAPES["core"])
    mask = [[char == "#" for char in line] for line in pattern]
    height, width = len(mask), max(len(line) for line in mask)
    points = [
        (x - (width - 1) / 2, y - (height - 1) / 2)
        for y, line in enumerate(mask)
        for x, filled in enumerate(line)
        if filled
    ]

    if shape in {"core", "idea"}:
        face = EMOTIONS.get(emotion, EMOTIONS["calm"]).splitlines()
        for y, line in enumerate(face):
            for x, filled in enumerate(line):
                if filled:
                    points.append((x - 6, y - 2))

    if len(points) > columns * rows:
        stride = len(points) / (columns * rows)
        points = [points[int(i * stride)] for i in range(columns * rows)]
    return points


class AvatarOverlay:
    """Pixel particle companion with spring-driven expression and subject morphs."""

    def __init__(self) -> None:
        self.config = load_config()
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.94)
        self.root.configure(bg="#101513")
        self.size = round(180 * self.config.avatar_scale / 100)
        self.canvas = tk.Canvas(self.root, width=self.size, height=self.size, bg="#101513", highlightthickness=0)
        self.canvas.pack()
        self.state_path = self.config.run_dir / "avatar_state.json"
        self.state = {"shape": "core", "emotion": "calm"}
        self.tick = 0
        self.points = _target_points("core", "calm")
        self.position = [[float(x), float(y), 0.0, 0.0] for x, y in self.points]
        self.items = [self.canvas.create_rectangle(0, 0, 0, 0, outline="", fill=self.config.avatar_accent) for _ in self.points]
        self.canvas.bind("<Button-1>", lambda _event: self._open_settings())
        self._place()
        self._animate()

    def _open_settings(self) -> None:
        import webbrowser

        webbrowser.open("http://127.0.0.1:8765")

    def _place(self) -> None:
        margin = 24
        self.root.update_idletasks()
        width, height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = margin if "left" in self.config.avatar_corner else width - self.size - margin
        y = margin if "top" in self.config.avatar_corner else height - self.size - margin
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")

    def _read_state(self) -> None:
        try:
            latest = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        shape = latest.get("shape", "core")
        emotion = latest.get("emotion", "calm")
        if shape == self.state.get("shape") and emotion == self.state.get("emotion"):
            return
        self.state = {"shape": shape, "emotion": emotion}
        points = _target_points(shape, emotion)
        self.points = points
        while len(self.position) < len(points):
            self.position.append([0.0, 0.0, 0.0, 0.0])
            self.items.append(self.canvas.create_rectangle(0, 0, 0, 0, outline="", fill=self.config.avatar_accent))
        for index, item in enumerate(self.items):
            self.canvas.itemconfigure(item, state="normal" if index < len(points) else "hidden")

    def _animate(self) -> None:
        self._read_state()
        unit = self.size / 20
        center = self.size / 2
        for index, item in enumerate(self.items):
            if index >= len(self.points):
                continue
            px, py, vx, vy = self.position[index]
            tx, ty = self.points[index]
            if self.config.avatar_animation_enabled:
                vx = (vx + (tx - px) * 0.16) * 0.78
                vy = (vy + (ty - py) * 0.16) * 0.78
                px += vx
                py += vy
            else:
                px, py = tx, ty
                vx = vy = 0
            self.position[index] = [px, py, vx, vy]
            pulse = 0.10 * math.sin(index * 0.9 + self.tick / 8)
            radius = max(2.5, unit * (0.34 + pulse))
            x = center + px * unit
            y = center + py * unit
            color = self.config.avatar_accent if index % 7 else "#f1bd73"
            self.canvas.coords(item, x - radius, y - radius, x + radius, y + radius)
            self.canvas.itemconfigure(item, fill=color)
        self.tick += 1
        self.root.after(30, self._animate)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    config = load_config()
    if config.avatar_enabled:
        AvatarOverlay().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
