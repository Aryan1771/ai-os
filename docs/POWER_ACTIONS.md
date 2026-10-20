# Reviewed shutdown and restart

2026-10-20. The model can propose `power_action` (`poweroff`, `reboot`, `cancel`),
never confirm or directly execute it. An omitted delay opens a native minute
picker (0–1440); zero means now. The next default-No dialog shows the exact
action, relative delay and argv. Ordinary command forms such as `shutdown +5`,
`poweroff`, `reboot` and `systemctl poweroff` enter the same review even when a
command grant exists. Conflicting times/flags, force flags and privilege wrappers
are rejected. This is not universal support for every shutdown option.

After native approval, the bridge runs `/usr/bin/shutdown --no-wall --poweroff +N`
or `--reboot +N`, with `shell=False`, no input/output logging and a ten-second
bound. Cancellation runs `/usr/bin/shutdown --no-wall -c` and needs its own review;
it can affect an existing system-wide schedule. A chat **Stop** does not cancel an
accepted shutdown. Save work before approving. A spoken “yes” is not a substitute
for trusted native confirmation.

Success means the OS accepted the request, not that power-off was observed.
Authentication, policy and inhibitors can still deny it; errors say so instead
of claiming success. REgenOS does not bypass them. See the official
[systemd shutdown manual](https://www.freedesktop.org/software/systemd/man/latest/shutdown.html).

Validation: `python -m pytest -q tests/test_power_actions.py` passes 36 cases,
including exact argv, proposal-only registration, native bridge separation,
time bounds, errors and no execution without approval. Every power subprocess is
mocked. Only `shutdown --help` was inspected on this host; **no shutdown, reboot,
schedule or cancellation was executed**. Physical acceptance needs a separate
explicitly approved, save-work test. Installer/VM acceptance is not established.
