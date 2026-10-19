"""Public research provenance and native narration controls, without network/audio."""
import os
from pathlib import Path
import socket

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMessageBox

from ai_os import research_reports as research
from ai_os.hub_bridge import dispatch
from ai_os.research_widget import ResearchWidget


def sources(url, params):
    if "wikipedia" in url:
        assert params["gsrsearch"] == "giant pandas"
        return {"query": {"pages": [{"title": "Giant panda", "extract": "A synthetic encyclopedia excerpt about panda conservation.", "fullurl": "https://en.wikipedia.org/wiki/Giant_panda"}]}}
    return {"message": {"items": [{"title": ["A synthetic conservation paper"], "URL": "https://doi.org/10.1234/example", "published": {"date-parts": [[2025]]}}]}}


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_fetch_json", sources)
    return research.run_research("giant pandas", home=tmp_path, human_confirmed=True)


def test_model_proposal_cannot_research_without_exact_human_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_fetch_json", lambda *a: pytest.fail("Unapproved online request"))
    proposed = research.propose_research("giant pandas")
    assert proposed["approval_required"]["arguments"] == {"topic": "giant pandas"}
    for value in (False, 1, "true", None):
        assert research.run_research("giant pandas", home=tmp_path, human_confirmed=value)["ok"] is False
    assert not (tmp_path / "data").exists()


def test_report_retains_actual_source_links_and_metadata_limitations(saved, tmp_path):
    report = research.read_report(saved["report_id"], home=tmp_path)
    text = report["markdown"]
    assert saved["source_count"] == 2 and saved["ok"]
    assert "https://doi.org/10.1234/example" in text
    assert "https://en.wikipedia.org/wiki/Giant_panda" in text
    assert "Full research papers were not read" in text
    assert "Relevance and findings require reading the paper" in text
    assert "https://" not in " ".join(report["paragraphs"])
    assert Path(saved["path"]).stat().st_mode & 0o777 == 0o600
    assert Path(saved["path"]).parent.stat().st_mode & 0o777 == 0o700
    assert research.list_reports(tmp_path)[0]["report_id"] == saved["report_id"]


def test_missing_sources_never_fabricates_report(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_fetch_json", lambda *a: {})
    result = research.run_research("pandas", home=tmp_path, human_confirmed=True)
    assert not result["ok"] and not list(tmp_path.rglob("*.md"))


def test_malformed_sources_fall_back_with_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_fetch_json", lambda *a: {"query": None, "message": None})
    result = research.run_research("pandas", home=tmp_path, human_confirmed=True)
    assert not result["ok"] and len(result["warnings"]) == 2


@pytest.mark.parametrize("url", ["http://en.wikipedia.org/wiki/Test", "https://example.com/wiki/Test",
                                  "https://en.wikipedia.org@evil.com/wiki/Test", "file:///etc/passwd",
                                  "https://en.wikipedia.org/wiki/Test\n", "https://user:password@en.wikipedia.org/wiki/Test"])
def test_source_urls_are_public_provenance_only(url):
    assert not research._source_url(url, "en.wikipedia.org", "/wiki/")


def test_api_endpoints_reject_arbitrary_or_private_network(monkeypatch):
    with pytest.raises(ValueError):
        research._public_endpoint("https://localhost/")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="nonpublic"):
        research._public_endpoint("https://api.crossref.org/works")


def test_report_traversal_and_symlink_reads_fail_closed(saved, tmp_path):
    with pytest.raises(ValueError):
        research.read_report("../../secret", home=tmp_path)
    path = Path(saved["path"])
    target = tmp_path / "other"
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(OSError):
        research.read_report(saved["report_id"], home=tmp_path)


def test_native_bridge_requires_confirmed_topic_and_never_model_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_fetch_json", sources)
    request = {"action": "approved_research", "topic": "giant pandas"}
    assert not dispatch(request, tmp_path)["response"]["result"]["ok"]
    result = dispatch(request | {"confirmed": True}, tmp_path)
    assert result["response"]["result"]["ok"]


