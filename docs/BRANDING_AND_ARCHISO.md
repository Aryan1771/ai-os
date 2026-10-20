# REgenOS branding and preview images

REgenOS is an Arch-based native desktop/runtime prototype. Branding source and a
setup wizard do not establish a finished distribution. Preserve upstream Arch,
Linux and third-party attribution, package names and compatibility.

## Current artwork

The default photograph is `branding/wallpapers/default.png`: the owner's nature
photograph enhanced with an AI aurora, supplied for this project. Its matching
**Aurora Ridge** logo uses mountain peaks and blue/teal/violet aurora ribbons.
The small SVG/PNG logo is shared by native app icons, Plymouth source and the
Calamares source. `branding/wallpapers/default.svg` is an original vector fallback;
`lockscreen.svg` supplies matching branded vector artwork. See
[asset provenance](../branding/README.md) for hashes, metadata sanitation and
remaining release-license questions. The original private wallpaper is preserved.

Render the tracked SVGs to a new staging directory, with the existing venv:

```bash
~/.ai_os/venv/bin/python scripts/render_branding.py --output /tmp/regenos-art-review
```

This only writes review assets. Do not run the broad historical setup scripts to
apply them: some install packages, change services or rewrite appearance defaults.
The current GNOME desktop already selects the owner's original photograph.
App source uses installed generic assets with a development-checkout fallback;
no production path depends on a username.

## Native graphical setup

`python -m ai_os.first_run` opens the new Qt first-run app. It introduces the
assistant, drafts language/personality choices, explains consent, offers explicit
read-only readiness checks and links to native settings. Finish records completion;
Cancel preserves settings. `--if-needed` is intended for a reviewed installed-session
integration; live sessions must not mark installed onboarding complete. See
[FIRST_RUN_SETUP](FIRST_RUN_SETUP.md). This is post-install onboarding, not a disk
partitioner, user-account installer or replacement kernel.

## Host boot, login and lock changes

A hash-bound [staged art/default/GDM installer](BRANDING_DEFAULTS_INSTALL.md)
provides private backups and guarded rollback, with 24 disposable-root tests.
The exact inventory and staged rollback proposal are in
[REGENOS_BRANDING_PROPOSAL](REGENOS_BRANDING_PROPOSAL.md). GNOME/GDM is the active
session. Plymouth is absent, and an owner-run sanitized helper identifies GRUB. The active entry and usable
recovery remain unverified; a preset references an unlisted fallback image. No boot changes have been applied. The owner-approved desktop/default/GDM
stages are installed and their hashes/compiled logo key pass readback; actual
login appearance remains pending. Installing
art/defaults, configuring the supported GDM logo, adding Plymouth to initramfs and
changing an identified boot entry each require separate concrete approval.

GNOME lock-screen styling is not the same as the GDM greeter logo. Do not replace
GNOME Shell resources, PAM or firmware logos to claim branding everywhere. Physical
lock/login/boot/recovery acceptance remains pending. Preserve an untouched working
boot entry and recovery path before any approved initramfs modification.

## ISO and graphical disk installer gates

Read Prompts F/G in [ARCH_HANDOFF](ARCH_HANDOFF.md) before packaging. Present and
obtain approval for hardware/UEFI scope, live desktop, kernel/recovery, package
source/signing, clean target root, Calamares version/modules, offline licenses,
updates/rollback and build-space requirements. Build only from tracked inputs;
never copy the live installation, private home, memory, keys or Ollama store.

The [Calamares source](../archiso/calamares/README.md) is still a skeleton, not
an enabled installer. It requires a reproducible package source and a clean
installed-system image at `/usr/share/regenos/installer/install-rootfs.squashfs`.
Validate every configured module against the exact built version. Installer
launcher/autostart belongs only to the live session; keep final disk-write review
and make the chosen disposable target unmistakable.

Use disposable VM disks only; never pass through physical disks, mount them
writable, flash media or install a host bootloader. No final ISO, hash or VM
acceptance exists at this checkpoint. Publication/signing is separately gated.
