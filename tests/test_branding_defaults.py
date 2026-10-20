"""Branding defaults use disposable roots only; no host/dconf/service writes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import install_branding_defaults as branding


@pytest.fixture
def roots(tmp_path):
    root, repo = tmp_path / "target", tmp_path / "source"
    root.mkdir()
    repo.mkdir()
    for relative in set(branding.ART.values()) | set(branding.GDM_ART.values()):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "branding/regenos-wordmark.png":
            path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (144).to_bytes(4, "big") + (48).to_bytes(4, "big"))
        else:
            path.write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC_IMAGE" if path.suffix == ".png" else b'<svg xmlns="http://www.w3.org/2000/svg" width="144" height="48"/>')
    return root, repo


def install(root, repo, stage="desktop"):
    proposal = branding.plan(root, repo, stage)
    return branding.apply(root, repo, stage, expected_plan=proposal["plan_sha256"], human_confirmed=True)


def test_plan_reads_only_and_limits_scope_to_approved_art_and_unlocked_defaults(roots):
    root, repo = roots
    proposal = branding.plan(root, repo)
    assert list(root.iterdir()) == []
    assert len(proposal["plan_sha256"]) == 64
    paths = {entry["path"] for entry in proposal["files"]}
    assert paths <= branding.ALLOWED
    assert "etc/dconf/db/regenos.d/90-background" in paths
    assert not any("lock" in path for path in paths if path.startswith("etc/"))
    assert not any(any(word in path for word in ("os-release", "pam.d", "boot", "systemd")) for path in paths)
    assert proposal["after_review"] == ["dconf update"]


def test_apply_private_backup_manifest_and_exact_rollback_restore_contents_modes(roots):
    root, repo = roots
    old = root / "usr/share/regenos/branding/regenos-mark.svg"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"OLD_SYNTHETIC_BRAND")
    old.chmod(0o640)
    profile = root / "etc/dconf/profile/user"
    profile.parent.mkdir(parents=True)
    original = "# Owner profile\nuser-db:user\nsystem-db:local\n"
    profile.write_text(original)
    result = install(root, repo)
    backup = root / branding.BACKUPS / result["backup_id"]
    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["state"] == "applied"
    assert backup.stat().st_mode & 0o777 == 0o700
    assert (backup / "manifest.json").stat().st_mode & 0o777 == 0o600
    saved = backup / "files/usr/share/regenos/branding/regenos-mark.svg"
    assert saved.read_bytes() == b"OLD_SYNTHETIC_BRAND" and saved.stat().st_mode & 0o777 == 0o600
    assert profile.read_text() == "# Owner profile\nuser-db:user\nsystem-db:regenos\nsystem-db:local\n"
    branding.rollback(root, result["backup_id"], human_confirmed=True)
    assert old.read_bytes() == b"OLD_SYNTHETIC_BRAND" and old.stat().st_mode & 0o777 == 0o640
    assert profile.read_text() == original
    assert not (root / "usr/share/regenos/wallpapers/default.png").exists()


def test_stale_reviewed_plan_refuses_before_backup_or_target_writes(roots):
    root, repo = roots
    proposal = branding.plan(root, repo)
    source = repo / "branding/regenos-mark.svg"
    source.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><title>changed</title></svg>')
    with pytest.raises(branding.BrandingError, match="plan changed"):
        branding.apply(root, repo, expected_plan=proposal["plan_sha256"], human_confirmed=True)
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("kind", ["destination", "parent", "source"])
def test_plan_refuses_symlinks_without_following_or_modifying_them(roots, tmp_path, kind):
    root, repo = roots
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_bytes(b"DO_NOT_CHANGE")
    if kind == "destination":
        path = root / "usr/share/regenos/branding/regenos-mark.svg"
        path.parent.mkdir(parents=True)
        path.symlink_to(sentinel)
    elif kind == "parent":
        (root / "usr").symlink_to(outside, target_is_directory=True)
    else:
        path = repo / "branding/regenos-mark.svg"
        path.unlink()
        path.symlink_to(sentinel)
    with pytest.raises(branding.BrandingError, match="symlink"):
        branding.plan(root, repo)
    assert sentinel.read_bytes() == b"DO_NOT_CHANGE"
    assert not (root / branding.BACKUPS).exists()


@pytest.mark.parametrize("confirmed", [False, None, 1, "yes"])
def test_apply_requires_explicit_confirmation_even_for_temp_root(roots, confirmed):
    root, repo = roots
    proposal = branding.plan(root, repo)
    with pytest.raises(branding.BrandingError, match="confirmation"):
        branding.apply(root, repo, expected_plan=proposal["plan_sha256"], human_confirmed=confirmed)
    assert list(root.iterdir()) == []


def test_real_root_cannot_apply_as_non_root_before_any_write(monkeypatch):
    monkeypatch.setattr(branding.os, "geteuid", lambda: 1000)
    with pytest.raises(branding.BrandingError, match="UID 0"):
        branding.require_apply(Path("/"), True)


def test_gdm_is_separate_and_requires_reviewed_installed_logo(roots):
    root, repo = roots
    with pytest.raises(branding.BrandingError, match="desktop art stage"):
        branding.plan(root, repo, "gdm")
    desktop = install(root, repo)
    gdm = install(root, repo, "gdm")
    assert (root / "etc/dconf/db/gdm.d/90-regenos-logo").read_bytes() == branding.GDM_LOGO
    assert (root / "usr/share/regenos/branding/regenos-wordmark.png").is_file()
    assert (root / "etc/dconf/profile/gdm").read_text() == (
        "user-db:user\nsystem-db:gdm\nfile-db:/usr/share/gdm/greeter-dconf-defaults\n")
    with pytest.raises(branding.BrandingError, match="GDM logo stage"):
        branding.rollback(root, desktop["backup_id"], human_confirmed=True)
    branding.rollback(root, gdm["backup_id"], human_confirmed=True)
    branding.rollback(root, desktop["backup_id"], human_confirmed=True)
    assert not (root / "etc/dconf/profile/gdm").exists()
    assert not (root / "etc/dconf/db/regenos.d/90-background").exists()


def test_changed_file_blocks_entire_rollback_before_other_files_are_touched(roots):
    root, repo = roots
    result = install(root, repo)
    wallpaper = root / "usr/share/regenos/wallpapers/default.png"
    wallpaper.write_bytes(b"OWNER_LATER_ART_EDIT")
    other = root / "usr/share/regenos/branding/regenos-mark.svg"
    before = other.read_bytes()
    with pytest.raises(branding.BrandingError, match="changed later"):
        branding.rollback(root, result["backup_id"], human_confirmed=True)
    assert wallpaper.read_bytes() == b"OWNER_LATER_ART_EDIT" and other.read_bytes() == before


def test_profile_rollback_removes_only_owned_lines_and_preserves_concurrent_additions(roots):
    root, repo = roots
    profile = root / "etc/dconf/profile/user"
    profile.parent.mkdir(parents=True)
    profile.write_text("# Preserve comment\nuser-db:user\nsystem-db:local\n")
    result = install(root, repo)
    profile.write_text(profile.read_text() + "# Added later\nsystem-db:owner-new\n")
    branding.rollback(root, result["backup_id"], human_confirmed=True)
    assert profile.read_text() == "# Preserve comment\nuser-db:user\nsystem-db:local\n# Added later\nsystem-db:owner-new\n"


def test_new_profile_later_additions_refuse_rollback_without_invalidating_profile(roots):
    root, repo = roots
    result = install(root, repo)
    profile = root / "etc/dconf/profile/user"
    profile.write_text(profile.read_text() + "system-db:owner-new\n")
    before = profile.read_bytes()
    wallpaper = root / "usr/share/regenos/wallpapers/default.png"
    art = wallpaper.read_bytes()
    with pytest.raises(branding.BrandingError, match="newly created dconf profile changed"):
        branding.rollback(root, result["backup_id"], human_confirmed=True)
    assert profile.read_bytes() == before
    assert wallpaper.read_bytes() == art


def test_rollback_never_removes_preexisting_regenos_profile_line(roots):
    root, repo = roots
    profile = root / "etc/dconf/profile/user"
    profile.parent.mkdir(parents=True)
    original = "user-db:user\nsystem-db:regenos\nsystem-db:other\n"
    profile.write_text(original)
    result = install(root, repo)
    branding.rollback(root, result["backup_id"], human_confirmed=True)
    assert profile.read_text() == original


def test_changed_original_profile_or_duplicate_owned_line_refuses_rollback(roots):
    root, repo = roots
    profile = root / "etc/dconf/profile/user"
    profile.parent.mkdir(parents=True)
    profile.write_text("user-db:user\nsystem-db:local\n")
    result = install(root, repo)
    profile.write_text(profile.read_text().replace("system-db:local", "system-db:changed"))
    with pytest.raises(branding.BrandingError, match="Original dconf profile content changed"):
        branding.rollback(root, result["backup_id"], human_confirmed=True)


def test_late_write_failure_recovers_unchanged_files_from_private_backup(roots, monkeypatch):
    root, repo = roots
    old = root / "usr/share/regenos/branding/regenos-mark.svg"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"ORIGINAL")
    proposal = branding.plan(root, repo)
    write = branding.atomic_write
    injected = [False]

    def fail_one_target(path, *args, **kwargs):
        if path == root / "usr/share/regenos/wallpapers/default.png" and not injected[0]:
            injected[0] = True
            raise OSError("SYNTHETIC_IO_FAILURE")
        return write(path, *args, **kwargs)

    monkeypatch.setattr(branding, "atomic_write", fail_one_target)
    with pytest.raises(branding.BrandingError, match="did not complete"):
        branding.apply(root, repo, expected_plan=proposal["plan_sha256"], human_confirmed=True)
    assert old.read_bytes() == b"ORIGINAL"
    assert not (root / "usr/share/regenos/branding/regenos-mark.png").exists()
    manifest = next((root / branding.BACKUPS).glob("*/manifest.json"))
    assert json.loads(manifest.read_text())["state"] == "failed_recovered"


def test_backup_tampering_and_untrusted_manifest_paths_refuse_restore(roots):
    root, repo = roots
    path = root / "usr/share/regenos/branding/regenos-mark.svg"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"PREVIOUS")
    result = install(root, repo)
    backup = root / branding.BACKUPS / result["backup_id"]
    (backup / "files/usr/share/regenos/branding/regenos-mark.svg").write_bytes(b"TAMPERED")
    with pytest.raises(branding.BrandingError, match="checksum"):
        branding.rollback(root, result["backup_id"], human_confirmed=True)
    assert path.read_bytes() != b"TAMPERED"


def test_existing_profile_order_and_comments_are_preserved_without_locks(roots):
    root, repo = roots
    profile = root / "etc/dconf/profile/user"
    profile.parent.mkdir(parents=True)
    profile.write_text("# Heading\nuser-db:user\n# Existing priority\nsystem-db:owner\n")
    install(root, repo)
    assert profile.read_text() == "# Heading\nuser-db:user\nsystem-db:regenos\n# Existing priority\nsystem-db:owner\n"
    assert not (root / "etc/dconf/db/regenos.d/locks").exists()


def test_custom_profile_database_and_dconf_override_require_separate_review(roots, monkeypatch):
    root, repo = roots
    profile = root / "etc/dconf/profile/user"
    profile.parent.mkdir(parents=True)
    profile.write_text("user-db:custom\nsystem-db:owner\n")
    with pytest.raises(branding.BrandingError, match="first database"):
        branding.plan(root, repo)
    monkeypatch.setenv("DCONF_PROFILE", "custom")
    with pytest.raises(branding.BrandingError, match="DCONF_PROFILE"):
        branding.plan(root, repo)


@pytest.mark.parametrize("arguments", [["--apply"], ["--rollback", "a" * 32]])
def test_cli_write_actions_require_explicit_root_before_any_operation(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["install_branding_defaults.py", *arguments])
    monkeypatch.setattr(branding, "apply", lambda *a, **kw: pytest.fail("apply was reached"))
    monkeypatch.setattr(branding, "rollback", lambda *a, **kw: pytest.fail("rollback was reached"))
    with pytest.raises(SystemExit) as result:
        branding.main()
    assert result.value.code == 2


def test_cli_apply_requires_reviewed_digest_before_any_write(roots, monkeypatch):
    root, repo = roots
    monkeypatch.setattr(sys, "argv", ["install_branding_defaults.py", "--apply", "--root", str(root), "--repo", str(repo)])
    with pytest.raises(SystemExit) as result:
        branding.main()
    assert result.value.code == 2
    assert list(root.iterdir()) == []


@pytest.mark.parametrize('width,height', [(512,512),(1024,256),(192,192),(144,0),(0,48)])
def test_gdm_refuses_native_size_assets_that_can_obscure_password(roots,width,height):
    root,repo=roots
    install(root,repo)
    png=repo/'branding/regenos-wordmark.png'
    png.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'+width.to_bytes(4,'big')+height.to_bytes(4,'big'))
    with pytest.raises(branding.BrandingError,match='compact'):
        branding.plan(root,repo,'gdm')
    assert not (root/'etc/dconf/db/gdm.d/90-regenos-logo').exists()


def test_square_legacy_login_configuration_can_be_migrated_and_rolled_back(roots):
    root,repo=roots
    desktop=install(root,repo)
    key=root/'etc/dconf/db/gdm.d/90-regenos-logo'
    key.parent.mkdir(parents=True)
    key.write_bytes(branding.LEGACY_GDM_LOGO)
    before=key.read_bytes()
    with pytest.raises(branding.BrandingError,match='GDM logo stage'):
        branding.rollback(root,desktop['backup_id'],human_confirmed=True)
    repair=install(root,repo,'gdm')
    assert key.read_bytes()==branding.GDM_LOGO
    branding.rollback(root,repair['backup_id'],human_confirmed=True)
    assert key.read_bytes()==before
    assert not (root/'usr/share/regenos/branding/regenos-wordmark.png').exists()


@pytest.mark.parametrize('svg',[b'<svg/>',b'<svg width="512" height="512"/>',b'<svg width="nan" height="48"/>'])
def test_gdm_svg_requires_bounded_intrinsic_dimensions(roots,svg):
    root,repo=roots
    install(root,repo)
    (repo/'branding/regenos-wordmark.svg').write_bytes(svg)
    with pytest.raises(branding.BrandingError):
        branding.plan(root,repo,'gdm')
