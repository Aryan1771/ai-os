import json
import sqlite3
import subprocess
import sys
import time

import pytest

from ai_os import ai_os_core as core
from ai_os.conversation_memory import ConversationMemory
from ai_os.settings_store import save_settings


@pytest.mark.parametrize("days, retained", [(7, False), (90, True)])
@pytest.mark.parametrize("operation", ["history", "context", "append"])
def test_memory_access_respects_saved_retention(tmp_path, days, retained, operation):
    save_settings({"memory_retention_days": days}, tmp_path)
    memory = ConversationMemory(tmp_path)
    memory.append("Older project fact", "Keep according to saved policy")
    with memory.connect() as db:
        db.execute("UPDATE turns SET created=?", (time.time() - 45 * 86400,))
    if operation == "append":
        memory.append("New fact", "Okay")
    elif operation == "context":
        memory.context("Older project fact")
    else:
        memory.history()
    with memory.connect() as db:
        count = db.execute("SELECT COUNT(*) FROM turns WHERE user='Older project fact'").fetchone()[0]
    assert bool(count) is retained


def test_restart_and_session_isolation(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("Our codename is Copper Finch", "Understood", session="work")
    code = (
        "import json,sys; from pathlib import Path; "
        "from ai_os.conversation_memory import ConversationMemory; "
        'print(json.dumps(ConversationMemory(Path(sys.argv[1])).context("What is our codename?",session="work")))'
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert "Copper Finch" in result.stdout
    assert memory.context("What is our codename?", session="personal") == []


def test_long_term_retrieval_and_explicit_preferences(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("Copper Finch uses SQLite storage", "Noted")
    for i in range(15):
        memory.append(f"Unrelated turn {i}", "Okay")
    memory.remember("style", "Prefer concise replies")
    memory.put("Gardening", "My basil needs morning light")
    context = json.dumps(memory.context("How does Copper Finch store data?"))
    assert "SQLite" in context and "Prefer concise replies" in context
    assert "basil" not in context


def test_forget_cannot_reappear_from_turns_notes_or_preferences(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("My preference is lavender", "Lavender, understood")
    memory.remember("color", "lavender")
    memory.put("Color", "lavender")
    assert memory.forget("lavender") == 3
    restarted = ConversationMemory(tmp_path)
    assert "lavender" not in json.dumps(restarted.context("What is my color preference?")).lower()
    assert restarted.history() == [] and restarted.notes() == [] and restarted.preferences() == {}
    with pytest.raises(ValueError):
        restarted.forget("")


def test_literal_forget_and_session_delete(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("100% battery", "Okay", session="a")
    memory.append("Do not erase me", "Okay", session="b")
    assert memory.forget("%") == 1
    assert len(memory.history("b")) == 1
    memory.clear_history("a")
    assert len(memory.history("b")) == 1
    memory.clear_all()
    assert memory.sessions() == []


@pytest.mark.parametrize("budget", [0, 1, 63, 64, 200, 1024])
def test_memory_budget_includes_reference_labels(tmp_path, budget):
    memory = ConversationMemory(tmp_path)
    memory.append("x" * 8000, "y" * 12000)
    memory.put("Large note", "note " * 1000)
    memory.remember("style", "s" * 1000)
    assert sum(len(m["content"]) for m in memory.context("Large note", budget=budget)) <= budget


def test_migration_backs_up_existing_database(tmp_path):
    path = tmp_path / "data/private/conversations.sqlite3"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE marker(value TEXT)")
        db.execute("INSERT INTO marker VALUES ('existing data')")
    ConversationMemory(tmp_path)
    backups = list((tmp_path / "backups").glob("*/conversations.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute("SELECT value FROM marker").fetchone()[0] == "existing data"
    ConversationMemory(tmp_path)
    assert len(list((tmp_path / "backups").glob("*"))) == 1


def test_obvious_secrets_not_automatically_retained(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("password: do-not-save-this", "Okay")
    assert memory.history() == []


def test_remote_memory_requires_separate_explicit_consent(tmp_path, monkeypatch):
    memory = ConversationMemory(tmp_path)
    memory.append("Private local fact", "Noted")
    save_settings(
        {
            "ai_provider": "openai_compatible",
            "ollama_url": "https://api.openai.com/v1/chat/completions",
            "allow_external_apis": True,
        },
        tmp_path,
        human_confirmed=True,
    )
    monkeypatch.setattr(core, "runtime_policy", lambda home: None)
    payloads = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "Hello"}}]}

    def post(*args, **kwargs):
        payloads.append(kwargs["json"])
        return Response()

    monkeypatch.setattr(core.requests, "post", post)
    core.ask_ollama("Hello", set(), tmp_path)
    assert "Private local fact" not in json.dumps(payloads[-1])
    with pytest.raises(PermissionError):
        save_settings({"memory_allow_remote": True}, tmp_path)
    save_settings({"memory_allow_remote": True}, tmp_path, human_confirmed=True)
    core.ask_ollama("Hello", set(), tmp_path)
    assert "Private local fact" in json.dumps(payloads[-1])


def test_model_cannot_write_explicit_memory():
    registry = core.build_tool_registry()
    assert (
        not {"set_habit", "store_semantic_memory", "remember_event", "remember", "forget"}
        & registry.keys()
    )


def test_bridge_preserves_selected_session(tmp_path, monkeypatch):
    from ai_os.hub_bridge import dispatch

    observed = []

    def handle(text, **kwargs):
        observed.append(kwargs["session"])
        return {"type": "text", "content": "okay"}

    monkeypatch.setattr(core, "handle_user_text", handle)
    dispatch({"action": "chat", "text": "hello", "session": "work"}, tmp_path)
    assert observed == ["work"]


def test_inflight_reply_cannot_restore_forgotten_memory(tmp_path):
    memory = ConversationMemory(tmp_path)
    memory.append("lavender", "favorite color")
    started_revision = memory.revision()
    memory.forget("lavender")
    memory.append("lavender", "late reply", expected_revision=started_revision)
    assert memory.history() == []
    memory.append("new fact", "new reply", expected_revision=memory.revision())
    assert len(memory.history()) == 1
