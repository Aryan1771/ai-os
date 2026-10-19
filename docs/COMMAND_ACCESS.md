# Native command access and companion behavior

## 2026-10-19 interactive commands and recoverable cleanup

`run_terminal_command` proposes installed binary argv/cwd and 1–900s for a default-No
native review in supervised mode. Launch is never a model tool; ordinary-user grants
cannot approve it. The exact reviewed program opens in a visible terminal. Sudo
elevates that program after OS authentication there; never enter passwords in chat.
The fixed timeout foreground helper bounds its direct target, not every privileged/
background descendant. Unconfirmed cleanup is reported. Disk/mount/boot/shell/script
guards remain: this broadens support without promising every possible Arch command.

`terminal_task_status(job_id)` exposes bounded status/exit metadata, never passwords
or terminal output. Launch acceptance is not completion; private argv specs are
single-use and removed after execution. Chat Stop/Steer now unwinds ordinary bounded
command cleanup before a new child starts. Completed actions and separately approved
terminal jobs are not undone. Two harmless private PTY checks pass; no real sudo job.

Requested clutter cleanup uses [native Trash previews and narrowly remembered rules](RESEARCH_AND_CLEANUP.md).
No user's files were removed in validation. Voice identity approves neither path.

## 2026-10-17 command and voice error repair

`run_command` already accepts arbitrary installed noninteractive programs as an
argv list. It is not a finite catalog to which every Arch executable must be
added. The model now receives explicit instructions to discover commands, inspect
local help and paths, choose `cwd`, execute, and ground its answer in results.
`cd` is a shell builtin: pass the directory as `cwd` rather than trying to launch
`cd`. Shell pipes/redirection are not interpreted with `shell=False`; use separate
tool steps, or a specifically reviewed shell invocation when needed. Commands do
not have a terminal/stdin and are limited to 60 seconds. Interactive jobs, ongoing
services, privileged installation and every possible task are not promised.

New `list_directory(path, limit)` is available through tool discovery. It reads
bounded names/types/sizes without file contents, recursion, symlink targets or
following entry symlinks. Relative inspection paths start from home. `run_command`
defaults to the user's home; an explicit `cwd` expands `~`. Grants and native
review use the same default, with native approval showing the resolved directory.
Broad-grant commands can now start in existing readable system directories such
as `/usr`, while the system tree remains **read-only**. This does not authorize
system writes or mounting anything. Home stays writable and `/tmp` stays private.

The new Linux runner caps combined captured output at 64 KiB, stops excessive
output with a failure result, closes stdin, uses `shell=False`, and kills its
process group on timeout and cleanup. This bounds ordinary descendants; it is
not proof against every deliberately detached/escaping program. Kernel, user,
service and Bubblewrap restrictions still apply. Missing executable, inaccessible
cwd and other OS errors return failure instead of crashing the request.

To enable the mode, choose **Permissions → Full access mode — time-limited ordinary
user commands**, then press **Enable full access mode…**. Inspect the stated scope,
choose a duration, and confirm the default-No native dialog. This creates a grant
for the default session (including voice). **Revoke full access** clears grants.
The mode dropdown alone does not grant command access. The assistant cannot
activate its own grant.
This checkpoint did not enable a grant or change command-access settings for the
user. Diagnostic/directory tools do not need a broad grant.

Voice worker errors now retain a sanitized diagnostic code for transcription,
model connection/HTTP/timeout, reasoning or speech playback; no exception text,
transcript or raw command output is copied into these diagnostics. Known blank
Whisper markers produce no utterance instead of a worker restart. A failed worker's
specific error survives supervisor cleanup/retry, until a successful reply or
explicit stop clears it. `python -m ai_os.runtime_health` exposes the code, selected
command mode and boundary availability. These are debugging improvements, not a
confirmed repair of the user's unspecified error. At inspection time the status
was freshly `armed` with no recorded error. The exact user-visible error remains
requested. Host audio/model access is unavailable inside this sandbox.

