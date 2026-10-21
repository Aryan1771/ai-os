# Boot and recovery inventory

The read-only helper prepares a boot-branding/recovery proposal. It does not
change a boot entry, mount, file, package, service, EFI variable or disk. It is
not a model tool and cannot approve later changes. Recovery remains unverified
until a separate known entry/image has actually been boot-tested by the owner.

```bash
~/.ai_os/venv/bin/python scripts/inspect_boot_branding.py
```

For the separately approved elevated **inspection**, the owner can run these
commands in the same terminal. The helper uses `sudo -n` only and never asks for
or receives a password. It preserves the terminal session while placing each
child in an owned process group for bounded cleanup:

```bash
sudo -v
~/.ai_os/venv/bin/python scripts/inspect_boot_branding.py --sudo
```

Do not run the whole development venv as root to work around authentication.
The coordinating executor may not share the owner's terminal credential cache.
Custom sudo policy can still prevent reuse. Known authentication/policy failures
stop further elevated commands once, with a fixed `sudo_reason`; generic warnings
are not automatically classified as authentication failure. Raw stderr is withheld.

## What the report establishes

All subprocess output shares a **1 MiB** limit and a **10-second** deadline.
Commands use fixed executable/argument lists, `shell=False`, no interactive stdin,
a minimal environment and verified child-group cleanup. The only commands are
read-only `uname -r`, selected-column `findmnt`, fixed-directory `ls`, fixed-file
`cat` and known-image `stat`, plus `bootctl --no-pager status`. Optional sudo is
used only for boot status/directories/files/image metadata; public metadata and
readable `/etc`/`/proc` configuration do not need elevation. Nothing is mounted.

| Field | Meaning and limit |
| --- | --- |
| `read_statuses` | Fixed requested path plus readable/not-found/permission-denied/not-directory/unavailable/budget status. Permission denied never means absent. Unknown/custom filenames are not exported or followed. |
| `mounts` | Known requested/actual mount target, whether the match is exact, filesystem type, total/available bytes and read-only flag. No source device, UUID, label, UID or raw mount options. `read_only: false` describes existing metadata; it performs no writable mount. |
| `running_kernel_release`, `current_boot` | Sanitized current kernel release, optional recognized `BOOT_IMAGE`, and quiet/splash/Plymouth-disable booleans. Other command-line values, root arguments and identifiers are discarded. No `BOOT_IMAGE` means this source cannot identify an image. |
| `presets` | Literal enabled `PRESETS`, known kernel image and default/fallback/recovery image/UKI declarations. `enabled: false` means an inactive declaration; `null` means dynamic/custom/missing activation could not be resolved. Presets are never sourced or executed. |
| `grub_defaults` | Safe static default kind/ordinal and presentation flags only. A saved/custom name is withheld. A configured default is never treated as the currently booted entry. |
| `grub_configs` | Bounded static menu/submenu ordinals, normal/fallback/recovery/unknown title hints, Linux/initrd versus chainloader form, known image paths and presentation booleans. Titles, IDs, search devices and root arguments are omitted. |
| `initramfs_hooks` | Known literal hook names/order and an unknown-hook count. Custom names, sourced/dynamic interpretation and compatibility are not established. |
| `image_files`, `fallback_images` | Known candidate path with explicit read status, regular/symlink/directory kind and size. Fallback lists require a nonempty regular file; a preset reference or directory listing alone is insufficient. No size/type result proves bootability. |
| `current_image_evidence` | Optional recognized path reported in bootctl's **Current** loader/stub section, with a fixed source/confidence label. It is not inferred from default entries or presets and does not establish the on-disk file, partition identity, signature, kernel contents or recovery. |
| `active_entry`, `recovery_boot_verified` | Remain unknown/false. The helper does not execute or fully interpret GRUB, boot a recovery entry, or certify rollback. |

Static GRUB ordinals count visible declarations, including submenu positions;
they are not verified runtime menu indices. Conditional/generated/function or
external configuration is marked uncertain; inline/custom bodies and unrecognized
paths are intentionally incomplete. Shell expansion is never evaluated. Menu
title words such as “fallback” are classification hints, not recovery evidence.
GRUB paths such as `/EFI/Linux/arch-linux.efi` can be relative to the loader's
filesystem, which is not proven to be the host's `/` filesystem. No arbitrary
custom path is added to the read allowlist from configuration content.

