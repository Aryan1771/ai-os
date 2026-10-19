"""Synthetic expiry regressions; no user's memory database is read."""

from ai_os.conversation_memory import ConversationMemory
from ai_os.settings_store import save_settings


def test_expired_candidate_cannot_promote_from_stale_occurrences(tmp_path, monkeypatch):
    save_settings({"reinforced_memory_enabled": True}, tmp_path, human_confirmed=True)
    memory = ConversationMemory(tmp_path)
    clock = [1800000000.0]
    monkeypatch.setattr("ai_os.conversation_memory.time.time", lambda: clock[0])
    statement = "My fictional project uses a lavender theme."
    for _ in range(2):
        memory.append(statement, "Synthetic reply")
        clock[0] += 601
    clock[0] += 181 * 86400
    # Deliberately do not inspect or retrieve between expiry and the next append.
    memory.append(statement, "Synthetic reply")
    assert memory.reinforced() == []
    with memory.connect() as db:
        assert db.execute("SELECT hits FROM reinforced").fetchone()[0] == 1


def test_repeated_reinforcement_extends_expiry_but_not_past_a_gap(tmp_path, monkeypatch):
    save_settings({"reinforced_memory_enabled": True}, tmp_path, human_confirmed=True)
    memory = ConversationMemory(tmp_path)
    clock = [1800000000.0]
    monkeypatch.setattr("ai_os.conversation_memory.time.time", lambda: clock[0])
    statement = "I like synthetic stories about lunar gardens."
    for _ in range(3):
        memory.append(statement, "Synthetic reply")
        clock[0] += 601
    clock[0] += 170 * 86400
    memory.append(statement, "Synthetic reply")
    clock[0] += 170 * 86400
    assert memory.reinforced()[0]["hits"] == 4
    clock[0] += 181 * 86400
    memory.append(statement, "Synthetic reply")
    assert memory.reinforced() == []
    with memory.connect() as db:
        assert db.execute("SELECT hits FROM reinforced").fetchone()[0] == 1
