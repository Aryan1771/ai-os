# Planning dispatch deadline

The three-step conversation planner has a 120-second dispatch budget measured
with a monotonic clock. The initial model request and followups now receive the
same original deadline. Previously the initial request omitted it, and a stale
tool proposal could start an action after the budget expired. A temporary fake
clock reproduced a fresh synthetic action starting after 121 seconds of model
work; no real command or inference was needed.

The planner now rejects expired proposals before screen-model dispatch or normal
tool dispatch, including direct website/application routes. It checks again after
the public working-status update and research-mode preparation. A completed tool
result is preserved if the deadline expires during that tool or its next model
turn; the response states that no further action started. The planner never
retries a completed action to recover from expiry. Expired requests also stop
before model preparation and immediately before the provider POST. A remaining
fraction of a second is no longer rounded up to an extra second.
Spoken summaries of an interrupted multi-step task report expiry in English or
Hindi instead of announcing that the whole task completed.

This is a dispatch budget, not a hard wall-clock cancellation guarantee. It
does not interrupt an already dispatched tool, withdraw pending native approval,
or cancel an interactive confirmation that began while the budget was valid.
Those paths retain their existing independent executor/approval limits. HTTP
timeouts remain the requests library's connection/read timeouts rather than a
total streaming deadline. Memory/context budgeting, durable recovery and strict
concurrent VRAM admission remain separate A036/A040 work. No mutex or sampled
hardware estimate is claimed to reserve GPU memory.

Verification uses temporary synthetic settings, fake clocks, stubbed provider
responses and callback counters. It does not record a microphone, load a model,
launch a browser, run a host command or change a service:

```bash
~/.ai_os/venv/bin/python -m pytest -q tests/test_planner_deadline.py tests/test_interaction_harness.py tests/test_tool_argument_repair.py tests/test_companion.py --tb=short
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/ai_os_core.py tests/test_planner_deadline.py tests/test_companion.py
git diff --check
```

The source checkpoint passes 15 new fake-clock tests and a broader 151-test run
covering interaction, argument repair, companion state, steering, memory consent,
recipient drift, GitHub isolation and desktop routing. Correctness lint, full
new-test lint and whitespace checks pass. These are local source results, not
hardware or installed-service acceptance.

Owner task acceptance and real overload/recovery measurements remain pending.