## Current-stub evidence

The official systemd documentation distinguishes the bootloader's
`LoaderImageIdentifier` from the UKI's `StubImageIdentifier`, available since
systemd 257. Therefore missing `BOOT_IMAGE` does **not** prove that all current-UKI
evidence is absent. [systemd-stub EFI variables](https://www.freedesktop.org/software/systemd/man/latest/systemd-stub.html).

Reviewed upstream bootctl code prints these in separate current-loader and
current-stub sections. The helper accepts only known EFI paths under the expected
field labels, and requires a recognized systemd-stub product for stub evidence.
Unknown versions/formats/filenames remain unknown; private EFI IDs and URLs are
dropped. No raw EFI-variable enumeration or write is performed.
[upstream bootctl status implementation](https://github.com/systemd/systemd/blob/main/src/bootctl/bootctl-status.c).

## Focused UKI metadata checkpoint

The optional `--uki` mode reads exactly `/boot/EFI/Linux/arch-linux.efi` instead
of repeating the full inventory. It cannot accept an arbitrary filename. Its
three fixed commands are `uname -r`, `bootctl --no-pager kernel-inspect` for that
path and `objdump --section-headers --section=.splash --` for that path. These
share the existing 10-second/1-MiB budget, shell-free execution and owned-group
cleanup. The default inventory's command scope is unchanged. No section is
extracted, rendered, saved or modified; no EFI variable is read by this mode.

After approval of any required elevation, the owner can run:

```bash
sudo -v && ~/.ai_os/venv/bin/python ~/src/ai-os/scripts/inspect_boot_branding.py --sudo --uki
```

Only the helper's sanitized JSON should be shared. Do not run `kernel-inspect`
directly and paste its raw output: it can include embedded root UUIDs and other
private kernel arguments. The report retains only a known image-type enum, a
bounded kernel release, whether that release equals the running release, a known
OS-family enum and quiet/splash/Plymouth-disable booleans. Unknown/custom text and
all raw command lines are withheld. A release match is metadata evidence, never
proof that this disk file is the image which booted.

`splash` reports presence and section size only when the complete expected PE
header format is recognized. Permission errors, unknown output, multiple rows,
truncation and budget failures leave presence unknown, rather than reporting
absence. Section addresses, raw flags and private stderr are discarded. A
present section is not proof of its artwork, rendering or selected boot profile.
The official systemd documentation describes `.splash` as an optional BMP shown
before kernel invocation. Thus a startup logo may be independent of GDM and
Plymouth; this inspection tests that possibility without changing the boot path.
[systemd-stub sections](https://www.freedesktop.org/software/systemd/man/latest/systemd-stub.html),
[bootctl inspection](https://www.freedesktop.org/software/systemd/man/latest/bootctl.html),
[upstream output labels](https://github.com/systemd/systemd/blob/v260/src/bootctl/bootctl-uki.c),
[GNU objdump section headers](https://sourceware.org/binutils/docs/binutils/objdump.html).

On 2026-10-21, the focused source checkpoint passed **95 mocked tests in 0.13s**
across `tests/test_boot_inventory.py`, plus correctness Ruff and whitespace
checks. The suite includes 35 new cases for metadata privacy, complete/absent/
unknown sections, authentication denial, failed reads with partial output,
global-budget stops and fixed opt-in CLI dispatch. Exact verification commands
are in the source checkpoint below. No actual privileged UKI inspection, host
boot write, package/service change, download or disk operation was run for this
source checkpoint. The owner subsequently supplied the focused report below.

### Owner's focused UKI report — 2026-10-21

The owner ran the separately approved `--sudo --uki` command in their terminal.
All three fixed reads completed. Sanitized results establish:

- The known file is recognized as a UKI with Arch OS-family metadata and an
  embedded command line. Its kernel version, `7.2.10-arch1-1`, matches the running
  release; embedded `quiet`, `splash` and Plymouth-disable flags are all false.
- A `.splash` section is present, **378,226 bytes**. This establishes embedded
  splash data, not the pixels it contains or whether firmware displayed them.
- Active entry, exact identity of the booted disk file and independent recovery
  remain unverified. A version match alone cannot establish any of those.

This is owner-provided hardware inspection evidence, separate from mocked tests.
No raw boot arguments, device identifiers or image contents are retained. There
was no image extraction, rebuild, boot write, mount, package/service change or
reboot. Embedded splash artwork is a supported candidate for the reported startup
logo; changing GDM does not replace it. A concrete recovery and activation plan
and separate boot approval are still required before any host image changes.

## Source checkpoint and nonprivileged result

On 2026-10-20:

```bash
~/.ai_os/venv/bin/python -m pytest -q tests/test_boot_inventory.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F \
  scripts/inspect_boot_branding.py tests/test_boot_inventory.py
git diff --check -- scripts/inspect_boot_branding.py \
  tests/test_boot_inventory.py docs/BOOT_RECOVERY_INVENTORY.md
```

**60 mocked tests passed in 0.09 seconds**; correctness lint passed. They cover
sanitized fixed reads, terminal-cache context, child cleanup, output/time limits,
missing versus denied paths, enabled versus inactive/dynamic presets, nested
static ordinals, chainloaders, private-data omission, current-stub/default
separation and mount/image metadata. No test invokes an actual privileged command.

After those tests, one nonprivileged helper execution completed in **0.157 s**
with `status: partial_inventory`. It reported:

- Running kernel `7.2.10-arch1-1`; no `BOOT_IMAGE`, `quiet` or `splash`.
- `/`: ext4, 249,845,608,448 total bytes and 188,299,341,824 available bytes.
- `/boot`: exact existing vfat mount, 1,071,624,192 total bytes and 712,892,416
  available bytes; existing mount is not read-only. These are point-in-time values.
- `linux.preset`: only `default` enabled; default UKI
  `/boot/EFI/Linux/arch-linux.efi`; fallback UKI assignment
  `/boot/EFI/Linux/arch-linux-fallback.efi` is **inactive**.
- `linux-zen.preset`: only `default` enabled; initramfs
  `/boot/initramfs-linux-zen.img`.
- All six known boot-image probes returned **permission denied**. The current
  helper execution could not read bootctl/current-stub evidence or GRUB contents.
  It did not establish image absence, an active menu entry or recovery.

The owner's earlier elevated helper report identified GRUB, but that older
partial inventory did not map enabled presets, read statuses or current-stub
paths. Its referenced fallback path alone is not proof a fallback was generated.
No elevated retry, boot write, service action, rebuild or download was performed
for this checkpoint. The public result must not replace an elevated owner report
with guesses.

## Owner's subsequent elevated report

The owner subsequently supplied sanitized output from the full elevated helper:

- Current-stub evidence reports `/EFI/Linux/arch-linux.efi`; the current-loader
  field reports `/boot/EFI/Linux/arch-linux.efi`. These firmware-reported paths
  do not establish the on-disk image's identity or a selected GRUB menu entry.
- The known UKI is a readable regular file of 154,340,352 bytes. The known
  fallback UKI and plain linux initramfs explicitly report **not found**.
  Zen's initramfs and both kernel files are readable; none is recovery-tested.
- GRUB is reported, but the parsed custom/unknown entry remains unresolved.
  Only default presets are enabled; no Plymouth hook is present. Current flags
  omit `BOOT_IMAGE`, `quiet` and `splash`.
- `/boot` has 712,892,416 bytes available of 1,071,624,192 bytes at inspection.
  It is an existing vfat mount; this is not a new mount or free-space guarantee.

This supersedes the earlier permission-denied observations for those files; it
does not establish an active entry, UKI contents or independently bootable
recovery. No full boot configuration, device identifiers or raw logs are stored.

## Remaining gate before a boot-change proposal

Review the focused UKI metadata report and resolve custom/unknown entries through
separately reviewed fixed reads; do not expose complete private boot configuration
or identifiers. Metadata alone must not be promoted to boot or recovery acceptance.
Confirm which existing image/entry is the working boot path, and establish an
independent usable recovery entry/image that the planned change will not rewrite.

Then present exact package/files/hook family/preset outputs/free-space budget,
private backups and key/file-specific rollback for approval. Test the Plymouth
theme and recovery behavior in a disposable VM first. Read-only inventory approval
does not authorize installing Plymouth, enabling fallback generation, rebuilding
initramfs/UKIs, regenerating GRUB, bootloader/EFI writes, mounting or rebooting.
Do not touch the Windows disk or the working development SSD as installer targets.
