# REgenOS UKI splash artwork and activation proposal

This is a source-artwork checkpoint, not a boot activation or accepted recovery
procedure. No host UKI was built, copied or changed. No package, bootloader,
mount, EFI variable, signing key or service was changed. Recovery and host
activation still require separate evidence and exact approval.

## Read-only findings

The owner's sanitized `--sudo --uki` report identifies the known image as a UKI
with kernel metadata `7.2.10-arch1-1`, equal to the running release. It reports a
378,226-byte `.splash` section and embedded command-line presence, with quiet,
splash and Plymouth-disable flags all false. It does not establish the disk
file's identity as the executed image, the selected GRUB entry or recovery.

Further nonprivileged checks found:

- The literal `linux.preset` default options select the exact public path
  `/usr/share/systemd/bootctl/splash-arch.bmp`. Raw preset options were withheld.
- That stock BMP is 566×167 and 378,226 bytes, exactly matching the reported
  embedded section size. Its header is BMPV5/32-bit. Contents of the embedded
  section were not extracted or compared. This strongly supports the embedded
  Arch splash as an explanation for the startup logo; it is not an identity or
  rendering proof. GDM and Plymouth are separate presentation stages.
- A captured `bootctl status` field reports Secure Boot **disabled**. The overall
  nonprivileged command exits unsuccessfully because its inventory is incomplete;
  this is a partial field readback, not a complete security-policy check.
- Installed mkinitcpio 42.2 supports `--splash`, a separate `--uki` output and
  `--nopost`. `ukify`, `sbsign` and `sbctl` were absent from the checked PATH.
  The matching module-tree kernel image is readable. Existing mkinitcpio
  configuration drop-ins are present and must be preserved and reviewed.

