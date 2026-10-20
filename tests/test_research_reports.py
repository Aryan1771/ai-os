"""Public research provenance and native narration controls, without network/audio."""
import os
import json
from pathlib import Path
import socket
import sys
import time

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


@pytest.fixture(autouse=True)
def no_real_browser(monkeypatch):
    monkeypatch.setattr("ai_os.tools.desktop_tools.open_website",
                        lambda *_args, **_kwargs: pytest.fail("Tests must fake browser launches"))


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_fetch_json", sources)
    return research.run_research("giant pandas", home=tmp_path, mode="report", human_confirmed=True)


def test_model_proposal_cannot_research_without_exact_human_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_fetch_json", lambda *a: pytest.fail("Unapproved online request"))
    proposed = research.propose_research("giant pandas")
    assert proposed["approval_required"]["arguments"] == {"topic": "giant pandas", "mode": "articles"}
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


def test_real_api_limits_and_short_abstract_provenance(tmp_path, monkeypatch):
    calls = []
    words = [f"abstractword{number}" for number in range(60)]

    def deposited(url, params):
        calls.append((url, params))
        if "wikipedia" in url:
            # Official TextExtracts only supports exchars up to 1200; the old
            # mocked tests accepted 2200 and concealed a live endpoint failure.
            assert 1 <= params["exchars"] <= 1200
            return sources(url, params)
        assert "abstract" in params["select"].split(",")
        return {"message": {"items": [
            {"title": ["Deposited abstract"], "URL": "https://doi.org/10.1234/abstract",
             "abstract": "<jats:p>" + " ".join(words) + "</jats:p><script>should-not-appear</script>"},
            {"title": ["Metadata only"], "URL": "https://doi.org/10.1234/metadata"},
            {"title": ["Later duplicate metadata"], "URL": "https://doi.org/10.1234/abstract"},
        ]}}

    monkeypatch.setattr(research, "_fetch_json", deposited)
    saved = research.run_research("giant pandas", home=tmp_path, mode="report", human_confirmed=True)
    assert len(calls) == 2
    assert saved["evidence_counts"] == {"encyclopedia": 1, "abstract": 1, "metadata": 1}
    report = research.read_report(saved["report_id"], home=tmp_path)
    markdown = report["markdown"]
    assert "publisher-deposited abstract" in markdown
    assert "abstractword24" in markdown and "abstractword25" not in markdown
    assert "should-not-appear" not in markdown and "<jats:p>" not in markdown
    assert "https://doi.org/10.1234/abstract" in markdown
    assert "copyright may belong to the publisher or authors" in markdown
    assert "Full research papers were not read" in markdown
    assert "Relevance and findings require reading the paper" in markdown
    assert "Later duplicate metadata" not in markdown


def test_report_language_is_explicit_and_does_not_translate_or_invent_sources(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(research, "_fetch_json", lambda url, params: calls.append((url, params)) or sources(url, params))
    saved = research.run_research("giant pandas", home=tmp_path, mode="report", language="hi", human_confirmed=True)
    report = research.read_report(saved["report_id"], home=tmp_path)
    assert report["language"] == "hi" and saved["language"] == "hi"
    assert "स्रोत विवरण" in report["markdown"]
    assert "A synthetic encyclopedia excerpt" in report["markdown"]
    assert {call[1].get("query", call[1].get("gsrsearch")) for call in calls} == {"giant pandas"}
    assert "https://" not in " ".join(report["paragraphs"])
    calls.clear()
    for invalid in ("fr", [], True):
        with pytest.raises(ValueError, match="language"):
            research.run_research("giant pandas", home=tmp_path, mode="report", language=invalid, human_confirmed=True)
    assert calls == []


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
    opened = []
    monkeypatch.setattr(research, "_fetch_json", sources)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs:
                        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])
    monkeypatch.setattr("ai_os.tools.desktop_tools.open_website",
                        lambda url: opened.append(url) or {"ok": True})
    request = {"action": "approved_research", "topic": "giant pandas"}
    assert not dispatch(request, tmp_path)["response"]["result"]["ok"]
    assert opened == []
    result = dispatch(request | {"confirmed": True}, tmp_path)
    assert result["response"]["result"]["ok"]
    assert opened == ["https://en.wikipedia.org/wiki/Giant_panda",
                      "https://doi.org/10.1234/example"]
    assert result["response"]["result"]["mode"] == "articles"
    assert not list(tmp_path.rglob("*.md"))


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


