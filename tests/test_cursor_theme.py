import configparser
import struct
from pathlib import Path

import pytest

from ai_os import cursor_theme as theme


def sample_cursor(hotspot=0):
    return (
        struct.pack("<4sIII", b"Xcur", 16, 0x10000, 1)
        + struct.pack("<III", 0xFFFD0002, 32, 28)
        + struct.pack("<9I", 36, 0xFFFD0002, 32, 1, 1, 1, hotspot, 0, 80)
        + b"\xff" * 4
    )


def test_xcursor_validation():
    theme.validate_xcursor(sample_cursor())
    for blob in (b"", sample_cursor()[:-1], sample_cursor(1), b"FAIL" + sample_cursor()[4:]):
        with pytest.raises(ValueError):
            theme.validate_xcursor(blob)


def test_theme_build_preserves_data_and_all_aliases(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    for name in theme.ROLES:
        (source / name).write_bytes(b"fixture")
    (source / "README.md").write_text("Artist attribution", encoding="utf-8")
    monkeypatch.setattr(theme, "convert_cursor", lambda path: sample_cursor())
    output = tmp_path / theme.THEME
    theme.build_theme(source, output)
    for aliases in theme.ROLES.values():
        for alias in aliases:
            assert (output / "cursors" / alias).read_bytes() == sample_cursor()
    assert "Adwaita" in (output / "index.theme").read_text()
    assert (output / "README.md").read_text() == "Artist attribution"
    with pytest.raises(FileExistsError):
        theme.build_theme(source, output)


def test_failed_build_does_not_publish_partial_theme(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / theme.THEME
    with pytest.raises(FileNotFoundError):
        theme.build_theme(source, output)
    for name in theme.ROLES:
        (source / name).touch()
    monkeypatch.setattr(theme, "convert_cursor", lambda path: b"bad")
    with pytest.raises(ValueError):
        theme.build_theme(source, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".cursor-build-*"))


def test_preferences_preserve_other_keys_and_original_backup(tmp_path):
    config, data = tmp_path / "config", tmp_path / "data"
    gtk = config / "gtk-3.0/settings.ini"
    gtk.parent.mkdir(parents=True)
    original = "[Settings]\ngtk-font-name=Example 11\ngtk-cursor-theme-name=Old\n"
    gtk.write_text(original, encoding="utf-8")
    theme.apply_preferences(config, data)
    theme.apply_preferences(config, data)
    parsed = configparser.ConfigParser()
    parsed.read(gtk)
    assert parsed["Settings"]["gtk-font-name"] == "Example 11"
    assert parsed["Settings"]["gtk-cursor-theme-name"] == theme.THEME
    assert gtk.with_name("settings.ini.regenos-backup").read_text() == original
    assert theme.THEME in (data / "icons/default/index.theme").read_text()
    assert (config / "gtk-4.0/settings.ini").exists()
    assert "enable_hyprcursor = false" in (config / "hypr/regenos-cursor.conf").read_text()
    with pytest.raises(ValueError):
        theme.apply_preferences(config, data, "bad\nINJECT=1")


def test_real_pack_conversion_when_dependencies_available(tmp_path):
    try:
        import win2xcur.parser  # noqa: F401
    except ImportError:
        pytest.skip("Install win2xcur and ImageMagick to run real artwork conversion")
    source = Path(__file__).resolve().parents[1] / "Cool_cursor"
    output = tmp_path / theme.THEME
    theme.build_theme(source, output)
    from win2xcur.parser import open_blob

    for filename, aliases in theme.ROLES.items():
        original = open_blob((source / filename).read_bytes())
        converted = open_blob((output / "cursors" / aliases[0]).read_bytes())
        assert len(original.frames) == len(converted.frames)
        for before, after in zip(original.frames, converted.frames):
            assert abs(before.delay - after.delay) <= 0.0011
            assert len(before) == len(after)
            for a, b in zip(before, after):
                assert a.hotspot == b.hotspot
                assert (a.image.width, a.image.height) == (b.image.width, b.image.height)
