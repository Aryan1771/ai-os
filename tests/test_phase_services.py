from types import SimpleNamespace
from time import sleep

from ai_os.services.external_api import validate_external_url
from ai_os.services.jobs import JobRegistry, JobState, wait_if_paused
from ai_os.services.scanner import scan_file


def test_external_url_requires_opt_in_and_allowlist() -> None:
    config = SimpleNamespace(
        allow_external_apis=False,
        allowed_api_hosts=("api.openai.com",),
    )
    assert validate_external_url("https://api.openai.com/v1/chat", config) is not None

    config.allow_external_apis = True
    assert validate_external_url("http://api.openai.com/v1/chat", config) is not None
    assert validate_external_url("https://example.com/v1/chat", config) is not None
    assert validate_external_url("https://api.openai.com/v1/chat", config) is None


def test_cooperative_job_registry_completes_job() -> None:
    registry = JobRegistry()

    def worker(cancel_event, pause_event):
        assert wait_if_paused(cancel_event, pause_event)
        return "done"

    job = registry.submit("test", worker)
    for _ in range(100):
        if job.state in {JobState.COMPLETED, JobState.FAILED}:
            break
        sleep(0.01)
    assert job.state is JobState.COMPLETED
    assert job.result == "done"


def test_scanner_rejects_missing_file(tmp_path) -> None:
    result = scan_file(tmp_path / "missing.bin")
    assert result.ok is False
    assert "missing" in result.error.lower()
