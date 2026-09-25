from __future__ import annotations

import math
from dataclasses import dataclass

from ai_os.companion_state import validate_pixels

# Each material remains a discrete pixel while the same particles change targets.
FORMS = {
    "core": """
..........**..........
..........**..........
.......########.......
.....############.....
....###++++++++###....
....##++++++++++##....
..####++oo++oo++####..
..####++oo++oo++####..
..####++++++++++####..
....##++++oo++++##....
....###++++++++###....
.....############.....
........######........
.....###******###.....
....####**++**####....
....####******####....
.....############.....
.......###..###.......
......####..####......
""",
    "heart": """
...####...####...
..######.######..
.###############.
.###############.
..#############..
...###########...
....#########....
.....#######.....
......#####......
.......###.......
........#........
""",
    "music": """
.......########..
.......########..
.......##....##..
.......##....##..
.......##....##..
.......##....##..
....#####.#####..
...######.#####..
...#####..####...
""",
    "code": """
....##....*....##....
...##....**.....##...
..##.....*.......##..
.##.....**........##.
..##....*........##..
...##..**.......##...
....##.*.......##....
""",
    "idea": """
......#####......
....#########....
...###+++++###...
..###+++++++###..
..##+++++++++##..
..##++++*++++##..
...##++***++##...
....##++*++##....
.....#######.....
......*****......
......*****......
.......***.......
""",
    "cloud": """
......#####........
....#########......
...############....
.################..
##################.
##################.
..##############...
....+....+....+....
...+....+....+.....
""",
    "gear": """
......####......
..##..####..##..
.##############.
..############..
...###....###...
######.**.######
######.**.######
...###....###...
..############..
.##############.
..##..####..##..
......####......
""",
    "shield": """
.......##.......
...##########...
.##############.
.###++++++++###.
.###+++++**+###.
..##++*+**++##..
..###++**++###..
...###++++###...
....########....
......####......
.......##.......
""",
    "folder": """
..######..........
.########.........
.################.
.################.
.##++++++++++++##.
.##++++++++++++##.
.##++++++++++++##.
.##++++++++++++##.
.################.
""",
    "chip": """
...#..#..#..#...
..############..
..##++++++++##..
####++****++####
..##++*oo*++##..
####++****++####
..##++++++++##..
..############..
...#..#..#..#...
""",
    "search": """
...######........
..########.......
.###....###......
.##......##......
.##......##......
.###....###......
..########.......
...######**......
.........***.....
..........***....
...........***...
""",
    "clock": """
....########....
..############..
.###+++*++++###.
.##++++*+++++##.
###++++*+++++###
###++++****++###
.##++++++++++##.
.###++++++++###.
..############..
....########....
""",
}


def target_pixels(shape: str, levels: dict[str, float], custom: list[str] | None = None):
    rows = validate_pixels(custom) or FORMS.get(shape, FORMS["core"]).strip().splitlines()
    grid = [list(row) for row in rows]
    if shape == "core" and not custom:
        # Face pixels are replaced in the lattice, not overpainted onto the body.
        if levels.get("concern", 0) > 55:
            grid[6][8:14] = list("o++++o")
            grid[9][9:13] = list("oooo")
        elif levels.get("joy", 0) > 55:
            grid[6][8:14] = list("oo++oo")
            grid[7][8:14] = list("++++++")
            grid[9][9:13] = list("oooo")
        elif levels.get("focus", 0) > 75:
            grid[7][8:14] = list("++++++")
        elif levels.get("energy", 45) < 25:
            grid[6][8:14] = list("++++++")
        elif levels.get("curiosity", 0) > 65:
            grid[6][8:14] = list("o+++oo")
            grid[9][9:13] = list("+oo+")
    width, height = max(map(len, grid)), len(grid)
    return [
        (x - (width - 1) / 2, y - (height - 1) / 2, cell)
        for y, row in enumerate(grid)
        for x, cell in enumerate(row)
        if cell != "."
    ]


@dataclass
class Pixel:
    x: float
    y: float
    tx: float
    ty: float
    material: str
    vx: float = 0
    vy: float = 0
    opacity: float = 1
    active: bool = True


class PixelEngine:
    """Damped springs plus a shared wave field produce a fluid-looking 2D morph."""

    def __init__(self) -> None:
        self.pixels: list[Pixel] = []
        self.elapsed = 0.0
        self.signature = None

    def set_form(self, shape: str, levels: dict[str, float], custom=None) -> None:
        targets = target_pixels(shape, levels, custom)
        signature = tuple(targets)
        if signature == self.signature:
            return
        self.signature = signature
        available = set(range(len(self.pixels)))
        for x, y, material in targets:
            if available:
                index = min(
                    available,
                    key=lambda i: (self.pixels[i].x - x) ** 2 + (self.pixels[i].y - y) ** 2,
                )
                available.remove(index)
                pixel = self.pixels[index]
                pixel.tx, pixel.ty, pixel.material, pixel.active = x, y, material, True
            else:
                self.pixels.append(Pixel(0, 0, x, y, material, opacity=0))
        for index in available:
            pixel = self.pixels[index]
            pixel.active = False
            pixel.tx, pixel.ty = pixel.x * 0.8, pixel.y * 0.8

    def advance(self, dt: float, motion: float = 0.65, animate: bool = True) -> None:
        dt = max(0, min(0.05, dt))
        self.elapsed += dt
        # Substeps keep spring integration stable after a delayed desktop frame.
        count = max(1, math.ceil(dt / 0.012))
        step = dt / count
        for _ in range(count):
            for pixel in self.pixels:
                if not animate:
                    pixel.x, pixel.y = pixel.tx, pixel.ty
                    pixel.vx = pixel.vy = 0
                    pixel.opacity = float(pixel.active)
                    continue
                ripple = math.sin(self.elapsed * 2.6 + pixel.ty * 0.3) * motion * 0.16
                sway = math.cos(self.elapsed * 2.0 + pixel.tx * 0.25) * motion * 0.12
                pixel.vx += ((pixel.tx + ripple - pixel.x) * 100 - pixel.vx * 14) * step
                pixel.vy += ((pixel.ty + sway - pixel.y) * 100 - pixel.vy * 14) * step
                pixel.x += pixel.vx * step
                pixel.y += pixel.vy * step
                pixel.opacity += (float(pixel.active) - pixel.opacity) * min(1, step * 8)
