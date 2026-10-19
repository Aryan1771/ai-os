from __future__ import annotations

import math
from dataclasses import dataclass

from ai_os.companion_state import validate_pixels

def _hologram_core() -> str:
    """Original segmented energy core; geometry is data, never a face or asset."""
    rows = []
    for y in range(-11, 12):
        row = []
        for x in range(-11, 12):
            radius = math.hypot(x, y)
            angle = math.atan2(y, x) % (2 * math.pi)
            quadrant = angle % (math.pi / 2)
            third = (angle + .23) % (2 * math.pi / 3)
            material = "."
            if 9.5 <= radius <= 10.6 and .12 < quadrant < 1.38:
                material = "#"
            elif 7.0 <= radius <= 7.8 and .12 < third < 1.86:
                material = "+"
            elif 4.3 <= radius <= 5.2:
                material = "#" if quadrant < .55 else "+"
            elif 5.8 < radius < 8.8 and abs(abs(x) - abs(y)) < .25:
                material = "o"
            elif radius < 2.4:
                material = "*" if radius < 1.2 else "+"
            if (abs(x) == 11 and y == 0) or (abs(y) == 11 and x == 0):
                material = "+"
            # A stable central lattice supports the speaking aperture without
            # spawning new particles or introducing cartoon facial features.
            if abs(y) <= 1 and abs(x) <= 3:
                material = "+" if y == 0 else "o"
            row.append(material)
        rows.append("".join(row))
    return "\n".join(rows)


# Each material remains a discrete particle while the same particles change targets.
FORMS = {
    "core": _hologram_core(),
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


def speech_mouth_frame(elapsed: float) -> int:
    """Bounded visual speech cadence, not audio amplitude or phoneme lip sync."""
    if not math.isfinite(elapsed) or elapsed < 0:
        return 0
    cadence = (0, 1, 2, 1, 0, 0, 1, 2, 2, 1, 0, 0)
    return cadence[int(elapsed / 0.12) % len(cadence)]


def target_pixels(shape: str, levels: dict[str, float], custom: list[str] | None = None,
                  *, mouth_open: int | None = None):
    validated = validate_pixels(custom)
    rows = validated or FORMS.get(shape, FORMS["core"]).strip().splitlines()
    grid = [list(row) for row in rows]
    if shape == "core" and not validated:
        # Mood changes the energy distribution, never the number of particles.
        if levels.get("concern", 0) > 55:
            grid[11][8:15] = list("o++*++o")
        elif levels.get("joy", 0) > 55:
            grid[11][8:15] = list("+*****+")
        elif levels.get("focus", 0) > 75:
            grid[11][8:15] = list("++***++")
        elif levels.get("energy", 45) < 25:
            grid[11][8:15] = list("ooo+ooo")
        elif levels.get("curiosity", 0) > 65:
            grid[11][8:15] = list("*++*++*")
        if mouth_open is not None:
            openness = max(0, min(2, int(mouth_open)))
            grid[11][8:15] = list(("o++*++o", "+*****+", "*******")[openness])
            grid[10][8:15] = grid[12][8:15] = list(
                ("ooooooo", "oo+++oo", "+*+*+*+")[openness]
            )
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
        self._geometry = None
        self._target_particles: list[Pixel] = []
        self.core_form = True
        self.orbit_elapsed = 0.0

    def set_form(self, shape: str, levels: dict[str, float], custom=None,
                 *, mouth_open: int | None = None) -> None:
        targets = target_pixels(shape, levels, custom, mouth_open=mouth_open)
        self.core_form = shape == "core" and validate_pixels(custom) is None
        signature = tuple(targets)
        if signature == self.signature:
            return
        self.signature = signature
        geometry = tuple((x, y) for x, y, _material in targets)
        if geometry == self._geometry:
            # Speech changes aperture energy, not geometry: keep the particle map
            # instead of doing a quadratic nearest-neighbor morph per syllable.
            for pixel, (_x, _y, material) in zip(self._target_particles, targets):
                pixel.material = material
            return
        self._geometry = geometry
        self._target_particles = []
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
                pixel = Pixel(0, 0, x, y, material, opacity=0)
                self.pixels.append(pixel)
            self._target_particles.append(pixel)
        for index in available:
            pixel = self.pixels[index]
            pixel.active = False
            pixel.tx, pixel.ty = pixel.x * 0.8, pixel.y * 0.8

    def advance(self, dt: float, motion: float = 0.65, animate: bool = True) -> None:
        dt = max(0, min(0.05, dt))
        self.elapsed += dt
        if animate and motion > 0:
            self.orbit_elapsed += dt * max(0, min(1, motion))
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
                target_x, target_y = pixel.tx, pixel.ty
                radius = math.hypot(target_x, target_y)
                if self.core_form and pixel.active and radius > 4.2 and motion > 0:
                    # Counter-rotating layers maintain the same particle objects.
                    # A model-provided pattern never enters this geometry path.
                    speed = .12 if radius > 9 else -.19 if radius > 6 else .25
                    angle = self.orbit_elapsed * speed
                    target_x, target_y = (target_x * math.cos(angle) - target_y * math.sin(angle),
                                          target_x * math.sin(angle) + target_y * math.cos(angle))
                pixel.vx += ((target_x + ripple - pixel.x) * 100 - pixel.vx * 14) * step
                pixel.vy += ((target_y + sway - pixel.y) * 100 - pixel.vy * 14) * step
                pixel.x += pixel.vx * step
                pixel.y += pixel.vy * step
                pixel.opacity += (float(pixel.active) - pixel.opacity) * min(1, step * 8)
