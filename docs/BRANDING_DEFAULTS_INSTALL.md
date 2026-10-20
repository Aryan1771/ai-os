# Staged desktop and GDM branding installer

`scripts/install_branding_defaults.py` implements stages 1 and 2 of
[the reviewed proposal](REGENOS_BRANDING_PROPOSAL.md). Source implementation and
disposable-root tests are complete. **The owner separately approved and executed both host stages and `dconf update`
on 2026-10-20. All nine installed 0644 files match reviewed sources; compiled
regenos/GDM databases exist and the GDM logo key resolves correctly. Private
rollback backups remain on the host; no rollback or GDM restart was run.** This changes desktop defaults and a supported greeter logo; it does
not install an operating system or establish ISO acceptance.

## Read-only review

From the checkout, using the existing venv:

```sh
~/.ai_os/venv/bin/python scripts/install_branding_defaults.py --plan --root / --stage desktop
~/.ai_os/venv/bin/python scripts/install_branding_defaults.py --plan --root / --stage gdm
```

`--plan` is the default action. It creates no directories or backups and runs no
commands. The plan records destination fingerprints, intended asset hashes,
profile additions and a `plan_sha256`. The apply operation recomputes that digest
and refuses stale source assets or destination state.

On 2026-10-20 the desktop plan found all seven destinations absent. Its digest
was `2a3fd1499ba17715861d18ba3767fa072c3a87c02658930100b1753c5a31bc6a`.
Before desktop installation, the GDM plan exited 1 with `Install the reviewed desktop art stage before the GDM
logo stage.` This is the expected dependency gate, not a GDM hardware test.
Re-run review before any apply; the recorded digest is evidence, not evergreen
approval.

## Exact scope

The `desktop` stage installs these regular source assets, with an additional
`lockscreen.png` only when that reviewed source exists:

```text
/usr/share/regenos/branding/regenos-mark.svg
/usr/share/regenos/branding/regenos-mark.png
/usr/share/regenos/wallpapers/default.png
/usr/share/regenos/wallpapers/lockscreen.svg
/usr/share/icons/hicolor/scalable/apps/regenos.svg
```

It adds `/etc/dconf/db/regenos.d/90-background` and merges `system-db:regenos`
after `user-db:user` in `/etc/dconf/profile/user`, retaining existing profile
lines and their order. A custom first user database or `DCONF_PROFILE` override
requires separate review. These are unlocked defaults: existing per-user
wallpaper choices retain priority. The lock-screen file is shipped art, not a
claim that GNOME consumes a separate lock wallpaper.

The separate `gdm` stage requires the installed mark to match the reviewed source.
It installs `regenos-wordmark.svg` and `regenos-wordmark.png` under
`/usr/share/regenos/branding/` and points GDM at the compact PNG. The intended
asset is144×48; the installer refuses square/oversize input, missing SVG intrinsic
dimensions, height over 64, width over 192, or proportions outside approximately 3:1.
GNOME 51 uses natural size: the 512px app icon is not a safe greeter asset.
It creates `/etc/dconf/db/gdm.d/90-regenos-logo` and merges the supported GDM
profile databases in `/etc/dconf/profile/gdm`. It never restarts GDM or ends a
session. No stage changes user preferences, locks, PAM, os-release, boot files,
packages, services, autostart or disks. No shell or subprocess is invoked.

## Apply only after approval

Both write actions require an explicit existing `--root`. The actual system root
also requires UID 0. The script uses only Python's standard library; it does not
install dependencies or modify system Python. A reviewed desktop apply has this
form, with the digest copied from the fresh reviewed plan:

```sh
sudo -- /usr/bin/python scripts/install_branding_defaults.py --apply --root / --stage desktop --expected-plan REVIEWED_DESKTOP_SHA256
```

Do not run that placeholder command. The coordinating executor must first
present the concrete fresh digest and get approval for that stage. After a
successful apply, separately review and approve `sudo -- dconf update`. The
installer prints that follow-up; it does not execute it. Check defaults using a
fresh profile or the next ordinary login, without resetting the owner's keys.

