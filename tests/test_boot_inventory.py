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
        assert argv[:3] == ["/usr/bin/sudo", "-n", "--"]
        command = argv[3:]
        assert command[0] in {"/usr/bin/bootctl", "/usr/bin/ls", "/usr/bin/cat"}
        if command[0] == "/usr/bin/cat":
            assert command[1] == "--" and command[-1] in boot.CONFIG_FILES
        if command[0] == "/usr/bin/ls":
            assert command == ["/usr/bin/ls", "--color=never", "--file-type", "-1", "--", command[-1]]
            assert command[-1] in boot.DIRECTORIES


def test_sudo_password_failure_stops_once_without_raw_error(monkeypatch):
    calls = []

    def denied(argv, _budget):
        calls.append(argv)
        return 1, "", "sudo: a password is required; SYNTHETIC_PRIVATE_LOG", ""

    monkeypatch.setattr(boot, "_read_command", denied)
    result = boot.inspect(sudo=True)
    assert len(calls) == 1 and result["status"] == "sudo_unavailable"
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
        if argv[3] == "/usr/bin/bootctl":
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