def test_native_paragraph_selection_and_previous_are_explicit(app, saved, tmp_path, monkeypatch):
    widget = ResearchWidget(tmp_path)
    requests = []
    monkeypatch.setattr(widget, "_start", lambda request, seconds: requests.append(request) or True)
    assert widget.load_report(saved["report_id"])
    assert widget.paragraph_picker.count() == len(widget.paragraphs)
    assert widget.select_paragraph(2)
    assert requests == []  # Browsing a paragraph must not start speech or inference.
    assert widget.index == 2 and widget.paragraph_picker.currentIndex() == 2
    assert widget.read_previous()
    assert requests[-1]["index"] == 1 and widget.index == 1
    widget.language.setCurrentIndex(widget.language.findData("hi"))
    assert widget.explain_current()
    assert requests[-1]["language"] == "hi" and requests[-1]["index"] == 1
    assert not widget.select_paragraph(-1)
    widget.action = None
    widget.close()


def test_native_selected_report_language_is_in_exact_consent_and_request(app, tmp_path, monkeypatch):
    widget = ResearchWidget(tmp_path)
    widget.topic.setText("giant pandas")
    widget.report_language.setCurrentIndex(widget.report_language.findData("hi"))
    requests = []
    monkeypatch.setattr(widget, "_start", lambda request, seconds: requests.append(request) or True)

    def approve(box):
        assert box.defaultButton() == box.button(QMessageBox.StandardButton.No)
        assert "Report labels: Hindi" in box.text()
        assert "giant pandas" in box.text() and "original language" in box.text()
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "exec", approve)
    assert widget.research(mode="report")
    assert requests == [{"action": "research", "topic": "giant pandas", "language": "hi", "mode": "report", "confirmed": True}]
    widget.action = None
    widget.close()


def test_native_progress_updates_before_worker_finished_and_handles_partial_utf8(app, tmp_path, monkeypatch):
    widget = ResearchWidget(tmp_path)
    event = (json.dumps({"progress": "Searching sources…"}, ensure_ascii=False) + "\n").encode()
    chunks = [event[:-2], event[-2:]]
    monkeypatch.setattr(widget.process, "readAllStandardOutput", lambda: chunks.pop(0))
    widget.status.setText("Waiting")
    widget._output()
    assert widget.status.text() == "Waiting"
    widget._output()
    assert widget.status.text() == "Searching sources…"
    widget.action = None
    widget.close()


def test_native_failed_worker_and_removed_report_have_visible_feedback(app, saved, tmp_path, monkeypatch):
    widget = ResearchWidget(tmp_path)
    assert widget.load_report(saved["report_id"])
    Path(saved["path"]).unlink()
    assert widget.open_report() is False
    assert "no longer available" in widget.status.text()
    monkeypatch.setattr(widget.process, "readAllStandardOutput", lambda: b"")
    widget.action = "speak"
    widget.output = bytearray(json.dumps({"result": {"ok": True, "message": "Should not report success"}}).encode())
    widget._finished(1, None)
    assert "successful result" in widget.status.text()
    assert "Should not report success" not in widget.status.text()
    widget.action = None
    widget.close()


def test_pause_stops_synthetic_worker_and_its_playback_child(app, tmp_path):
    """Exercise actual process-group cleanup without microphone or audio assets."""
    import psutil
    from PySide6.QtCore import QProcess

    if sys.platform != "linux":
        pytest.skip("Linux process group behavior")
    widget = ResearchWidget(tmp_path)
    widget.action = "speak"
    pid_file = tmp_path / "synthetic-child.pid"
    script = ("import subprocess,sys,time,pathlib; "
              "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); "
              "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); "
              "print('ready',flush=True);time.sleep(30)")
    child_pid = None
    try:
        widget.process.start(sys.executable, ["-c", script, str(pid_file)])
        assert widget.process.waitForStarted(2000)
        assert widget.process.waitForReadyRead(2000)
        child_pid = int(pid_file.read_text())
        assert os.getpgid(child_pid) == widget.process.processId()
        widget.stop()
        assert widget.process.state() == QProcess.ProcessState.NotRunning
        # A reparented dead child can briefly remain a zombie awaiting init;
        # it is no longer executing or holding the speech lease/audio device.
        for _ in range(100):
            try:
                if psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE:
                    break
            except psutil.NoSuchProcess:
                break
            time.sleep(.01)
        else:
            pytest.fail("Synthetic playback child survived pause")
        assert widget.cancelled is True
    finally:
        widget.stop()
        if child_pid is not None and psutil.pid_exists(child_pid):
            try:
                psutil.Process(child_pid).kill()
            except psutil.NoSuchProcess:
                pass
        widget.close()