systemd-stub supports an optional BMP `.splash` before kernel invocation; a static
UKI splash does not require Plymouth. The installed mkinitcpio implementation and
current official manual agree on these build options.
[systemd-stub sections](https://www.freedesktop.org/software/systemd/man/latest/systemd-stub.html),
[mkinitcpio options](https://man.archlinux.org/man/mkinitcpio.8.en).

## Source-only artwork generation

From the checkout, using the existing venv, choose a fresh staging directory:

```bash
~/.ai_os/venv/bin/python scripts/render_branding.py \
  --output /tmp/regenos-boot-artwork-review --boot-splash
```

The directory must be new or empty. Existing contents, output symlinks and
symlink ancestors are refused. New final staging directories use mode 0700 and
artifacts use 0600. Exclusive file creation prevents overwriting a later
collision; a failed run can leave an incomplete staging directory, which must
not be treated as a complete artifact set. No installation or root access is
part of this command. Choose another new path for subsequent runs.

The opt-in mode creates only `regenos-boot.bmp` and
`regenos-boot.manifest.json`. It reads the fixed tracked
`branding/regenos-wordmark.svg`; there is no arbitrary input selector, wallpaper,
photograph, font, network request or model download. The SVG uses original
outlined lettering and local gradients. Text, scripts, external references,
styles, event handlers, DTDs and symlink input files are refused.

The black canvas preserves the stock Arch splash footprint of **566×167**.
The landscape wordmark occupies a centered **501×167** rectangle. The custom BMP
encoder emits an uncompressed, bottom-up, 24-bit `BI_RGB` image with a 40-byte
information header, BGR pixels and zero row padding: **283,954 bytes** total.
The manifest records relative input/output names, hashes, dimensions, encoding,
layout and Qt/PySide versions, with `boot_tested: false`. It contains no absolute
home paths, boot arguments, machine identity, timestamps or private configuration.

Repeated generation with the same tracked input and renderer versions produces
identical bytes. The manifest records those renderer versions; byte identity
across different Qt implementations is not established. Neither bitmap validity
nor source tests establish actual firmware display or boot success.

Without `--boot-splash`, the existing four PNG asset names and dimensions remain
the default. Font-dependent wallpaper rendering is kept out of the boot mode.

## Future candidate build — proposal only, not approved

**Do not execute the following candidate recipe yet.** It illustrates the
separate-output route for a future exact, reviewed approval. It is not a host
setup command, and the private input files/directory do not exist merely because
they are named here:

```text
/usr/bin/mkinitcpio
  --kernel 7.2.10-arch1-1
  --kernelimage /usr/lib/modules/7.2.10-arch1-1/vmlinuz
  --cmdline /var/lib/regenos/boot-staging/reviewed-command-line
  --splash /var/lib/regenos/boot-staging/regenos-boot.bmp
  --uki /var/lib/regenos/boot-staging/regenos-test.efi
  --nopost
```

Revalidate the kernel/version and inspect effective hooks/drop-ins before
finalizing this recipe. The reviewed command-line file must privately preserve
the required boot arguments; never paste or commit its contents. Omitting `-c`
preserves default/drop-in loading. `--nopost` skips post hooks, not the normal
initramfs build hooks, which therefore still require review. Leave the current
host OS-release and the existing udev hook family intact for the initial static
artwork experiment. Do not infer permission to add Plymouth or change identity.
[mkinitcpio configuration](https://man.archlinux.org/man/mkinitcpio.conf.5.en).

Do not substitute `-p linux` or `-P`: existing presets target current boot
outputs. The candidate path must be new and separate from `/boot`, with guarded
non-overwrite checks and private logs. Do not patch the live UKI in place with
objcopy. Any subsequent ESP copy, preset/update integration or boot selection is
a separate approved stage. This proposal installs no physical bootloader and
changes no EFI variables or default boot selection.

## Required gates before host generation or activation

1. Identify the actual working boot route and a separately selectable,
   independently owner-boot-tested recovery image/entry. A readable file, an
   inactive fallback assignment, a matching version or a firmware path alone is
   insufficient. Preserve the original UKI and current presets; candidate builds
   must not rewrite the recovery image. Do not force a logout or reboot.
2. Test the artwork/build process in a disposable VM using that VM's own kernel,
   root arguments and disposable disks. Never use a host-derived UKI or attach
   host disks. Check boot, display size, visible errors and untouched recovery.
   VM results cannot establish physical firmware/GPU behavior.
3. Inspect current Secure Boot/signing and TPM-backed-unlock policy. A rebuilt
   image changes signatures and measurements. Disabled Secure Boot or absent
   signing tools do not prove that all relevant policies are absent. Do not
   disable security, enroll keys or rebind credentials automatically; keep keys
   and private boot artifacts outside Git. Obtain any needed additional approval.
   [UKI signing](https://www.freedesktop.org/software/systemd/man/latest/ukify.html),
   [systemd-stub measurements](https://www.freedesktop.org/software/systemd/man/latest/systemd-stub.html).
4. Recheck existing mount/free-space metadata and compare the measured candidate
   size against explicit recovery/update reserve. The earlier 712,892,416 free
   bytes on `/boot` are a historical observation, not an allocation guarantee.
   Build-space and expanded fallback-image size are not yet measured.
5. Present exact input/output paths, package requirements, hashes, private
   backups, effective hook scope, rollback and guarded cleanup for approval
   before generation, any ESP copy or activation. Initially rollback means
   selecting the untouched known working image. Never install a bootloader to
   a physical disk or change the Windows/internal disk or working Arch root.

Persistent updates and a preview ISO remain later checkpoints. Source artwork
does not authorize a pacman hook, rebuilding all presets, changing GRUB, an ISO
build, artifact signing/publication or production-readiness claims.

## Automated source validation

```bash
~/.ai_os/venv/bin/python -m pytest -q tests/test_boot_splash_artifact.py --tb=short
~/.ai_os/venv/bin/python -m ruff check \
  scripts/render_branding.py tests/test_boot_splash_artifact.py
git diff --check -- scripts/render_branding.py \
  tests/test_boot_splash_artifact.py docs/UKI_SPLASH_PROPOSAL.md
```

The isolated Qt subprocess tests check complete BMP headers, exact size, BGR
channel order, bottom-up rows, padding, nonblank artwork, default PNG output,
repeatability, manifest hashes/privacy, unchanged tracked input and staging/input
refusal paths. They use temporary directories and never inspect host boot files.
No host UKI build, firmware rendering, recovery boot, signature verification or
physical disk operation is included in this source acceptance.

On 2026-10-21, **20 tests passed in 1.55s**; full Ruff for the two Python files
and whitespace checks passed. Generated files remained in pytest temporary
directories. No raster artifact or private input was added to Git.
