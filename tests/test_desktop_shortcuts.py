"""Fake GSettings transactions only: these tests never change desktop settings."""
from copy import deepcopy
import io
import json
import shlex
import subprocess
import sys
from types import SimpleNamespace

import pytest

from ai_os import desktop_shortcuts as shortcuts


class FakeSettings:
    def __init__(self):
        self.values = {(shortcuts.MEDIA, shortcuts.LIST_KEY): []}
        self.builtin = {schema: [("existing-action", ["<Super>a", "<Super>space"])]
                        for schema in shortcuts.SCHEMAS}
        self.calls = []
        self.writes = []
        self.fail_once = None

    def run(self, argv, **kwargs):
        assert argv[0] == "/usr/bin/gsettings"
        assert kwargs["shell"] is False and kwargs["stdin"] == subprocess.DEVNULL
        assert 0 < kwargs["timeout"] <= 2
        self.calls.append(tuple(argv))
        action, *args = argv[1:]
        if action == "list-schemas":
            text = "\n".join(shortcuts.SCHEMAS)
        elif action == "list-recursively":
            text = "\n".join(f"{args[0]} {key} {value!r}" for key, value in self.builtin[args[0]])
        elif action == "get":
            schema, key = args
            value = self.values.get((schema, key), "")
            text = "@as []" if value == [] else repr(value)
        elif action == "set":
            schema, key, raw = args
            if self.fail_once == key:
                self.fail_once = None
                raise subprocess.TimeoutExpired(argv, 2, stderr="private settings output")
            value = shortcuts.parse_variant(raw, list if key == shortcuts.LIST_KEY else str)
            self.values[schema, key] = value
            self.writes.append((schema, key, value))
            text = ""
        else:
            pytest.fail("Unexpected settings operation")
        return SimpleNamespace(returncode=0, stdout=text, stderr="")


@pytest.fixture
def settings(monkeypatch):
    fake = FakeSettings()
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.setattr(shortcuts.subprocess, "run", fake.run)
    return fake


def custom(fake, path, binding, command="private unrelated command"):
    fake.values[shortcuts.MEDIA, shortcuts.LIST_KEY].append(path)
    schema = shortcuts.CUSTOM + ":" + path
    fake.values[schema, "name"] = "private unrelated label"
    fake.values[schema, "binding"] = binding
    fake.values[schema, "command"] = command


def test_proposal_is_read_only_preserves_super_keys_and_hides_other_commands(tmp_path, settings):
    path = shortcuts.ROOT + "custom0/"
    custom(settings, path, "<Control>y")
    result = shortcuts.propose_shortcuts(tmp_path)
    assert result["ok"] and not result["already_applied"]
    assert result["custom_shortcut_count"] == 1
    assert [binding["accelerator"] for binding in result["bindings"]] == ["<Super><Alt>a", "<Super><Alt>c", "<Super><Alt>r"]
    assert [shlex.split(binding["command"])[-1] for binding in result["bindings"]] == ["ai_os.hub_launcher", "ai_os.quick_chat", "--show"]
    assert "private unrelated" not in json.dumps(result)
    assert not any(call[1:] == ("get", shortcuts.CUSTOM + ":" + path, "command") for call in settings.calls)
    assert not settings.writes and not (tmp_path / "backups").exists()


def test_builtin_alias_and_custom_conflicts_are_detected_without_overwrite(tmp_path, settings):
    settings.builtin[shortcuts.SCHEMAS[0]] = [("existing-action", ["<Mod1><Mod4>A"])]
    custom(settings, shortcuts.ROOT + "custom0/", "<Alt><Super>c")
    result = shortcuts.propose_shortcuts(tmp_path)
    assert not result["ok"]
    assert {entry["id"] for entry in result["conflicts"]} == {"settings", "chat"}
    assert "private unrelated" not in json.dumps(result)
    assert not settings.writes


def test_occupied_reserved_path_is_not_overwritten_even_when_not_enabled(tmp_path, settings):
    schema = shortcuts.CUSTOM + ":" + shortcuts.ROOT + "regenos-settings/"
    settings.values[schema, "command"] = "private pre-existing command"
    result = shortcuts.propose_shortcuts(tmp_path)
    assert not result["ok"] and result["conflicts"][0]["id"] == "settings"
    assert "private pre-existing" not in json.dumps(result)
    assert not shortcuts.apply_shortcuts(result, tmp_path, human_confirmed=True)["ok"]
    assert not settings.writes


