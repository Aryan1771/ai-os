import pytest

from ai_os.settings_server import save_settings


def test_settings_server_saves_non_protected_change(tmp_path) -> None:
    saved = save_settings({"theme": "ocean"}, tmp_path)

    assert saved["theme"] == "ocean"


def test_sandbox_blocks_protected_change_without_confirmation(tmp_path) -> None:
    with pytest.raises(PermissionError):
        save_settings({"always_listening_enabled": True}, tmp_path)


def test_sandbox_allows_confirmed_protected_change(tmp_path) -> None:
    saved = save_settings(
        {"always_listening_enabled": True, "wake_word_enabled": True},
        tmp_path,
        human_confirmed=True,
    )

    assert saved["always_listening_enabled"] is True
    assert saved["wake_word_enabled"] is True
