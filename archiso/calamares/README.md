# REgenOS Graphical Installer Source

This directory contains the first Calamares integration sources: an Ubuntu-style
wizard sequence, REgenOS branding, a desktop launcher, and the expected install
image contract. Calamares is a Qt/Linux application; it does not replace the
Linux kernel or Arch base.

## Status: Not Yet An Installable ISO

These files are **not enabled in the Archiso profile** and are not a finished,
tested installer. The profile currently has no reproducible Calamares package
source, no `install-rootfs.squashfs`, and no tested Arch target image build.
`unpackfs.conf` expects that image at
`/usr/share/regenos/installer/install-rootfs.squashfs`. Do not add this config
to a release ISO or launch it against a real disk until all three are supplied
and the full flow has passed disposable-VM testing.

The image contract is intentional: it must be a clean installed REgenOS root,
not the live Archiso root copied wholesale. The final root image must exclude
live-session credentials, autologin, temporary mounts, installer packages,
developer data, and machine-specific state. Hardware drivers must be selected
through supported packages and first-boot detection rather than baked for one
computer.

## Wizard Flow

The UI collects language, keyboard, partitioning, account credentials and a
final summary. The execution sequence applies the partition plan, mounts the
target, unpacks the OS image, creates machine identity and fstab, configures
locale, users, networking and systemd, generates initramfs, installs a
bootloader, and unmounts. Calamares shows a final confirmation before disk
changes (`prompt-install: true`). Disk operations remain destructive once
approved; the UI must clearly identify the target disk and test cancellation
and failure recovery.

## Required Before Enabling

1. Package Calamares and every configured module from a pinned, reviewed source
   in a reproducible signed repository or clean-chroot build. Calamares is not
   added to `packages.x86_64.add` because the project has not established that
   source yet.
2. Build and inspect the clean target root image, and put it at the documented
   image path in the live ISO.
3. Add `/etc/calamares/settings.conf`, module configs, branding, the launcher,
   authorization agent and all runtime dependencies to the Archiso profile.
4. Confirm the selected bootloader, UEFI and portable-USB behavior, encrypted
   partition support, installed REgenOS runtime/services, and live-only account
   removal against the packaged Calamares version.
5. Boot and install only in disposable VMs first. Test UEFI, manual partitions,
   encryption, erase-disk warnings, cancel, power/failure recovery, low space,
   no network, and reboot into the installed OS. Never use the internal Windows
   disk or development SSD as an installer test target.

Calamares's sequence and branding formats are version-sensitive. The current
configuration follows the upstream structure, but must be checked against the
exact built package before enabling. See [Archiso and branding](../../docs/BRANDING_AND_ARCHISO.md)
and the [implementation checklist](../../docs/IMPLEMENTATION_CHECKLIST.md).
