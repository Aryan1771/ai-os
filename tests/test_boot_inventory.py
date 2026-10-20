"""Boot inventory tests never execute privileged commands or inspect host boot files."""
from __future__ import annotations

import json
import os
import subprocess
import time

import pytest

from scripts import inspect_boot_branding as boot


def test_inventory_reports_only_recognized_metadata_and_fixed_commands(monkeypatch):
    calls = []
    private = "SYNTHETIC_PRIVATE_IDENTIFIER"

    def fake(argv, _budget):
        calls.append(argv)
        command = argv[3:] if argv[:3] == ["/usr/bin/sudo", "-n", "--"] else argv
        if command[0] == "/usr/bin/bootctl":
            return 0, f"System:\n Firmware: {private}\nCurrent Boot Loader:\n Product: systemd-boot 260\n UUID: {private}\n", "", ""
        if command[0] == "/usr/bin/stat":
            return ((0, "regular file|1024", "", "") if command[-1] == "/boot/initramfs-linux-fallback.img"
                    else (1, "", "No such file or directory", ""))
        path = command[-1]
        if command[0] == "/usr/bin/ls":
            listings = {"/boot": f"vmlinuz-linux\ninitramfs-linux.img\ninitramfs-linux-fallback.img\ngrub/\nloader/\n{private}\n",
                        "/boot/loader/entries": f"arch.conf\n{private}.conf\n",
                        "/etc/mkinitcpio.d": "linux.preset\n"}
            return (0, listings[path], "", "") if path in listings else (1, "", "Permission denied", "")
        if path.endswith("grub.cfg"):
            return 0, (f"menuentry 'Arch Linux {private}' {{\n linux /vmlinuz-linux root=UUID={private}\n"
                       " initrd /intel-ucode.img /initramfs-linux.img\n}\n"
                       "menuentry 'Arch Linux (fallback initramfs)' {}\n"
                       "menuentry 'Arch Linux recovery' {}\n"), "", ""
        if path.endswith("arch.conf"):
            return 0, f"title Arch Linux {private}\nlinux /vmlinuz-linux\noptions root=UUID={private}\n", "", ""
        if path.endswith("linux.preset"):
            return 0, f"default_image='/boot/initramfs-linux.img'\nALL_kver='{private}'\n", "", ""
        return 1, "", "Unavailable", ""

    monkeypatch.setattr(boot, "_read_command", fake)
    result = boot.inspect(sudo=True)
    encoded = json.dumps(result)
    assert private not in encoded and "UUID" not in encoded and "root=" not in encoded
    assert result["loader_product"] == "systemd-boot"
    assert result["menu_entry_classes"] == ["fallback", "normal", "recovery"]
    assert result["fallback_images"] == ["/boot/initramfs-linux-fallback.img"]
    assert "/vmlinuz-linux" in result["referenced_images"]
    assert result["readable_presets"] == ["/etc/mkinitcpio.d/linux.preset"]
    for argv in calls:
        elevated = argv[:3] == ["/usr/bin/sudo", "-n", "--"]
        command = argv[3:] if elevated else argv
        assert command[0] in {"/usr/bin/bootctl", "/usr/bin/ls", "/usr/bin/cat", "/usr/bin/stat", "/usr/bin/uname", "/usr/bin/findmnt"}
        if command[0] in {"/usr/bin/bootctl", "/usr/bin/ls", "/usr/bin/stat"}:
            assert elevated
        if command[0] == "/usr/bin/cat":
            assert command[1] == "--" and command[-1] in boot.CONFIG_FILES
            assert elevated is command[-1].startswith(("/boot/", "/efi/"))
        if command[0] == "/usr/bin/ls":
            assert command == ["/usr/bin/ls", "--color=never", "--file-type", "-1", "--", command[-1]]
            assert command[-1] in boot.DIRECTORIES
        if command[0] == "/usr/bin/stat":
            assert command == ["/usr/bin/stat", "--format=%F|%s", "--", command[-1]]
            assert command[-1] in boot.IMAGE_PATHS
        if command[0] == "/usr/bin/uname":
            assert command == ["/usr/bin/uname", "-r"] and not elevated
        if command[0] == "/usr/bin/findmnt":
            assert command == ["/usr/bin/findmnt", "--json", "--bytes", "--target", command[4],
                               "--output", "TARGET,FSTYPE,SIZE,AVAIL,OPTIONS"]
            assert command[4] in boot.MOUNT_TARGETS and not elevated