def test_human_confirmation_and_exact_proposal_are_both_required(tmp_path, settings):
    proposal = shortcuts.propose_shortcuts(tmp_path)
    assert not shortcuts.apply_shortcuts(proposal, tmp_path)["ok"]
    tampered = deepcopy(proposal)
    tampered["bindings"][0]["command"] = "malicious command"
    assert not shortcuts.apply_shortcuts(tampered, tmp_path, human_confirmed=True)["ok"]
    settings.builtin[shortcuts.SCHEMAS[0]].append(("changed-while-reviewing", ["<Alt>z"]))
    assert not shortcuts.apply_shortcuts(proposal, tmp_path, human_confirmed=True)["ok"]
    assert not settings.writes


def test_apply_private_backup_readback_and_idempotence(tmp_path, settings):
    path = shortcuts.ROOT + "custom0/"
    custom(settings, path, "<Control>y")
    before = deepcopy(settings.values)
    proposal = shortcuts.propose_shortcuts(tmp_path)
    result = shortcuts.apply_shortcuts(proposal, tmp_path, human_confirmed=True)
    assert result["ok"]
    backup = tmp_path / "backups/desktop-shortcuts" / (result["backup_id"] + ".json")
    assert backup.stat().st_mode & 0o777 == 0o600
    assert backup.parent.stat().st_mode & 0o777 == 0o700
    record = json.loads(backup.read_text())
    assert record["previous_paths"] == [path]
    assert settings.values[shortcuts.CUSTOM + ":" + path, "command"] == before[shortcuts.CUSTOM + ":" + path, "command"]
    assert settings.values[shortcuts.MEDIA, shortcuts.LIST_KEY][0] == path
    reviewed = shortcuts.propose_shortcuts(tmp_path)
    assert reviewed["already_applied"]
    count = len(settings.writes)
    assert shortcuts.apply_shortcuts(reviewed, tmp_path, human_confirmed=True)["already_applied"]
    assert len(settings.writes) == count


def test_revert_requires_confirmation_and_preserves_later_unrelated_paths(tmp_path, settings):
    original = shortcuts.ROOT + "custom0/"
    custom(settings, original, "<Control>y")
    result = shortcuts.apply_shortcuts(shortcuts.propose_shortcuts(tmp_path), tmp_path, human_confirmed=True)
    later = shortcuts.ROOT + "custom1/"
    custom(settings, later, "<Control>z")
    count = len(settings.writes)
    assert not shortcuts.revert_shortcuts(result["backup_id"], tmp_path)["ok"]
    assert len(settings.writes) == count
    assert shortcuts.revert_shortcuts(result["backup_id"], tmp_path, human_confirmed=True)["ok"]
    assert settings.values[shortcuts.MEDIA, shortcuts.LIST_KEY] == [original, later]
    for binding in shortcuts._trusted_bindings(tmp_path):
        assert settings.values[shortcuts.CUSTOM + ":" + binding["path"], "command"] == ""
    assert settings.values[shortcuts.CUSTOM + ":" + later, "command"] == "private unrelated command"


def test_revert_refuses_later_edits_to_owned_command(tmp_path, settings):
    result = shortcuts.apply_shortcuts(shortcuts.propose_shortcuts(tmp_path), tmp_path, human_confirmed=True)
    schema = shortcuts.CUSTOM + ":" + shortcuts.ROOT + "regenos-settings/"
    settings.values[schema, "command"] = "a later deliberate user edit"
    count = len(settings.writes)
    assert not shortcuts.revert_shortcuts(result["backup_id"], tmp_path, human_confirmed=True)["ok"]
    assert len(settings.writes) == count
    assert settings.values[schema, "command"] == "a later deliberate user edit"


