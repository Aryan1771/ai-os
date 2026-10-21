# Broad-command bootstrap isolation

Broad user grants require the existing Bubblewrap boundary. A source audit found
that its Python bootstrap could resolve an `ai_os` package in the command's chosen
working directory before reaching the real `ai_os.unprivileged_command` helper.
The previous invocation was `python -m ai_os.unprivileged_command ...` with that
directory as `cwd`; inherited `PYTHONPATH` could also affect module resolution.
This could run substituted bootstrap code before the namespace started.

A temporary shadow-package metadata probe and a stubbed command runner reproduced
the vulnerable resolution order. No payload, broad command, real grant or
Bubblewrap namespace was executed by that reproducer.

The bootstrap now uses the existing venv's interpreter with
`-I -m ai_os.unprivileged_command`. Isolated mode excludes the working directory,
ignores Python interpreter environment variables and excludes the user site.
The official Python command-line documentation defines `-I` as implying `-E`,
`-P` and `-s`, which supply those restrictions.
See [Python isolated mode](https://docs.python.org/3.14/using/cmdline.html#cmdoption-I).
The venv's installed package metadata remains available, including the reviewed
editable source mapping. The approved command's `cwd`, argv and timeout remain
unchanged for the real helper to place inside its boundary. An unavailable
installed helper fails with a command failure; there is no ordinary-execution
fallback. Individually reviewed commands outside a broad grant keep their
existing execution path.

Read-only import metadata from a neutral `/tmp` directory verified the actual
venv resolves the expected source helper with isolated, ignore-environment and
safe-path flags, and excludes cwd. Regressions also probe neutral/shadow cwd and
inherited `PYTHONPATH`, bogus `PYTHONHOME`, user-site and inspect settings. Those
child interpreters inspect origins and flags only; they never import the helper
or run a desktop command. Other runner tests stub all command execution.

```bash
~/.ai_os/venv/bin/python -m pytest -q tests/test_command_confinement.py tests/test_access_grants.py tests/test_command_risk.py --tb=short
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os/tools/system_tools.py tests/test_command_confinement.py
git diff --check
```

The focused source run passes 72 tests, including six new confinement checks;
correctness lint, full new-test lint and whitespace checks pass. The runner is
stubbed for all broad-command dispatch in this run.

This closes bootstrap lookup through cwd/interpreter environment. It does not
make same-account application code or its editable checkout immutable, isolate
private home files, authenticate a speaker, or create a hardened privileged
broker. The grant still requires trust in the local installation and programs,
expires/revokes according to its existing claim policy, and cannot undo completed
effects. Actual boundary/missing-package/expiry/revocation acceptance remains
separate from these source and import-metadata checks; no host security policy
or service was changed.