def test_sudo_password_failure_stops_once_without_raw_error(monkeypatch):
    calls = []

    def denied(argv, _budget):
        calls.append(argv)
        return 1, "", "sudo: a password is required; SYNTHETIC_PRIVATE_LOG", ""

    monkeypatch.setattr(boot, "_read_command", denied)
    result = boot.inspect(sudo=True)
    assert len([argv for argv in calls if argv[0] == "/usr/bin/sudo"]) == 1
    assert result["status"] == "sudo_unavailable"
    assert result["sudo_reason"] == "authentication_required"
    assert "SYNTHETIC_PRIVATE_LOG" not in json.dumps(result)


def test_default_never_uses_sudo_and_unreadable_paths_are_partial(monkeypatch):
    calls = []
    monkeypatch.setattr(boot, "_read_command", lambda argv, budget: calls.append(argv) or (1, "", "Permission denied", ""))
    result = boot.inspect()
    assert calls and all("sudo" not in " ".join(argv) for argv in calls)
    assert result["status"] == "partial_inventory" and result["listed_images"] == []


def test_global_budget_exhaustion_stops_commands(monkeypatch):
    calls = []
    monkeypatch.setattr(boot, "_read_command", lambda argv, budget: calls.append(argv) or (None, "", "", "limit"))
    assert boot.inspect()["status"] == "budget_exhausted"
    assert len(calls) == 1


@pytest.mark.parametrize("value", ["/etc/shadow", "/boot/../etc/vmlinuz-linux", "/boot/private/vmlinuz-linux",
                                    "/boot/SECRET.img", "relative/vmlinuz-linux", "/boot//vmlinuz-linux"])
def test_unrecognized_image_paths_are_not_reported(value):
    assert boot._safe_image(value) is None


def test_grub_device_prefix_is_removed_without_exposing_identifiers():
    assert boot._safe_image("(PRIVATE_DEVICE_ID)/vmlinuz-linux") == "/vmlinuz-linux"


def test_preset_references_do_not_claim_fallback_file_exists(monkeypatch):
    def fake(argv, _budget):
        if argv[0] == "/usr/bin/ls" and argv[-1] == "/etc/mkinitcpio.d":
            return 0, "linux.preset\n", "", ""
        if argv[0] == "/usr/bin/cat" and argv[-1].endswith("linux.preset"):
            return 0, "fallback_image='/boot/initramfs-linux-fallback.img'", "", ""
        return 1, "", "", ""
    monkeypatch.setattr(boot, "_read_command", fake)
    result = boot.inspect()
    assert result["referenced_images"] == ["/boot/initramfs-linux-fallback.img"]
    assert result["fallback_images"] == []


class FakeProcess:
    def __init__(self, out=b"", err=b"", **kwargs):
        self.pid = 23456789
        self.stdout = self.pipe(out)
        self.stderr = self.pipe(err)

    @staticmethod
    def pipe(content):
        read, write = os.pipe()
        os.write(write, content)
        os.close(write)
        return os.fdopen(read, "rb")

    def wait(self, timeout):
        return 0


def test_subprocess_keeps_terminal_session_with_owned_group_and_no_prompt(monkeypatch):
    calls = []
    def spawn(argv, **kwargs):
        calls.append((argv, kwargs))
        return FakeProcess(out=b"recognized output")
    monkeypatch.setattr(boot.subprocess, "Popen", spawn)
    result = boot._read_command(["/usr/bin/bootctl", "--no-pager", "status"], boot.Budget(time.monotonic() + 1))
    assert result == (0, "recognized output", "", "")
    options = calls[0][1]
    assert options["shell"] is False and options["start_new_session"] is False
    assert options["process_group"] == 0
    assert options["stdin"] == subprocess.DEVNULL
    assert options["env"] == {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}


