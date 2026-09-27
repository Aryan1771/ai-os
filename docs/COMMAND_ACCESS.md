# Native command access and companion behavior

2026-09-28. Use REgenOS Settings → Conversation or the REgenOS terminal entry;
bare Ollama bypasses these tools, memory and permissions.

## Applications and commands

`Open Brave browser` now routes directly to a dedicated launcher, without asking
the model to invent a shell command. Supported installed system desktop entries:
Brave, Firefox, Files (GNOME), Terminal (Kitty) and GNOME Settings. The launcher
accepts no URLs, flags or arbitrary desktop files. It reports a launch request,
not proof that a visible window appeared. Other apps can be requested through
the reviewed command path. Graphical session environment is required.

The model receives tool argument examples. `command_help(command="pacman")` reads
installed man pages with a fixed pager and timeout. `run_command` accepts argv
for installed commands beyond the diagnostic allowlist; it is not a promise to
know every command, install missing tools, or successfully perform every task.

In Settings → Permissions select **Full command access — approve each change**
and Save. Changing this setting always requires confirmation, even when the
general settings confirmation guard is off. Each non-diagnostic command proposed
in native chat then displays its exact argv, working directory and timeout in a
plain-text dialog, defaulting to No. Denial executes nothing. Approval submits
that exact command to the child bridge; no model inference takes place between
approval and execution. Select Restricted and Save to revoke this UI capability.
The default remains Restricted; this checkpoint did not enable it for the user.

Terminal requests retain per-action human approval. Background voice requests
cannot display this native chat confirmation and fail closed. Model-supplied
`approve=true` is discarded. Full command access is supervised, not an unattended
root shell. Prohibited formatting/wiping patterns and direct disk device access
remain blocked. Sudo uses `-n`, stdin is closed, and password prompting is never
handled by chat. If authentication is unavailable, execute the reviewed action
in a real terminal. Privilege changes are still subject to OS policy.

This same-account application approval mechanism is not a hardened privileged
broker or complete sandbox. A reviewed interpreter/script may perform operations
that cannot be understood by argument matching. Never approve an opaque script
as a shortcut around restrictions. No AppArmor, firewall, sudoers or boot policy
was changed. Commands remain bounded to 60 seconds; cancellation cannot undo
already completed actions. Long-running administration needs a real terminal.

## Emotions and learning

Greetings now encourage a natural social response without unsolicited feelings
disclaimers. Model replies can provide six bounded emotion channels. Text cues
provide fallback warmth/concern/focus, including for voice transcripts. The
same expression metadata reaches the companion and speech activity. These are
simulated presentation values, not sentience or a diagnosis of the user. Acoustic
emotion recognition, expressive prosody and durable mood evolution are not added
by this change.

Explicit preferences and local conversation memory continue to provide adaptation.
Official manuals can now be downloaded deliberately and retrieved offline:

```bash
~/.ai_os/venv/bin/python -m ai_os.knowledge refresh pacman
~/.ai_os/venv/bin/python -m ai_os.knowledge refresh systemctl
~/.ai_os/venv/bin/python -m ai_os.knowledge search 'pacman install package'
```

Catalog: pacman, systemctl, journalctl, ip, lsblk, nmcli. Fixed HTTPS URLs on
`man.archlinux.org`, no redirects, bounded downloads, source URL/date/hash stored
under `~/.ai_os/data/knowledge`. Relevant bounded excerpts are added to model
context as untrusted reference data. Refresh is a human CLI operation, not a
model tool; it does not send private conversations online or run downloaded code.
Repeat refresh when documentation updates. Knowledge changes do not retrain
weights or autonomously modify source code. Installed man pages remain the
preferred source for locally installed versions. Context budgeting is still
approximate rather than tokenizer-exact.

## User appearance and remaining system branding

`scripts/apply_user_branding.py` builds the original Cool cursor and applies it
and the original wallpaper to GNOME, backing up appearance first. Current backup:
`~/.local/share/regenos/appearance-backup-h7dv8w3x`. The backup's `gsettings.json`
records exact previous GNOME values; restore each using `gsettings set SCHEMA KEY
VALUE`. Existing GTK/session fragments have `.regenos-backup` copies. Applications
may need reopening to pick up the cursor. This script never edits boot configuration.

The current `/etc/os-release` is a symlink to Arch's packaged file. Do not overwrite
its target. A future approved system-branding step should back up that symlink and
install an independent `/etc/os-release`, retaining upstream attribution and
package compatibility. Proposed display name: `REgenOS (Arch Linux prototype)`;
retain `ID=arch` for this installed development host. Install the REgenOS logo
system-wide in the same reviewed step. Boot splash requires a separate Plymouth
package/theme, review of the active initramfs hooks/bootloader, and recovery entry.
Login-screen branding needs a display-manager-specific plan. None is applied yet;
changing a cursor/wallpaper does not create a finished distribution.
