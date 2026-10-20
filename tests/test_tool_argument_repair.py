import json
import pytest
from ai_os import ai_os_core as core
from ai_os.tools import desktop_tools as desktop


@pytest.mark.parametrize(
    "text",
    [
        "Please open a random website to test if website opening works.",
        "Could you visit any website?",
        "Take me to an example page.",
        "Please bring up a random site in Brave.",
        "Go to a test web page for testing.",
    ],
)
def test_test_site_synonyms_select_only_benign_public_examples(text):
    result = desktop.website_intent(text)
    assert result and result["url"] in desktop.TEST_WEBSITES
    assert result["browser"] == "brave" if "Brave" in text else result["browser"] == ""


def test_negative_and_descriptive_test_site_text_do_not_launch():
    for text in (
        "Do not open a random website",
        "Why are random websites unsafe?",
        "Explain how opening a website works",
    ):
        assert desktop.website_intent(text) is None


def test_test_website_tool_uses_existing_installed_browser_launcher(monkeypatch):
    opened = []
    monkeypatch.setattr(
        desktop, "open_website", lambda url, browser: opened.append((url, browser)) or {"ok": True}
    )
    assert desktop.open_test_website("brave")["ok"]
    assert opened[0][0] in desktop.TEST_WEBSITES and opened[0][1] == "brave"


def test_read_only_invalid_args_can_be_corrected_once(tmp_path, monkeypatch):
    responses = iter(
        [
            {"tool": "list_directory", "arguments": {"directory": "/usr"}},
            {"tool": "list_directory", "arguments": {"path": "/usr"}},
            {"reply": "Directory metadata is ready."},
        ]
    )
    monkeypatch.setattr(core, "ask_ollama", lambda *_a, **_k: json.dumps(next(responses)))
    calls = []

    def read(path):
        calls.append(path)
        return {"ok": True, "entries": []}

    result = core.handle_user_text("List /usr", {"list_directory": read}, home=tmp_path)
    assert result["content"] == "Directory metadata is ready." and calls == ["/usr"]


def test_permission_and_action_failures_are_never_automatically_retried(tmp_path, monkeypatch):
    requests = []
    monkeypatch.setattr(
        core,
        "ask_ollama",
        lambda *_a, **_k: (
            requests.append(True)
            or json.dumps({"tool": "list_directory", "arguments": {"path": "/private"}})
        ),
    )

    def denied(path):
        raise PermissionError("Access denied")

    result = core.handle_user_text("List directory", {"list_directory": denied}, home=tmp_path)
    assert result["result"]["ok"] is False and len(requests) == 1


def test_second_invalid_read_arguments_stop_instead_of_looping(tmp_path, monkeypatch):
    responses = iter(
        [
            {"tool": "list_directory", "arguments": {"directory": "/usr"}},
            {"tool": "list_directory", "arguments": {"folder": "/usr"}},
        ]
    )
    monkeypatch.setattr(core, "ask_ollama", lambda *_a, **_k: json.dumps(next(responses)))
    result = core.handle_user_text(
        "List /usr", {"list_directory": lambda path: {"ok": True}}, home=tmp_path
    )
    assert result["result"]["ok"] is False
