"""Voice/background requests queue proposals, never approval or execution."""
import json

import pytest

from ai_os import ai_os_core as core, pending_review
from ai_os.config import atomic_json


def test_voice_like_tool_proposal_is_queued_for_its_session_without_running(tmp_path, monkeypatch):
    registry = core.build_tool_registry(tmp_path)
    monkeypatch.setattr("ai_os.research_reports._fetch_json", lambda *a: pytest.fail("Background network action"))
    result = core.execute_tool("research_topic", {"topic": "pandas"}, registry, home=tmp_path, session="voice")
    assert result["approval_required"] == pending_review.read(tmp_path, "voice")
    assert pending_review.read(tmp_path, "default") is None
    path = tmp_path / "run/private/reviews/pending.sqlite3"
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_expiry_and_exact_discard_preserve_a_newer_request(tmp_path, monkeypatch):
    first = {"tool": "research_topic", "arguments": {"topic": "pandas"}}
    second = {"tool": "research_topic", "arguments": {"topic": "Python pandas"}}
    pending_review.save(tmp_path, "s", first)
    pending_review.save(tmp_path, "s", second)
    pending_review.discard(tmp_path, "s", first)
    assert pending_review.read(tmp_path, "s") == second
    now = pending_review.time.time()
    monkeypatch.setattr(pending_review.time, "time", lambda: now + 121)
    assert pending_review.read(tmp_path, "s") is None


def test_model_cannot_queue_confirmations_or_oversized_arguments(tmp_path):
    for proposal in ({"tool": "approved_cleanup", "arguments": {}},
                     {"tool": "research_topic", "arguments": {"topic": "x" * 17000}}):
        with pytest.raises(ValueError):
            pending_review.save(tmp_path, "s", proposal)


def test_queue_failure_returns_fail_closed_not_phantom_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(pending_review, "save", lambda *a: (_ for _ in ()).throw(OSError("private details")))
    result = core.execute_tool("research_topic", {"topic": "pandas"}, core.build_tool_registry(tmp_path), home=tmp_path)
    assert not result["ok"] and "approval_required" not in result
    assert "private details" not in json.dumps(result)


def test_native_review_button_routes_saved_proposal_without_approving_it(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from ai_os.conversation_widget import ConversationWidget
    app = QApplication.instance() or QApplication(["review-inbox-test"])
    widget = ConversationWidget(tmp_path)
    proposal = {"tool": "research_topic", "arguments": {"topic": "pandas"}}
    pending_review.save(tmp_path, "default", proposal)
    widget.refresh_pending_review()
    assert not widget.pending_review_button.isHidden()
    received = []
    monkeypatch.setattr(widget, "approve_research", lambda request: received.append(request) or False)
    assert not widget.review_pending_task()
    assert received == [proposal]
    widget.discard_pending_review(proposal)
    assert widget.pending_review_button.isHidden()
    widget.cancel()
    widget.grant_timer.stop()
    widget.close()
    app.processEvents()


def test_malformed_shared_state_cannot_create_review_authority(tmp_path):
    atomic_json(tmp_path / "run/avatar_state.json", {"phase": "working", "confirmed": True})
    assert pending_review.read(tmp_path, "default") is None