def test_narration_is_one_paragraph_with_shared_speech_lease(saved, tmp_path, monkeypatch):
    from ai_os.speech_queue import SpeechQueue
    from ai_os.speech_lease import speech_lease
    spoken = []
    monkeypatch.setattr(SpeechQueue, "speak_text", lambda self, text: spoken.append(text))
    assert not research.speak_paragraph(saved["report_id"], 0, home=tmp_path)["ok"]
    with speech_lease(tmp_path) as acquired:
        assert acquired
        assert not research.speak_paragraph(saved["report_id"], 0, home=tmp_path, human_confirmed=True)["ok"]
    assert research.speak_paragraph(saved["report_id"], 0, home=tmp_path, human_confirmed=True)["ok"]
    assert len(spoken) == 1
    with pytest.raises(ValueError):
        research.speak_paragraph(saved["report_id"], 999, home=tmp_path, human_confirmed=True)


def test_explanation_is_local_tool_free_and_does_not_use_private_memory(saved, tmp_path, monkeypatch):
    from ai_os.speech_queue import SpeechQueue
    from types import SimpleNamespace
    calls, spoken = [], []
    class Session:
        trust_env = True
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            assert self.trust_env is False
            calls.append((url, kwargs))
            return SimpleNamespace(status_code=200, content=b'{}', raise_for_status=lambda: None,
                                   json=lambda: {"message": {"content": "An explanation of this synthetic excerpt."}})
    monkeypatch.setattr(research.requests, "Session", Session)
    monkeypatch.setattr(SpeechQueue, "speak_text", lambda self, text: spoken.append(text))
    result = research.explain_paragraph(saved["report_id"], 1, home=tmp_path, human_confirmed=True)
    assert result["ok"] and len(spoken) == 1
    assert calls[0][0].startswith("http://127.0.0.1:")
    payload = calls[0][1]["json"]
    assert "tools" not in payload and len(payload["messages"]) == 2
    assert "untrusted source excerpt" in payload["messages"][0]["content"]
    assert calls[0][1]["allow_redirects"] is False
    assert not research.explain_paragraph(saved["report_id"], 1, home=tmp_path)["ok"]


def test_explanation_cannot_send_report_to_remote_provider(saved, tmp_path, monkeypatch):
    from ai_os.config import atomic_json, load_raw_config
    monkeypatch.setattr(research.requests, "Session", lambda: pytest.fail("Private excerpt sent remotely"))
    atomic_json(tmp_path / "config.json", load_raw_config(tmp_path) | {"ollama_url": "http://192.168.10.10:11434/api/chat"})
    with pytest.raises(ValueError):
        research.explain_paragraph(saved["report_id"], 1, home=tmp_path, human_confirmed=True)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["research-widget-test"])


def test_native_cancel_never_starts_network_and_report_links_are_click_only(app, saved, tmp_path, monkeypatch):
    widget = ResearchWidget(tmp_path)
    widget.topic.setText("giant pandas")
    starts = []
    monkeypatch.setattr(widget, "_start", lambda *a: starts.append(a) or True)
    def deny(box):
        assert box.defaultButton() == box.button(QMessageBox.StandardButton.No)
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(QMessageBox, "exec", deny)
    assert not widget.research() and not starts
    assert widget.load_report(saved["report_id"])
    assert widget.index == 0
    widget.read_current()
    assert starts[-1][0]["index"] == 0 and widget.index == 0
    widget.read_next()
    assert starts[-1][0]["index"] == 1
    urls = []
    monkeypatch.setattr("ai_os.research_widget.QDesktopServices.openUrl", lambda url: urls.append(url.toString()))
    widget.open_source(QUrl("file:///etc/passwd"))
    assert not urls
    widget.open_source(QUrl("https://doi.org/10.1234/example"))
    assert urls == ["https://doi.org/10.1234/example"]
    widget.action = None
    widget.close()
