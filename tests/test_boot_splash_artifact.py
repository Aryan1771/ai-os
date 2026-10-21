"""Build artwork only in temporary directories; never inspect or alter host boot files."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import render_branding as render

ROOT = Path(__file__).resolve().parents[1]


def _python(*args):
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        shell=False, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20, check=False,
    )


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    pytest.importorskip("PySide6.QtSvg")
    parent = tmp_path_factory.mktemp("boot-artwork")
    before = (ROOT / render.WORDMARK).read_bytes()
    directories = [parent / "one", parent / "two"]
    for directory in directories:
        result = _python("scripts/render_branding.py", "--output", str(directory), "--boot-splash")
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [render.BOOT_NAME, render.MANIFEST_NAME]
    assert (ROOT / render.WORDMARK).read_bytes() == before
    return directories


def test_boot_bitmap_is_standard_uncompressed_24_bit_with_zero_row_padding(artifacts):
    data = (artifacts[0] / render.BOOT_NAME).read_bytes()
    assert struct.unpack_from("<2sIHHI", data) == (b"BM", 283954, 0, 0, 54)
    assert struct.unpack_from("<IiiHHIIiiII", data, 14) == (
        40, 566, 167, 1, 24, 0, 283900, 0, 0, 0, 0,
    )
    assert len(data) == 283954
    rows = [data[54 + y * 1700:54 + (y + 1) * 1700] for y in range(167)]
    assert all(row[-2:] == b"\0\0" for row in rows)
    assert all(row[:32 * 3] == b"\0" * (32 * 3) for row in rows)
    assert all(row[534 * 3:566 * 3] == b"\0" * (32 * 3) for row in rows)
    assert sum(any(row[x:x + 3]) for row in rows for x in range(0, 566 * 3, 3)) > 1000


def test_bitmap_encoder_preserves_bgr_bottom_up_rows_and_padding():
    pytest.importorskip("PySide6.QtGui")
    result = _python("-c", """
from PySide6.QtGui import QColor, QImage
from scripts.render_branding import _bmp24
image = QImage(3, 2, QImage.Format.Format_RGB888)
for y, row in enumerate((("red", "green", "blue"), ("cyan", "magenta", "yellow"))):
    for x, color in enumerate(row):
        image.setPixelColor(x, y, QColor(color))
