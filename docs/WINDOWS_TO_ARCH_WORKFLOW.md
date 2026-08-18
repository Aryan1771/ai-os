# Windows To Arch Workflow

Windows and the external Arch install normally cannot run at the same time on the same PC. Use GitHub as the bridge.

## Recommended Flow

1. Edit and commit this repo on Windows.
2. Push to GitHub.
3. Reboot into the external NVMe Arch system.
4. Clone or pull the repo.
5. Run the commands in `docs/ARCH_RUNBOOK.md`.
6. Paste logs back into Codex from a phone, browser, or another device.

## Optional Shared Partition

If you want offline transfer without GitHub, create a small exFAT partition on the external drive:

```text
EFI System Partition       FAT32
Arch root partition        ext4
Shared transfer partition  exFAT
```

Windows and Arch can both read exFAT. Arch root on ext4 is not normally writable from Windows without extra software.

