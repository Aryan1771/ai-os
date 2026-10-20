"""Resolve REgenOS artwork in packaged installations and source checkouts."""
from pathlib import Path


def logo_path(preferred: str = "") -> Path:
    candidates = [
        Path(preferred) if preferred else Path("/usr/share/regenos/branding/regenos-mark.svg"),
        Path("/usr/share/regenos/branding/regenos-mark.svg"),
        Path(__file__).resolve().parents[1] / "branding/regenos-mark.svg",
    ]
    return next((path for path in candidates if path.is_file()), candidates[1])


def brand_icon(preferred: str = ""):
    from PySide6.QtGui import QIcon

    return QIcon(str(logo_path(preferred)))