def test_output_budget_kills_mock_child_and_withholds_partial_output(monkeypatch):
    process = FakeProcess(out=b"123456789")
    killed = []
    monkeypatch.setattr(boot.subprocess, "Popen", lambda *a, **kw: process)
    monkeypatch.setattr(boot, "_kill", lambda child: killed.append(child))
    assert boot._read_command(["/usr/bin/ls"], boot.Budget(time.monotonic() + 1, 8)) == (None, "", "", "limit")
    assert killed == [process]


def test_expired_budget_never_starts_a_process(monkeypatch):
    monkeypatch.setattr(boot.subprocess, "Popen", lambda *a, **kw: pytest.fail("Expired command started"))
    assert boot._read_command(["/usr/bin/cat"], boot.Budget(time.monotonic() - 1))[-1] == "limit"


def test_deadline_during_read_kills_mock_child(monkeypatch):
    process = FakeProcess()
    killed = []
    ticks = iter([0, 11])
    monkeypatch.setattr(boot.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(boot.subprocess, "Popen", lambda *a, **kw: process)
    monkeypatch.setattr(boot, "_kill", lambda child: killed.append(child))
    assert boot._read_command(["/usr/bin/bootctl"], boot.Budget(10)) == (None, "", "", "limit")
    assert killed == [process]


def test_symlink_or_directory_name_does_not_claim_available_fallback_image(monkeypatch):
    def fake(argv, _budget):
        if argv[0] == "/usr/bin/ls" and argv[-1] == "/boot":
            return 0, "initramfs-linux-fallback.img@\ninitramfs-linux-zen-fallback.img/\n", "", ""
        return 1, "", "", ""
    monkeypatch.setattr(boot, "_read_command", fake)
    result = boot.inspect()
    assert result["listed_images"] == [] and result["fallback_images"] == []


def test_main_internal_failure_has_fixed_public_message(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["inspect_boot_branding.py"])
    monkeypatch.setattr(boot, "inspect", lambda **kwargs: (_ for _ in ()).throw(ValueError("SYNTHETIC_PRIVATE_ERROR")))
    assert boot.main() == 0
    output = capsys.readouterr().out
    assert "SYNTHETIC_PRIVATE_ERROR" not in output
    assert json.loads(output)["status"] == "inspection_unavailable"


@pytest.mark.parametrize("message,category", [
    ("sudo: a password is required", "authentication_required"),
    ("sudo: a terminal is required to read the password", "authentication_required"),
    ("sudo: authentication failure", "authentication_required"),
    ("sudo: user is not in the sudoers file", "policy_denied"),
    ("Sorry, user is not allowed to execute this command", "policy_denied"),
    ("sudo: effective uid is not 0", "execution_unavailable"),
    ('sudo: The "no new privileges" flag is set', "execution_unavailable"),
    ("sudo: unable to resolve host SYNTHETIC_PRIVATE_HOST", None),
    ("bootctl: Permission denied", None),
])
def test_sudo_errors_have_precise_fixed_categories(message, category):
    assert boot._sudo_failure(message) == category


def test_sudo_warning_does_not_misclassify_command_failure_as_authentication(monkeypatch):
    calls = []
    def fake(argv, _budget):
        calls.append(argv)
        command = argv[3:] if argv[0] == "/usr/bin/sudo" else argv
        if command[0] == "/usr/bin/bootctl":
            return 1, "", "sudo: unable to resolve host SYNTHETIC_PRIVATE_HOST", ""
        return 1, "", "No such file or directory", ""
    monkeypatch.setattr(boot, "_read_command", fake)
    result = boot.inspect(sudo=True)
    assert len(calls) > 1 and result["status"] == "partial_inventory"
    assert "sudo_reason" not in result and "SYNTHETIC_PRIVATE_HOST" not in json.dumps(result)


@pytest.mark.parametrize("pid,actual_group,parent_group,expected_group,expected_single", [
    (23456789, 23456789, 42, 23456789, False),
    (23456789, 42, 42, None, True),
    (23456789, 23456789, 23456789, None, True),
    (0, 0, 42, None, False),
    (1, 1, 42, None, False),
])
def test_cleanup_only_signals_verified_owned_group(monkeypatch, pid, actual_group, parent_group, expected_group, expected_single):
    groups, singles = [], []
    process = type("MockOwnedChild", (), {"pid": pid, "kill": lambda self: singles.append(True)})()
    monkeypatch.setattr(boot.os, "getpgid", lambda child_pid: actual_group)
    monkeypatch.setattr(boot.os, "getpgrp", lambda: parent_group)
    monkeypatch.setattr(boot.os, "killpg", lambda group, sig: groups.append((group, sig)))
    boot._kill(process)
    assert groups == ([(expected_group, boot.signal.SIGKILL)] if expected_group is not None else [])
    assert bool(singles) is expected_single


@pytest.mark.parametrize("error,expected", [
    ("cat: /boot/grub/grub.cfg: Permission denied", "permission_denied"),
    ("cat: /boot/grub/grub.cfg: No such file or directory", "not_found"),
    ("cat: /boot/grub/grub.cfg: Not a directory", "not_directory"),
    ("SYNTHETIC_PRIVATE_RAW_ERROR", "unavailable"),
])
def test_read_failures_are_distinct_public_categories(error, expected):
    assert boot._read_status(1, error, "") == expected
    assert boot._read_status(None, error, "limit") == "budget_exhausted"


def test_enabled_preset_outputs_are_separate_from_inactive_fallback():
    parsed = boot._preset("/etc/mkinitcpio.d/linux.preset", """
PRESETS=('default')
ALL_kver='/boot/vmlinuz-linux'
default_uki='/boot/EFI/Linux/arch-linux.efi'
fallback_uki='/boot/EFI/Linux/arch-linux-fallback.efi'
""")
    assert parsed["enabled_presets"] == ["default"]
    assert parsed["kernel_image"] == "/boot/vmlinuz-linux"
    assert [(item["preset"], item["enabled"]) for item in parsed["outputs"]] == [("default", True), ("fallback", False)]
    assert parsed["bootability_verified"] is False


def test_multiline_presets_and_comments_are_literal_without_execution():
    parsed = boot._preset("/etc/mkinitcpio.d/linux.preset", """
# PRESETS=('private')
PRESETS=(
    'default' # ordinary
    'fallback'
)
fallback_image='/boot/initramfs-linux-fallback.img'
""")
    assert parsed["enabled_presets"] == ["default", "fallback"]
    assert parsed["outputs"][0]["enabled"] is True
    assert parsed["bootability_verified"] is False


@pytest.mark.parametrize("declaration", [
    "", "PRESETS=('$PRIVATE')", "PRESETS=('custom-private-name')",
    "PRESETS=('default')\nPRESETS+=('fallback')",
    "PRESETS=('default')\nPRESETS=('fallback')",
    "PRESETS=('default')\nPRESETS[1]='fallback'",
    "source '/SYNTHETIC_PRIVATE_CONFIG'\nPRESETS=('default')",
    "PRESETS=('default')\nfunction choose_outputs {\nfallback_image='/boot/initramfs-linux-fallback.img'\n}",
])
def test_dynamic_or_missing_presets_never_enable_outputs_by_guess(declaration):
    parsed = boot._preset("/etc/mkinitcpio.d/linux.preset", declaration + "\nfallback_image='/boot/initramfs-linux-fallback.img'")
    assert parsed["enabled_presets"] is None and parsed["parse_status"] == "partial_or_custom"
    assert parsed["outputs"][0]["enabled"] is None
    assert "PRIVATE" not in json.dumps(parsed)


def test_unknown_preset_paths_are_not_exposed():
    parsed = boot._preset("/etc/mkinitcpio.d/linux.preset", "PRESETS=('default')\ndefault_image='/home/PRIVATE/key'\nfallback_uki='$PRIVATE'")
    assert all(item["path"] is None for item in parsed["outputs"])
    assert "PRIVATE" not in json.dumps(parsed)


def test_grub_nested_static_ordinals_and_chainloader_drop_ids_titles_and_rootargs():
    parsed = boot._grub_entries("/boot/grub/grub.cfg", """
function load_video {
  insmod efi_gop
}
menuentry 'Arch Linux SECRET_TITLE { # }' --class arch --id SECRET_ID {
  linux /vmlinuz-linux root=UUID=SECRET_UUID quiet splash
  initrd /intel-ucode.img /initramfs-linux.img
}
submenu 'SECRET_SUBMENU' $menuentry_id_option 'SECRET_SUBMENU_ID' {
  menuentry 'Arch Linux fallback' --id SECRET_ID_2 {
    linux /vmlinuz-linux root=UUID=SECRET_UUID
    initrd /initramfs-linux-fallback.img
  }
  menuentry 'Arch Linux recovery' {
    chainloader (SECRET_DEVICE)/EFI/Linux/arch-linux.efi
  }
}
menuentry 'SECRET_WINDOWS_TITLE' {
  chainloader /EFI/Unknown/SECRET.efi
}
""")
    assert [entry["ordinal"] for entry in parsed["entries"]] == ["0", "1>0", "1>1", "2"]
    assert [entry["class"] for entry in parsed["entries"]] == ["normal", "fallback", "recovery", "unknown"]
    assert parsed["entries"][2]["images"] == ["/EFI/Linux/arch-linux.efi"]
    assert parsed["entries"][2]["boot_form"] == "chainloader"
    assert parsed["entries"][3]["custom_or_dynamic"] is True
    assert parsed["entries"][0]["flags"]["splash"] is True
    assert "SECRET" not in json.dumps(parsed) and "root=" not in json.dumps(parsed)
    assert parsed["active_entry_verified"] is False and parsed["runtime_order_verified"] is False


@pytest.mark.parametrize("body", [
    "if [ x = y ]; then\nmenuentry 'Arch Linux' {\nlinux /vmlinuz-linux\n}\nfi",
    "function dynamic_menu {\nmenuentry 'Arch Linux' {\nlinux /vmlinuz-linux\n}\n}\ndynamic_menu",
    "configfile '/PRIVATE/another.cfg'\nmenuentry 'Arch Linux' {\nchainloader +1\n}",
])
def test_conditional_function_or_external_grub_never_has_runtime_ordinal_confidence(body):
    parsed = boot._grub_entries("/boot/grub/grub.cfg", body)
    assert parsed["ordinal_confidence"] == "unknown_custom_syntax"
    assert parsed["active_entry_verified"] is False
    assert "PRIVATE" not in json.dumps(parsed)


def test_grub_entry_count_and_parser_time_are_bounded():
    text = "\n".join("menuentry 'Arch Linux' {\nlinux /vmlinuz-linux\n}" for _ in range(1000))
    parsed = boot._grub_entries("/boot/grub/grub.cfg", text)
    assert len(parsed["entries"]) == boot.MAX_MENU_ENTRIES and parsed["truncated"]
    assert boot._grub_entries("/boot/grub/grub.cfg", text, boot.Budget(time.monotonic() - 1))["truncated"]


def test_current_stub_evidence_is_distinct_from_default_entry_or_loader():
    parsed = boot._reported_images("""
Current Boot Loader:
        Product: GRUB 2.16
         Loader: └─/boot//EFI/GRUB/grubx64.efi
      Partition: /dev/disk/by-partuuid/PRIVATE_UUID
Current Stub:
        Product: systemd-stub 262
           Stub: └─/EFI/Linux/arch-linux.efi
      Partition: /dev/disk/by-partuuid/PRIVATE_UUID
Default Boot Loader Entry:
          title: PRIVATE_TITLE
            efi: /EFI/Linux/arch-linux-fallback.efi
""")
    assert [item["source"] for item in parsed] == ["bootctl_current_loader", "bootctl_current_stub"]
    assert parsed[0]["path"] == "/boot/EFI/GRUB/grubx64.efi"
    assert parsed[1]["path"] == "/EFI/Linux/arch-linux.efi"
    assert "not_disk_verified" in parsed[1]["confidence"]
    assert "PRIVATE" not in json.dumps(parsed) and "fallback" not in json.dumps(parsed)


def test_unknown_stub_format_or_private_uki_name_produces_no_image_guess():
    assert boot._reported_images("Current Stub:\n Product: unknown-stub\n Stub: /EFI/Linux/arch-linux.efi") == []
    assert boot._reported_images("Current Stub:\n Product: systemd-stub 262\n Stub: /EFI/Linux/PRIVATE_ID.efi") == []


def test_cmdline_emits_only_known_image_and_presentation_booleans():
    result = boot._cmdline("BOOT_IMAGE=(PRIVATE_DEVICE)/vmlinuz-linux root=UUID=PRIVATE_UUID quiet splash disablehooks=autodetect,plymouth secret=PRIVATE_SECRET")
    assert result["recognized_boot_image"] == "/vmlinuz-linux"
    assert result["flags"] == {"quiet": True, "splash": True, "plymouth_disabled": True}
    assert "PRIVATE" not in json.dumps(result) and "root=" not in json.dumps(result)
    assert boot._cmdline("root=UUID=PRIVATE_UUID")["recognized_boot_image"] is None


def test_mount_metadata_excludes_device_identity_and_exactly_classifies_inherited_mount():
    text = json.dumps({"filesystems": [{"target": "/boot", "fstype": "vfat", "size": "1000000",
                       "avail": 750000, "options": "rw,uid=PRIVATE_UID,secret=PRIVATE_SECRET",
                       "source": "/dev/PRIVATE_DEVICE", "uuid": "PRIVATE_UUID"}]})
    result = boot._mount(text, "/boot/efi")
    assert result["target"] == "/boot" and not result["exact_mount"]
    assert result["total_bytes"] == 1000000 and result["available_bytes"] == 750000
    assert result["read_only"] is False and "PRIVATE" not in json.dumps(result)
    assert boot._mount('{"filesystems":[]}', "/boot")["status"] == "unrecognized"


def test_static_default_and_hook_parsers_do_not_expose_unreviewed_values():
    defaults = boot._grub_defaults("GRUB_DEFAULT='PRIVATE_ID'\nGRUB_CMDLINE_LINUX_DEFAULT='root=UUID=PRIVATE_UUID quiet splash'")
    assert defaults["configured_default"] == {"kind": "custom"}
    assert defaults["active_entry_verified"] is False and "PRIVATE" not in json.dumps(defaults)
    assert boot._grub_defaults("GRUB_DEFAULT='1>0'")["configured_default"] == {"kind": "static_ordinal", "ordinal": "1>0"}
    hooks = boot._hooks("HOOKS=(base udev PRIVATE_HOOK plymouth keyboard)")
    assert hooks["known_hooks"] == ["base", "udev", "plymouth", "keyboard"]
    assert hooks["unknown_hook_count"] == 1 and "PRIVATE" not in json.dumps(hooks)


def test_known_image_metadata_distinguishes_missing_permission_symlink_empty_and_regular():
    path = "/boot/EFI/Linux/arch-linux-fallback.efi"
    assert boot._image_metadata(path, None, "permission_denied")["status"] == "permission_denied"
    assert boot._image_metadata(path, None, "not_found")["status"] == "not_found"
    assert boot._image_metadata(path, "symbolic link|12", "readable")["kind"] == "symlink"
    assert boot._image_metadata(path, "regular empty file|0", "readable")["bytes"] == 0
    assert boot._image_metadata(path, "regular file|1234", "readable")["bytes"] == 1234


def test_deadline_while_waiting_is_reported_as_budget_limit(monkeypatch):
    process = FakeProcess()
    waits, killed = [], []
    def wait(timeout):
        waits.append(timeout)
        if len(waits) == 1:
            raise subprocess.TimeoutExpired("mock-command", timeout)
        return 0
    process.wait = wait
    monkeypatch.setattr(boot.subprocess, "Popen", lambda *a, **kw: process)
    monkeypatch.setattr(boot, "_kill", lambda child: killed.append(child))
    assert boot._read_command(["/usr/bin/stat"], boot.Budget(time.monotonic() + 1))[-1] == "limit"
    assert killed == [process]
