# Headless CI checkpoint — 2026-10-20

The public GitHub Actions runs for source revisions `4ec0150` and `ee422f1`
failed three Python tests. The latter reported **3 failed, 1085 passed, 6 skipped**
on Ubuntu 24.04 / Python 3.12.15, then exited 139 during interpreter teardown.
The C++ and installer syntax steps did not run because Python tests failed.

- [Run 39468895671](https://github.com/Aryan1771/ai-os/actions/runs/39468895671)
- [Run 39471040412](https://github.com/Aryan1771/ai-os/actions/runs/39471040412)

## Confirmed causes and bounded changes

Two tests only inspect Bubblewrap argv construction but depended on the host
having `/usr/bin/bwrap` installed. The hosted runner did not. They now fake only
that exact file-presence probe; real cwd validation and every confinement-argument
assertion remain in place. A separate missing-Bubblewrap regression asserts the
existing fail-closed error. Production confinement was not changed, and no package
was installed on the developer host or added just to satisfy synthetic tests.

The native research bridge test had not adapted to the articles default. After
approval it performed real DNS resolution and attempted a real browser launch.
The hosted runner has no graphical session; a developer desktop could instead
open a real browser during the suite. The test now fakes DNS and browser dispatch,
asserts that no launch occurs before confirmation, checks the exact returned URLs,
and verifies that article mode creates no report. An autouse guard forbids an
unmocked browser launch throughout that test module. Existing article tests retain
the three-link bound, URL validation and stop-after-first-launch-failure checks.

The post-summary exit 139 has **not** been reproduced locally and has no confirmed
cause. No exception suppression, forced successful exit, speculative Qt lifetime
change or production workaround was added. A successful Python 3.12 hosted rerun
is still needed before calling the remote CI checkpoint complete.

## Reproduction and local evidence

Read-only remote inspection used:

```bash
gh run view 39468895671 --repo Aryan1771/ai-os --json conclusion,headSha,jobs,name,status,url
gh run view 39468895671 --repo Aryan1771/ai-os --log-failed
gh run view 39471040412 --repo Aryan1771/ai-os --json conclusion,headSha,jobs,name,status,url
gh run view 39471040412 --repo Aryan1771/ai-os --log-failed
```

Before the fixes, the following isolated simulation reproduced all three failures
without a network request, browser launch or package change. The fixed paths are
public dependency probes, not access to private data.

```bash
cd ~/src/ai-os
~/.ai_os/venv/bin/python - <<'PY'
import os
from pathlib import Path
import socket
import pytest
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ.pop('DISPLAY', None)
os.environ.pop('WAYLAND_DISPLAY', None)
real_is_file = Path.is_file
Path.is_file = lambda path: False if path == Path('/usr/bin/bwrap') else real_is_file(path)
socket.getaddrinfo = lambda *args, **kwargs: [
    (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
raise SystemExit(pytest.main(['-q', '--tb=short',
    'tests/test_access_grants.py::test_broad_command_runner_uses_bubblewrap_and_no_privilege_gain',
    'tests/test_command_navigation.py::test_broad_grant_allows_readonly_system_directory_cwd',
    'tests/test_research_reports.py::test_native_bridge_requires_confirmed_topic_and_never_model_launch']))
PY
```

Before: **3 failed in 0.26s**, exit 1. After: the same simulated conditions,
including the new `test_broad_command_runner_refuses_missing_bubblewrap`, produced
**4 passed in 0.23s**, exit 0.

Focused validation after the changes:

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q \
  tests/test_access_grants.py tests/test_command_navigation.py \
  tests/test_research_reports.py tests/test_research_articles.py --tb=short
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F \
  tests/test_access_grants.py tests/test_command_navigation.py tests/test_research_reports.py
git diff --check -- tests/test_access_grants.py tests/test_command_navigation.py tests/test_research_reports.py docs/CI_VALIDATION.md
```

Results: **89 passed in 1.05s**; correctness Ruff and whitespace checks passed.
Local interpreter: Python 3.14.8 / PySide6 6.11.2; Python 3.12 is not installed.

A further headless working-tree observation used:

```bash
env -u DISPLAY -u WAYLAND_DISPLAY QT_QPA_PLATFORM=offscreen \
  REGENOS_HUB_NO_COMPANION=1 ~/.ai_os/venv/bin/python -X faulthandler \
  -m pytest -q --tb=short
```

It exited 0 with **1116 passed, 6 skipped in 11.38s**, with no teardown crash.
Other source checkpoints were being prepared concurrently, so this is not final
revision acceptance. The six optional Plymouth source checks skipped because
their separately supplied upstream source directory was not set. These results
do not verify physical voice, GPU, desktop, boot, installer or ISO behavior.
