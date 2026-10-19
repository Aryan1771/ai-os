# GNOME native application shortcuts

The old Desktop page listed Hyprland defaults even in GNOME. It now explains the
session distinction and offers a reviewed GNOME setup, separate from preferences:

| Keys | Native application |
| --- | --- |
| Super + Alt + A | REgenOS Settings |
| Super + Alt + C | REgenOS Chat |
| Super + Alt + R | REgenOS Companion, revealed with `--show` |

**Desktop → Review GNOME shortcuts…** first inventories supported GNOME schemas
and custom binding accelerators. Native approval defaults to No, with the exact
launch commands in Details. Conflicts refuse installation; existing Super+A,
Super+Space and other bindings are preserved. Cancelling keeps unsaved settings.
Inspection/application run in a bounded child so the native UI stays responsive.

Application binds only the three REgenOS-owned GSettings paths. It rechecks the
reviewed revision and current master list, writes a private backup first, then
verifies readback. A concurrent change aborts and attempts partial recovery without
removing unrelated additions. This is not a transaction with every desktop process;
do not concurrently edit shortcuts during installation. Partial recovery failures
are reported rather than claimed to have succeeded.

**Restore shortcut backup…** selects its original private JSON under
`~/.ai_os/backups/desktop-shortcuts/`. Confirmation is required. Rollback removes
only paths added by the operation and restores owned values, preserving unrelated
current bindings. It refuses to overwrite REgenOS bindings edited after setup.
The helper is trusted UI plumbing, never a model tool or independent OS auth boundary.

## Applied host checkpoint

The owner explicitly approved these three shortcuts on 2026-10-19. Fresh GNOME
inspection found no conflicts. Application and subsequent readback succeeded;
physical key presses remain owner acceptance. No system, service, boot, disk or
other desktop settings were changed.

Private backup ID: `1b32cb89af574ced9d092e35d3261e34`. The file is outside Git.
Current launch commands use the existing venv and explicit `AI_OS_HOME`; they do
not invoke sudo, a shell or service-control commands.

Read-only inspection:

```bash
~/.ai_os/venv/bin/python -m ai_os.desktop_shortcuts --action propose
```

The approved application used a fresh `propose_shortcuts(home)` result followed
by `apply_shortcuts(proposal, home=home, human_confirmed=True)` and a second
proposal for readback. Rollback, if requested, is:

```python
from ai_os.config import AI_OS_HOME
from ai_os.desktop_shortcuts import revert_shortcuts
result = revert_shortcuts("1b32cb89af574ced9d092e35d3261e34",
                          home=AI_OS_HOME, human_confirmed=True)
```

Run rollback only after approving it or through the native Restore control.
Physical app/extension shortcuts may introduce conflicts not represented in the
GNOME schemas; those remain a keyboard acceptance check.