print(_bmp24(image)[54:].hex())
""")
    assert result.returncode == 0, result.stderr
    # Bottom row first, each RGB pixel encoded as BGR, three zero padding bytes.
    assert bytes.fromhex(result.stdout.strip()) == bytes.fromhex(
        "ffff00 ff00ff 00ffff 000000 0000ff 008000 ff0000 000000"
    )


def test_artifacts_repeat_exactly_and_manifest_has_only_public_relative_metadata(artifacts):
    for name in (render.BOOT_NAME, render.MANIFEST_NAME):
        assert (artifacts[0] / name).read_bytes() == (artifacts[1] / name).read_bytes()
    raw = (artifacts[0] / render.MANIFEST_NAME).read_text()
    manifest = json.loads(raw)
    assert manifest["source"] == {
        "path": "branding/regenos-wordmark.svg",
        "sha256": hashlib.sha256((ROOT / render.WORDMARK).read_bytes()).hexdigest(),
    }
    output = manifest["output"]
    assert output["path"] == render.BOOT_NAME
    assert output["sha256"] == hashlib.sha256((artifacts[0] / render.BOOT_NAME).read_bytes()).hexdigest()
    assert output["wordmark_bounds"] == {"x": 32.5, "y": 0, "width": 501, "height": 167}
    assert output["bits_per_pixel"] == 24 and output["compression"] == "BI_RGB"
    assert manifest["boot_tested"] is False and manifest["product"] == "REgenOS"
    assert set(manifest["renderer"]) == {"pyside", "qt"}
    assert str(ROOT) not in raw and str(artifacts[0]) not in raw and "/home/" not in raw
    assert "timestamp" not in raw and "cmdline" not in raw
    assert {path.name for path in artifacts[0].iterdir()} == {render.BOOT_NAME, render.MANIFEST_NAME}
    if os.name == "posix":
        assert stat.S_IMODE(artifacts[0].stat().st_mode) == 0o700
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in artifacts[0].iterdir())


def test_default_cli_keeps_four_png_assets(tmp_path):
    pytest.importorskip("PySide6.QtSvg")
    output = tmp_path / "legacy-pngs"
    result = _python("scripts/render_branding.py", "--output", str(output))
    assert result.returncode == 0, result.stderr
    expected = {name: (width, height) for _, name, width, height in render.PNG_ASSETS}
    assert set(result.stdout.splitlines()) == set(expected)
    assert {path.name for path in output.iterdir()} == set(expected)
    for name, dimensions in expected.items():
        data = (output / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack_from(">II", data, 16) == dimensions


def test_staging_refuses_existing_files_before_writing_any_artifact(tmp_path):
    existing = tmp_path / "keep.txt"
    existing.write_bytes(b"OWNER CONTENT")
    with pytest.raises(ValueError, match="empty staging"):
        render._write_staging(tmp_path, {render.BOOT_NAME: b"new"})
    assert existing.read_bytes() == b"OWNER CONTENT"
    assert list(tmp_path.iterdir()) == [existing]


@pytest.mark.parametrize("where", ["output", "ancestor", "dangling_output"])
def test_staging_refuses_symlinks_without_writing_through_them(tmp_path, where):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real if where != "dangling_output" else tmp_path / "absent", target_is_directory=True)
    output = link / "stage" if where == "ancestor" else link
    with pytest.raises(ValueError, match="symlinks"):
        render._write_staging(output, {render.BOOT_NAME: b"new"})
    assert list(real.iterdir()) == [] and not (tmp_path / "absent").exists()


def test_empty_staging_is_supported_and_later_collision_never_overwrites(tmp_path):
    render._write_staging(tmp_path, {render.BOOT_NAME: b"first"})
    with pytest.raises(ValueError, match="empty staging"):
        render._write_staging(tmp_path, {render.BOOT_NAME: b"second", render.MANIFEST_NAME: b"later"})
    assert (tmp_path / render.BOOT_NAME).read_bytes() == b"first"
    assert not (tmp_path / render.MANIFEST_NAME).exists()


def test_artifact_names_cannot_escape_staging(tmp_path):
    with pytest.raises(ValueError, match="simple filenames"):
        render._write_staging(tmp_path / "stage", {"../outside": b"new"})
    assert not (tmp_path / "stage").exists() and not (tmp_path / "outside").exists()


@pytest.mark.parametrize("element", [
    '<text x="1" y="1">Needs a font</text>',
    '<image href="https://example.invalid/image.png"/>',
    '<path d="M0 0" fill="url(https://example.invalid/image.svg)"/>',
    '<path d="M0 0" fill="url(#local);url(https://example.invalid/image.svg)"/>',
    '<path d="M0 0" style="font-family:private"/>',
    '<script>untrusted()</script>',
    '<path d="M0 0" onload="untrusted()"/>',
])
def test_boot_vector_rejects_fonts_external_references_css_and_scripts(element):
    pytest.importorskip("PySide6.QtSvg")
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="144" height="48">' + element + '</svg>'
    result = _python("-c", """
import sys
from scripts import render_branding as render
render._source = lambda _: sys.argv[1].encode()
try:
    render._boot_payloads()
except ValueError:
    print("rejected")
else:
    raise SystemExit("Unsafe input was accepted")
""", svg)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "rejected"


def test_boot_vector_rejects_dtd_before_svg_loading_or_output():
    pytest.importorskip("PySide6.QtSvg")
    result = _python("-c", """
from scripts import render_branding as render
render._source = lambda _: b'<!DOCTYPE svg [<!ENTITY private "secret">]><svg/>'
try:
    render._boot_payloads()
except ValueError:
    print("rejected")
else:
    raise SystemExit("DTD was accepted")
""")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "rejected"


def test_cli_cannot_select_untracked_artwork(tmp_path):
    result = _python("scripts/render_branding.py", "--output", str(tmp_path / "stage"),
                     "--boot-splash", "--source", "/UNTRACKED/private.svg")
    assert result.returncode == 2 and not (tmp_path / "stage").exists()


def test_source_symlink_is_refused(tmp_path, monkeypatch):
    (tmp_path / "branding").mkdir()
    target = tmp_path / "outside.svg"
    target.write_text("<svg/>")
    (tmp_path / render.WORDMARK).symlink_to(target)
    monkeypatch.setattr(render, "REPO", tmp_path)
    with pytest.raises(ValueError, match="must not be a symlink"):
        render._source(render.WORDMARK)

