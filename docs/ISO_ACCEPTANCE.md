# REgenOS preview ISO acceptance

2026-10-21: **No ISO built or accepted.** There is no final artifact path/SHA256,
build manifest or VM result. Runtime source tests and graphical setup previews
are not installer or distribution acceptance.

| Gate | Status |
| --- | --- |
| Runtime quality/security | 1321 automated regressions pass with normal exit (six use separately reviewed upstream Plymouth source); 31 progress tests pass again after caption correction. Limited native reply and approved core restart pass. Personal voice/Hindi, broader confinement/context and physical interaction acceptance remain open |
| Release architecture (ARCH_HANDOFF Prompt F) | Awaiting concrete reviewed proposal and owner approval before impactful packaging |
| Clean target root and pinned package source/signing | Not implemented/validated |
| Calamares exact package/modules and rootfs image | Skeleton only; no install-rootfs.squashfs |
| Asset/license/provenance audit | Owner photo provenance recorded; release redistribution terms remain pending |
| Final build versions/revisions/checksums/private-data inspection | Not performed |
| Disposable VM live boot/offline/network behavior | Not tested |
| Installer cancellation/manual/erase/encryption actually supported | Not tested |
| UEFI bootloader/reboot without ISO/unique machine identity | Not tested |
| Failure/low-space recovery/installed services/runtime | Not tested |
| Physical GPU/microphone/suspend/multiple machines | Not tested by an ISO; never infer from VM results |

Follow [ARCH_HANDOFF](ARCH_HANDOFF.md) Prompts F/G in order. Never expose host
physical disks to VMs or test disk writes on the Windows disk/development SSD.
Final acceptance must reference the rebuilt final ISO SHA256. No flashing,
signing, release upload or publication is authorized by a source commit/push.