Validation:

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q \
  tests/test_command_navigation.py tests/test_command_risk.py \
  tests/test_desktop_access.py tests/test_personal_interaction.py \
  tests/test_listener.py tests/test_interaction_harness.py tests/test_access_grants.py
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q --tb=line
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests
```

108 focused tests pass. Full suite: 270 passed, 1 failed, 7 errors; all unsuccessful
checks require local socket operations denied by this execution environment.
A harmless real `run_command(['/usr/bin/pwd'], cwd='/usr', user_sandbox=True)`
returned success, exit 0 and `/usr` inside Bubblewrap. No broad grant was activated
by this smoke check. No private file content, device, service or package was changed.
Live voice and model-selected multi-step command acceptance remain pending. No
service restart, commit, push, ISO build or publication was performed.

The current native interface also offers an expiring **Broad user access** grant,
with a Bubblewrap boundary and separate approval. See [INTERACTION_HARNESS](INTERACTION_HARNESS.md)
for its exact scope, limitations and pending host acceptance. Earlier scoped grants
below retain their narrow behavior.

2026-09-28. Use REgenOS Settings → Conversation or the REgenOS terminal entry;
bare Ollama bypasses these tools, memory and permissions.

## Applications and commands

`Open Brave browser` routes directly to a dedicated launcher, without asking the
model to invent a shell command. Explicit site requests such as `Open YouTube`,
`Go to example.org` and `Open YouTube on Brave` now route deterministically to
the website tool; ordinary text requests no longer depend on the model choosing
that tool correctly. The URL is opened via the desktop's default browser, or a
named installed Brave/Firefox/Chromium/Chrome/Edge desktop entry. Browser lookup
covers system, user-local and Flatpak-exported desktop files. Application
discovery reads standard system/user/Flatpak application directories; launch
still accepts only an exact discovered desktop ID (or a reviewed built-in alias)
and no model-supplied executable path, URL or flags. Gio returning success only
means it accepted a launch request; it does not prove that a visible browser
window or loaded page appeared. Graphical session environment is required.

The model receives tool argument examples. `command_help(command="pacman")` reads
installed man pages with a fixed pager and timeout. `run_command` accepts argv
for installed commands beyond the diagnostic allowlist; it is not a promise to
know every command, install missing tools, or successfully perform every task.

In Settings → Permissions select **Full access mode — time-limited ordinary user
commands**, then choose **Enable full access mode…** and confirm a duration/scope.
Changing the saved mode always requires confirmation, even when the general
settings confirmation guard is off. Outside an active grant, each non-diagnostic
command proposed in native chat displays its exact argv, working directory and
timeout in a plain-text dialog, defaulting to No. Denial executes nothing.
Approval submits that exact command to the child bridge; no model inference takes
place between approval and execution. **Revoke full access** clears grants;
select Restricted and Save to disable this UI capability.
The default remains Restricted; this checkpoint did not enable it for the user.

Terminal requests retain per-action human approval unless a confirmed applicable
grant exists. Background voice requests without such a grant fail closed or leave
a pending request for native review. Model-supplied
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

## One-command and timed access grants

Enable supervised command access in Settings → Permissions first. Then use these
phrases in the REgenOS conversation or terminal (not bare Ollama):

- `I give you full access to this command` requests one execution of the most
  recent pending command in that session. Request the action first. The pending
  command expires after two minutes; approval binds its argv, directory and timeout.
- `I give you full access for 30 seconds`, `five minutes`, `1.5 hours`, or
  `1 hour and 30 minutes` requests a timed grant. Supported durations are 1 second
  through 24 hours, using seconds/minutes/hours and common English number words.
- `revoke access` clears grants and pending requests for the current session.
  `revoke all access` clears them for every session.

The phrase requests permission; it does not itself activate access. In native
Conversation, choose **Review access request**, inspect the scope or exact command,
and confirm the default-No dialog. Terminal users receive a human consent prompt.
Voice requests await native review because microphone input does not prove identity.
The model cannot create or confirm grants through its tool registry.

Timed scope is deliberately limited to audited diagnostics and new-file
`mkdir`, `touch`, and `cp` operations below `~/Documents`, `~/Downloads`, or `/tmp`.
It excludes hidden paths, runtime data, overwrites, deletion, sudo, shells, scripts,
package/service changes and protected disk access. Other commands still need
individual approval. Executables are pinned to `/usr/bin`; copy adds
`--no-clobber`. This is application-level checking, not race-proof filesystem
isolation or an OS sandbox. An exact-command grant can authorize a broader reviewed
command once, but cannot override prohibited-command checks or OS permissions.

The Conversation panel shows the selected session's countdown and **Revoke access**.
The companion shows default-session access state and offers **Revoke all access
grants** in its menu. Voice uses the default session. Changing the saved command
access mode revokes all grants. Grants survive client restarts during their duration,
but expire on reboot or their monotonic/wall-clock deadline. Pending confirmations
expire after two minutes and use single-use tokens. One-command claims are atomic
and consumed even if execution fails. Revocation blocks future claims; it does not
cancel already-started commands or undo their effects.

State is local at `~/.ai_os/run/private/access.sqlite3` (directory 0700, file 0600).
Same-account processes are not isolated from that state or the native bridge.
Do not interpret this feature as unattended unrestricted root access.

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