Only then produce a fresh GDM plan and obtain separate approval for:

```sh
sudo -- /usr/bin/python scripts/install_branding_defaults.py --apply --root / --stage gdm --expected-plan REVIEWED_GDM_SHA256
```

The GDM stage also needs its approved `dconf update`. Inspect the logo at the
next owner-initiated login. Do not restart the display manager to preview it.

## Backups, refusal and rollback

Before replacing any destination the installer saves all previous regular files
under `/var/lib/regenos/branding-backups/BACKUP_ID/`, with a private mode-0700
backup directory and mode-0600 manifest/files. The manifest records previous
bytes, modes, owner, modification time, absence, and installed hashes/fingerprints.
All source, destination, target-root and parent symlinks are refused for manual
review. Paths outside the fixed branding whitelist cannot be restored.

Save the returned backup ID privately. Roll back GDM before desktop art because
the GDM logo depends on the latter. After separate owner approval:

```sh
sudo -- /usr/bin/python scripts/install_branding_defaults.py --rollback RECORDED_BACKUP_ID --root /
```

Rollback preflights every destination before restoring any file, verifies backup
hashes, and refuses later asset edits. For a previously existing profile it may
remove only the uniquely identified added lines while preserving later additions;
changed or deleted original lines require manual review. If a newly created
profile was subsequently edited, rollback refuses before any restoration so it
cannot remove a user-database dependency needed by the later lines. Unchanged
files are restored with their original mode/owner/time, or removed if originally
absent. Backups and any empty newly created directories remain. Review and approve
`dconf update` after rollback as well.

Each file replacement is atomic; the multi-file operation is not a filesystem
transaction. A normal apply failure or interrupt attempts to recover only its
unchanged writes and records `failed_recovered` or `failed_needs_review` in the
private manifest. It never overwrites a later edit during recovery. A hard process
kill, power loss, rollback write failure or concurrent edit during rollback needs
inspection of that private manifest before any retry. Do not delete the backup
or blindly rerun an apply to resolve a partial failure.

## Verification

```sh
~/.ai_os/venv/bin/python -m pytest -q tests/test_branding_defaults.py --tb=short
~/.ai_os/venv/bin/python -m ruff check scripts/install_branding_defaults.py tests/test_branding_defaults.py
```

Result: 33 tests passed in disposable roots, covering read-only planning, explicit
write gates, stale-plan refusal, symlink refusal, private backups, staged
dependencies, exact restoration, guarded profile merging, later-edit refusal,
checksum tampering and recovery after an injected write failure. These tests do
not execute dconf, log in to GDM, test a lock screen, build an ISO or verify boot.
Asset redistribution terms remain the separate release gate recorded in the
branding proposal.

## Approved host follow-up

After desktop installation, the fresh two-file GDM plan was
`5ce984567051387570150e920ddac66ac9b1f111403a7170e21ddd54f7ee9757`; the owner
separately approved and executed it and dconf update in their own terminal.
Fresh readback verifies both source files and the compiled logo key. Existing
owner wallpaper still selects its original file; no preference reset occurred.
The current login session was preserved. New-user defaults and visual logo
acceptance need the next ordinary owner login; no login, lock or boot visual pass
is inferred from configuration readback. Bootloader/initramfs changes remain
unapproved and recovery verification remains open.

## Password-area layout regression and requested correction

The first two-file GDM stage installed correctly but failed owner visual testing:
the 512×512 app icon obscured the password area. Readback did not establish layout
acceptance. The new four-file GDM stage installs separate compact wordmark assets
and updates the logo key, preserving its profile. It creates a fresh private
backup of the old GDM configuration. Current corrective plan:
`e26d1419c5cdd8ba7b68315478d3f183b2f541add69a22e423030830a336646e`.
The owner requested this fix under the existing GDM authorization; terminal
execution and a fresh password-field visibility check are still pending. No
GDM restart/logout, PAM change or password-unmasking is required. See
[the installed GNOME code investigation](LOGIN_LOGO_FIX.md).