def test_partial_write_failure_recovers_old_values_and_keeps_private_backup(tmp_path, settings):
    custom(settings, shortcuts.ROOT + "custom0/", "<Control>y")
    before = deepcopy(settings.values)
    proposal = shortcuts.propose_shortcuts(tmp_path)
    settings.fail_once = "command"
    result = shortcuts.apply_shortcuts(proposal, tmp_path, human_confirmed=True)
    assert not result["ok"] and result["rollback_ok"]
    assert settings.values[shortcuts.MEDIA, shortcuts.LIST_KEY] == before[shortcuts.MEDIA, shortcuts.LIST_KEY]
    for binding in proposal["bindings"]:
        schema = shortcuts.CUSTOM + ":" + binding["path"]
        assert all(settings.values[schema, key] == "" for key in ("name", "binding", "command"))
    assert (tmp_path / "backups/desktop-shortcuts" / (result["backup_id"] + ".json")).exists()
    assert "private settings output" not in json.dumps(result)


def test_concurrent_custom_path_addition_is_preserved_during_partial_recovery(tmp_path, settings, monkeypatch):
    original = shortcuts.ROOT + "custom0/"
    later = shortcuts.ROOT + "custom1/"
    custom(settings, original, "<Control>y")
    proposal = shortcuts.propose_shortcuts(tmp_path)
    original_run = settings.run
    injected = []

    def concurrently_edit(argv, **kwargs):
        result = original_run(argv, **kwargs)
        if argv[1] == "set" and not injected:
            injected.append(True)
            custom(settings, later, "<Control>z", "a concurrently added unrelated command")
        return result

    monkeypatch.setattr(shortcuts.subprocess, "run", concurrently_edit)
    result = shortcuts.apply_shortcuts(proposal, tmp_path, human_confirmed=True)
    assert injected and not result["ok"] and result["rollback_ok"]
    assert settings.values[shortcuts.MEDIA, shortcuts.LIST_KEY] == [original, later]
    assert settings.values[shortcuts.CUSTOM + ":" + later, "command"] == "a concurrently added unrelated command"
    for binding in proposal["bindings"]:
        schema = shortcuts.CUSTOM + ":" + binding["path"]
        assert all(settings.values[schema, key] == "" for key in ("name", "binding", "command"))


def test_symlink_backup_directory_is_rejected_before_writing_outside(tmp_path, settings):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    (home / "backups").symlink_to(outside, target_is_directory=True)
    result = shortcuts.apply_shortcuts(shortcuts.propose_shortcuts(home), home, human_confirmed=True)
    assert not result["ok"] and not settings.writes
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("payload", [[], {"version":1}, {"version":1,"bindings":[],"previous_paths":[]}, "private invalid backup"])
def test_invalid_backup_is_rejected_without_settings_writes(tmp_path, settings, payload):
    directory = tmp_path / "backups/desktop-shortcuts"
    directory.mkdir(parents=True, mode=0o700)
    identifier = "a" * 32
    backup = directory / (identifier + ".json")
    backup.write_text(json.dumps(payload))
    backup.chmod(0o600)
    result = shortcuts.revert_shortcuts(identifier, tmp_path, human_confirmed=True)
    assert not result["ok"] and not settings.writes
    assert "private invalid" not in json.dumps(result)


def test_home_paths_with_spaces_are_literal_command_arguments(tmp_path, settings):
    home = tmp_path / "space and dollar $()"
    home.mkdir()
    proposal = shortcuts.propose_shortcuts(home)
    assert proposal["ok"]
    for binding in proposal["bindings"]:
        argv = shlex.split(binding["command"])
        assert argv[:3] == ["/usr/bin/env", "AI_OS_HOME=" + str(home), sys.executable]
        assert argv[3] == "-m"


def test_non_gnome_and_oversized_native_request_never_call_settings(tmp_path, settings, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "Hyprland")
    assert not shortcuts.propose_shortcuts(tmp_path)["supported"]
    assert not settings.calls
    monkeypatch.setattr(sys, "argv", ["shortcuts", "--action", "apply", "--home", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"x" * 32769)))
    assert shortcuts.main() == 0
    assert not json.loads(capsys.readouterr().out)["ok"]
    assert not settings.calls


@pytest.mark.parametrize("raw", ["__import__('os').getcwd()", "{'unsupported':'mapping'}", "['a']" * 40000])
def test_variant_parser_rejects_unsupported_or_unbounded_input(raw):
    with pytest.raises(shortcuts.ShortcutError):
        shortcuts.parse_variant(raw, list)
