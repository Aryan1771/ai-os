from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


JobFn = Callable[[threading.Event, threading.Event], Any]


@dataclass
class ManagedJob:
    id: str
    name: str
    state: JobState = JobState.QUEUED
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    result: Any = None
    error: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    pause_event: threading.Event = field(default_factory=threading.Event, repr=False)


class JobRegistry:
    """Cooperative background jobs. Workers must observe the supplied events."""

    def __init__(self) -> None:
        self._jobs: dict[str, ManagedJob] = {}
        self._lock = threading.Lock()

    def submit(self, name: str, worker: JobFn) -> ManagedJob:
        job = ManagedJob(id=uuid.uuid4().hex, name=name)
        with self._lock:
            self._jobs[job.id] = job
        threading.Thread(target=self._run, args=(job, worker), daemon=True, name=f"ai-os-{job.id}").start()
        return job

    def _run(self, job: ManagedJob, worker: JobFn) -> None:
        job.state = JobState.RUNNING
        try:
            result = worker(job.cancel_event, job.pause_event)
            job.result = result
            job.state = JobState.CANCELLED if job.cancel_event.is_set() else JobState.COMPLETED
        except Exception as exc:
            job.error = str(exc)
            job.state = JobState.FAILED
        finally:
            job.finished_at = time.time()

    def get(self, job_id: str) -> ManagedJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[ManagedJob]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def pause(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job or job.state is not JobState.RUNNING:
            return False
        job.pause_event.set()
        job.state = JobState.PAUSED
        return True

    def resume(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job or job.state is not JobState.PAUSED:
            return False
        job.pause_event.clear()
        job.state = JobState.RUNNING
        return True

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job or job.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
            return False
        job.cancel_event.set()
        job.pause_event.clear()
        return True


def wait_if_paused(cancel_event: threading.Event, pause_event: threading.Event) -> bool:
    """Return False when cancelled; call this from cooperative worker loops."""
    while pause_event.is_set() and not cancel_event.wait(0.1):
        pass
    return not cancel_event.is_set()
