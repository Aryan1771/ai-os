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

### Hosted follow-up: assertions fixed; interpreter crash remains

- [Run 39471797121](https://github.com/Aryan1771/ai-os/actions/runs/39471797121),
  revision `6aa38d7510284e1bd1e3e14a7f7b07636d429449`: **1089 passed, 6 skipped
  in 20.47s**, then SIGSEGV / exit 139.
- [Run 39471870621](https://github.com/Aryan1771/ai-os/actions/runs/39471870621),
  revision `9f698d26eaa4decc68c45103c5ddb7383f240200`: **1116 passed, 6 skipped
  in 21.58s**, then SIGSEGV / exit 139.

Both used Python 3.12.15. Installation logs show PySide6-Essentials and shiboken6
**6.12.0**, whereas the developer host has 6.11.2. This dependency difference is
a lead, not proof of a Qt version regression. In both hosted runs the C++ and
installer syntax stages were skipped because the Python process failed.

The diagnostic workflow enabled `PYTHONFAULTHANDLER=1` and ran independent Python 3.12
matrix jobs with PySide6-Essentials **6.11.2** and **6.12.0**, each installed in the
same pip transaction as the editable desktop/dev requirements. Matrix fail-fast
was disabled so a failure in one version could not hide the other result. Both
retained the existing C++ and installer syntax stages. The comparison changed only
hosted CI dependencies and did not ignore crashes or force a successful result.

### Controlled comparison results

The same-source jobs differed only in their explicit PySide6 requirement; both
used Ubuntu 24.04 and Python 3.12.15. Both comparisons reproduced the difference:

| Revision / run | PySide6 6.11.2 | PySide6 6.12.0 |
| --- | --- | --- |
| `f2d9e25` / [39472270464](https://github.com/Aryan1771/ai-os/actions/runs/39472270464) | 1116 passed, 6 skipped in 20.67s; exit 0; C++ and shell checks passed | 1116 passed, 6 skipped in 20.01s; then exit 139 |
| `28d9258` / [39472375770](https://github.com/Aryan1771/ai-os/actions/runs/39472375770) | 1144 passed, 6 skipped in 17.64s; exit 0; C++ and shell checks passed | 1144 passed, 6 skipped in 26.64s; then exit 139 |

The passing [latest 6.11.2 job](https://github.com/Aryan1771/ai-os/actions/runs/39472375770/job/118799455246)
also passed the historical C++ hub test (1/1) and all three retained installer
shell syntax checks. The 6.12 jobs' faulthandler reports contain a main-thread
native segmentation fault with **no Python frame**, after the pytest summary.
They provide no specific Python callback or test-lifetime fix to apply.

This establishes a reproducible version-specific project interaction, not a
confirmed upstream Qt defect. Test QApplication ownership and native object
destruction remain possible contributors. No speculative production or test
lifetime workaround has been applied.

### Supported dependency bounds

The `desktop` Essentials and `screen` Addons requirements now both use
`>=6.8,<6.12`; keeping these bounds paired avoids an optional screen dependency
silently selecting the excluded release. The required Python 3.12 CI job selects
the demonstrated working **6.11.2** explicitly and retains faulthandler, C++ tests
and shell checks. The failing version was removed from the supported matrix;
its failure was not converted to success or ignored with `continue-on-error`.
This does not claim that every older allowed version was tested in this run.

No developer-host pip, package, service or boot changes were made for this repair.
A fresh install will resolve within the source bounds; an existing manually
installed 6.12 environment needs its own reviewed downgrade before support can
be claimed. Further 6.12 lifetime isolation is deferred. Revisit the cap only
after a controlled full suite, native UI smoke and interpreter teardown succeed;
matching test assertions alone are insufficient. A fresh required hosted run
must verify the final bounded revision before the CI checkpoint is closed.

### Supported hosted checkpoint verified — 2026-10-21

Read-only `gh run view`/`gh run list` checks confirm complete successful runs,
including normal Python process exit, historical C++ tests and installer syntax:

| Source revision | Required hosted run | Result |
| --- | --- | --- |
| `6a7f6ee` (paired supported dependency bounds) | [39598212234](https://github.com/Aryan1771/ai-os/actions/runs/39598212234) | Success |
| `82e89b2` (fixed UKI metadata inspection) | [39599110437](https://github.com/Aryan1771/ai-os/actions/runs/39599110437) | Success |
| `945f3fc` (planner dispatch deadline) | [39600496127](https://github.com/Aryan1771/ai-os/actions/runs/39600496127) | Success |

The required supported-version CI checkpoint is complete for these revisions.
The excluded 6.12 teardown interaction remains unresolved; this does not turn its
earlier failures into passes. Later source changes require their own results.
Hosted checks are not physical microphone, GPU, desktop, boot or ISO acceptance.

### Enrollment test fixture regression — 2026-10-21

[Run 39603184949](https://github.com/Aryan1771/ai-os/actions/runs/39603184949)
for `90e41f0` crashed during native Settings rendering on the supported 6.11.2,
before completing Python tests; C++ and syntax stages were skipped. This is
distinct from the earlier excluded-6.12 post-summary crash. Root reproduced the
same mid-suite failure locally under Python 3.14.8 / PySide6 6.11.2; faulthandler
identified `tests/test_native_ui.py:58` during event processing.

Two reduced sequences each run one fake-input enrollment test followed by native
page rendering. Both reproduced a bus error (exit 135). An independent event
probe identified deferred deletion of the completed metadata `FakeScan`; the
QApplication instance was unchanged. Flushing that owner's deletion before its
Python fake-process fixture teardown allowed normal exit.

The targeted test cleanup now rejects the enrollment owner, asserts its timers
are inactive, deletes that owner while its fake class/instances are still alive,
and verifies the destroyed signal plus invalid owner/child wrappers. It does not
drain unrelated events, add timing sleeps, skip rendering or alter production
cleanup. Both reduced sequences pass after correction. A final frozen-source
suite passes **1290 tests in 16.64s**, with normal exit, including six explicitly
supplied pinned Plymouth interpreter tests and the following boot-artwork source
checkpoint. Correctness lint and whitespace checks pass. A hosted rerun must
still establish later revisions' remote acceptance.

[Run 39606303461](https://github.com/Aryan1771/ai-os/actions/runs/39606303461)
for the fixture repair `3132e4a` completes successfully under Python 3.12 /
PySide6 6.11.2. Its Python, historical C++ and installer syntax steps all pass.
This closes the demonstrated fixture regression for that revision; it does not
resolve the distinct excluded-6.12 interaction or accept later source changes.

The subsequent source-artwork revision `7d5b138` also completes successfully:
[run 39606763037](https://github.com/Aryan1771/ai-os/actions/runs/39606763037).
This is required hosted source validation, not a host boot or VM test.

The guided phase/early-reap revision `d7417c7` completes all required steps:
[run 39610470745](https://github.com/Aryan1771/ai-os/actions/runs/39610470745).
Python, historical C++ and syntax checks pass with normal process completion.
Personal microphone operation is still unaccepted; source CI is not its proof.

Both disabled-primary styling `4191283` and private diagnostic status `818064b`
complete successfully in required hosted CI:
[39611842565](https://github.com/Aryan1771/ai-os/actions/runs/39611842565),
[39613110856](https://github.com/Aryan1771/ai-os/actions/runs/39613110856).

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
