# REgenOS branding proposal — 2026-10-20

This records the initial read-only inventory and staged proposal, followed by
the owner-approved desktop/GDM application below. No package, initramfs, boot
entry, mount or disk setting was changed; the current GDM session was preserved. The earlier broad commands in [BRANDING_AND_ARCHISO](BRANDING_AND_ARCHISO.md)
are not approval to run them on this host. REgenOS remains an Arch-based runtime
and desktop prototype; a branded session is not an accepted distribution image.

## Owner-run boot follow-up

After fixing the helper to preserve its caller's terminal session, the owner ran
`sudo -v && ~/.ai_os/venv/bin/python ~/src/ai-os/scripts/inspect_boot_branding.py --sudo`
in their terminal and supplied its sanitized JSON. It reports **GRUB** as the
current loader, and lists `/boot/EFI/Linux/arch-linux.efi`,
`/boot/initramfs-linux-zen.img`, `/boot/intel-ucode.img`, `/boot/vmlinuz-linux` and
`/boot/vmlinuz-linux-zen`. Both linux/linux-zen presets are readable. A preset
references `/boot/EFI/Linux/arch-linux-fallback.efi`, but the helper lists no
recognized fallback image and no recognized menu-entry classes. This is a
**partial inventory**, not proof the referenced fallback exists, an active entry
is known, or recovery is bootable. Custom paths are intentionally omitted.

The coordinating executor's noninteractive sudo still cannot share that terminal's
cache; the owner-run result is distinct from direct agent elevated inspection.
No boot writes occurred. Before enabling Plymouth, inspect the actual GRUB entry,
preset contents/output paths and ESP free space, then establish an untouched,
working recovery entry/image. This requires its own exact approval; no rebuild or
bootloader installation is authorized by read-only inspection.

## Initial read-only starting point

| Item | Observed state |
| --- | --- |
| GNOME desktop background | Light and dark `picture-uri` both select `~/.config/background`; `picture-options` is `zoom`. |
| Selected image | Regular PNG, 1672 × 941, 2,867,511 bytes, not a symlink. SHA256: `51959b66c6dc7012be4a3b826a7e9bab1c7b964d9950f6f076c3615b247be97d`. |
| Asset provenance | Owner says this is their nature photograph enhanced with an AI aurora and requests its use for REgenOS. The coordinating agent viewed the landscape and found no visible private content. No particular redistribution license or AI-provider terms have been supplied. |
| Desktop/login | GNOME Shell `1:51.1-1`; GDM `51.0-1`; `display-manager.service` is active and resolves to GDM. No uncommented `WaylandEnable` or automatic-login override was found in the inspected GDM config. |
| Host identity | `/etc/os-release` still identifies Arch Linux, with `LOGO=archlinux-logo`. This inventory does not replace upstream identity or attribution. |
| Boot environment | UEFI is present. `/boot` is an existing vfat mount, unreadable to the current user. The active loader, entry paths and recovery images are **unverified**. Installed GRUB does not prove it is the loader used for this boot. |
| Boot packages | `linux-zen 7.2.10.zen1-1`, `mkinitcpio 42.2-1`, `systemd 262-1`, `grub 2:2.16-1`; `linux-zen.preset` and `linux.preset` exist. Plymouth and dracut are not installed. |
| Initramfs hooks | `base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck`; no Plymouth hook. No `quiet` or `splash` flag was observed in the inspected current kernel command line. |
| GRUB defaults | Distributor is `Arch`, timeout style `menu`, graphics mode `auto`; no active theme/background override was found. Generated GRUB config under `/boot` was not readable. |
| GNOME system defaults | `/etc/dconf/profile/user` and `/etc/dconf/profile/gdm` are absent; no GDM logo definition was found. `/usr/share/gdm/greeter-dconf-defaults` exists. |
| Installed REgenOS art | Expected mark and wallpaper files under `/usr/share/regenos/` are absent. Existing per-user art remains untouched. |
| Repository art | The owner-approved photograph is now the tracked `branding/wallpapers/default.png`, with the Aurora Ridge SVG/512px PNG mark and matching Calamares mark prepared in source. Existing SVG wallpapers and companion atlas remain. Source Plymouth prompt handling is described below; none of these assets has been installed system-wide. |
| ISO/installer | `archiso 91-1` is installed; Calamares is not. The tracked installer skeleton is not evidence of a clean target root, usable installer or accepted ISO. |

Read-only commands included `gsettings get` for the three background keys,
`systemctl show display-manager.service` for its names/path/state, selected
`pacman -Q` queries, `findmnt` for mount point/filesystem type, selected config
keys, and image metadata/hash inspection with the existing venv and Qt image
reader. No complete dconf database, kernel command line, machine ID or private log
was dumped. `bootctl is-installed` failed with a permission error; no privileged
retry was attempted. An inaccessible `/boot` path must not be reported as absent.

## Source assets and identity

The original photo remains unchanged. A container-only privacy pass removed its
ancillary `caBX` (C2PA) chunk from the tracked copy without decoding or changing
the IHDR/IDAT pixel data. The tracked `branding/wallpapers/default.png` is
2,838,412 bytes with SHA256
`ddce8ca177f43fc929ffec37563526e5ce29073256b2bf1219067a5d910be4d9`;
the original file/hash in the inventory above is distinct. Private provenance
payloads were not printed. The coordinating agent viewed the new small Aurora
Ridge PNG mark. A whole wallpaper becomes illegible as a small login logo; the
matching mountain/aurora mark supplies that identity. A lock-screen variant may
share the photograph with a restrained wordmark. Production asset paths must be
generic:

```text
/usr/share/regenos/branding/regenos-mark.svg
/usr/share/regenos/branding/regenos-mark.png
/usr/share/regenos/wallpapers/default.png
/usr/share/regenos/wallpapers/lockscreen.png
```

Record the owner's provenance and requested project use alongside the source
asset; do not invent a Creative Commons license. Check image metadata before
tracking it, record hashes and dimensions, and keep any private metadata out of
derived public assets. Redistribution terms, including any relevant AI-provider
terms, remain a release gate. App icons, wallpaper, boot splash and greeter art
must retain REgenOS capitalization and upstream attribution. Do not replace every
Arch/Linux reference, package-owned logo or firmware mark across the host.

## Proposed host changes and rollback

Each stage below requires its own concrete approval before system writes. Preserve
private backups of the affected files and relevant individual preference values,
including whether each file/key originally existed. Record the installed hashes.
Rollback must refuse to overwrite a later unrelated edit.

1. **Install art and add unlocked GNOME defaults.** Install only the reviewed
   source assets at the four production paths above, mode 0644. Merge a dedicated
   `system-db:regenos` after `user-db:user` in `/etc/dconf/profile/user`, preserving
   any profile added since this inventory. Add
   `/etc/dconf/db/regenos.d/90-background` with the following values and run
   `dconf update` only after approval:

   ```ini
   [org/gnome/desktop/background]
   picture-uri='file:///usr/share/regenos/wallpapers/default.png'
   picture-uri-dark='file:///usr/share/regenos/wallpapers/default.png'
   picture-options='zoom'
   ```

   Do not add locks or reset the current user's preferences. Existing user
   background choices take precedence, so this stage supplies defaults for a
   fresh session/profile rather than forcing a visible change on this desktop.
   GNOME documents system defaults and profile precedence; profile changes apply
   at the next normal login. Check any `DCONF_PROFILE` override before making
   changes. [GNOME defaults](https://help.gnome.org/system-admin-guide/dconf-custom-defaults.html),
   [GNOME profiles](https://help.gnome.org/system-admin-guide/dconf-profiles.html).

   Rollback: remove only unchanged REgenOS-owned defaults/assets, remove only the
   added profile line or restore the exact unchanged original, and regenerate the
   database with `dconf update`. Keep the existing user photo/settings intact.

2. **Add the supported GDM greeter logo.** Merge/create
   `/etc/dconf/profile/gdm` with `user-db:user`, `system-db:gdm` and
   `file-db:/usr/share/gdm/greeter-dconf-defaults`. Add the dedicated file
   `/etc/dconf/db/gdm.d/90-regenos-logo`:

   ```ini
   [org/gnome/login-screen]
   logo='/usr/share/regenos/branding/regenos-mark.png'
   ```

   Run `dconf update` after approval. GNOME supports this logo key. Its generic guide describes 48px scaling, but
   installed GNOME 51.1 actually loads natural dimensions without a CSS cap.
   The initial 512px square failed owner visual testing; use the separate 144×48
   `regenos-wordmark.png`, as documented in LOGIN_LOGO_FIX.md. Check the result on the next owner-initiated login;
   do not restart GDM or terminate the desktop to preview it. Rollback removes
   only the owned logo file/profile additions, restores any prior value and
   regenerates the database. [GNOME greeter logo](https://help.gnome.org/system-admin-guide/login-logo.html).

3. **Verify native lock appearance.** The existing GNOME lock screen/authentication
   stays in place. Observe whether GNOME 51 displays the desired photo/blur with
   the current background and whether all monitors remain usable. A separate
   shipped `lockscreen.png` is an asset, not proof that GNOME consumes it. Do not
   promise independent lock branding or patch GNOME Shell resources, extensions,
   PAM, biometric policy or automatic login as part of the logo/default stage.
   No host lock-screen modification is proposed until its supported scope is
   established; there is therefore nothing to roll back at this stage.

4. **Validate boot art before enabling it.** The source Plymouth script now
   handles normal, password, question, modern secret/nonsecret prompt, message,
   hide-message, progress, hotplug and quit callbacks. It draws only masked
   password counts (at most 64 visual bullets), clears displayed input on normal/
   quit, keeps the newest failure message and pauses animation during prompts.
   The logo fits the smallest of up to 16 attached displays, recomputes layout on
   refresh/hotplug and falls back to the REgenOS wordmark if the PNG is missing.
   It registers no keyboard/validation interception and logs no input. These are
   **source-interpreter checks**, not proof of actual boot or password handling.

   Test the theme in a disposable VM, including actual boot output, keyboard/
   password prompts, failed/retried passwords, multilingual prompt rendering,
   Escape, text fallback, multiple resolutions and recovery. Plymouth requires
   its initramfs integration and a `splash` kernel argument; Escape exposes boot
   output. This changes Linux startup presentation, not the motherboard firmware
   logo or kernel identity.
   [Plymouth manual](https://man.archlinux.org/man/plymouth.8).

   Host activation remains **blocked on identification of the active GRUB entry,
   its initramfs/UKI paths and a verified usable recovery image**. The owner-run
   helper identifies GRUB, but does not establish those remaining facts. If elevated inspection is necessary, ask
   for that inspection separately; do not mount anything or write an ESP merely
   to discover the loader. Then present the exact files, package transaction,
   preset outputs, free-space check and restore commands for approval. Candidate
   changes are the `plymouth` package, art under
   `/usr/share/plymouth/themes/regenos/`, the selected theme in
   `/etc/plymouth/plymouthd.conf`, one reviewed hook insertion in
   `/etc/mkinitcpio.conf`, and `splash` in the confirmed active entry. Preserve the
   existing `udev` hook family; do not silently convert to a systemd initramfs.
   Rebuild only the explicitly approved preset after inspecting its output paths,
   rather than running a blanket `mkinitcpio -P` across both kernels.
   [Arch Plymouth integration](https://wiki.archlinux.org/title/Plymouth).

   Preserve a verified working entry, kernel and initramfs that are not rewritten
   by this change. Keep visible boot/recovery options; `quiet` is optional and
   must not hide failures during initial testing. The documented temporary escape
   flags are `plymouth.enable=0 disablehooks=plymouth`; boot them in a VM before
   relying on them for recovery. Rollback restores the exact prior theme/hook/
   command-line configuration and rebuilds only the same approved preset, with
   pre-change image copies available. The active entry is unknown today, so an
   executable host boot-write recipe would be speculative. No `grub-install`,
   `bootctl install/update`, firmware-variable write or physical-disk operation
   is proposed. [Arch recovery guidance](https://wiki.archlinux.org/title/Plymouth#Disable_with_kernel_parameters).

## Isolated source validation

The script APIs were checked against upstream Plymouth **26.134.222**, commit
`d15928a8e06c217aad0f2e3579df23fec93dc009`:
[example theme](https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/26.134.222/themes/script/script.script),
[callback bindings](https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/26.134.222/src/plugins/splash/script/script-lib-plymouth.c),
[shared display canvas](https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/26.134.222/src/plugins/splash/script/script-lib-sprite.c).
The used API signatures were also checked against the pinned source: `Image.Text`
has seven positional arguments (text, RGB, alpha, font, alignment; later values
are optional), image dimensions take no argument, `Scale` takes two, and Sprite
position takes three. The window geometry calls accept an optional display index;
background colors take RGB. Every registered callback setter takes one function;
the modern prompt receives prompt/entry/secret, legacy password and question take
two values, boot progress takes duration/fraction, system update takes one integer,
message/hide take one string, and refresh/normal/hotplug/quit take no values.
`String.Length` returns a byte count. [Image helpers](https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/26.134.222/src/plugins/splash/script/script-lib-image.script),
[math helpers](https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/26.134.222/src/plugins/splash/script/script-lib-math.script).
The GitLab web fetch was unavailable; bounded HTTPS reads from the official
GitLab raw/API endpoints succeeded. No third-party theme was copied.

An isolated upstream parser/interpreter subset was downloaded into
`/tmp/regenos-plymouth-source-wlc93w_n`, with tag/commit recorded in its local
`provenance.json`. It contains `script`, `script-debug`, `script-scan`,
`script-parse`, `script-object`, `script-execute`, `ply-list`, `ply-hashtable` and
`ply-bitarray` `.c`/`.h` pairs, plus `ply-utils.h`, `ply-logger.h` and
`script-lib-math.script`, flattened from that upstream revision. Tests load the
actual upstream `Math.Min`, `Math.Max` and `Math.Clamp` definitions; they are not
invented mock APIs. The C bridge matches native `Math.Int`'s `floor` behavior and
`Math.Sin`'s `sin`, and the image mock accepts the complete seven-argument text
signature. No production theme change was needed after this API review.
No upstream files or compiled binary were vendored
into this repository. Tests compile those reviewed files with the installed C
compiler into pytest's temporary directory; graphics objects are explicit mocks.
The test bridge supplies only checks, math/string primitives and error reporting.
It does not start Plymouth, render Pango, collect keys or touch host configuration.

```bash
REGENOS_PLYMOUTH_SOURCE_DIR=/tmp/regenos-plymouth-source-wlc93w_n \
  QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q \
  tests/test_plymouth_theme.py --tb=short
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F tests/test_plymouth_theme.py
git diff --check
```

Result: **5 tests / 41 callback-state/layout checks passed in 0.53s**; focused
correctness lint and whitespace checks passed. Initial mock initialization and
callback receiver mistakes were corrected in the harness before this result;
this did not involve a host boot attempt. The tests never download dependencies.
Without a separately reviewed `REGENOS_PLYMOUTH_SOURCE_DIR`, they explicitly skip;
that skip is not acceptance. To reproduce after the temporary source directory
is removed, obtain exactly the listed source files from the pinned official
revision and review them before setting the environment variable. A real
`plymouth`/`plymouthd` executable is absent; boot, actual text/graphics, input,
encrypted-root prompts and Escape behavior remain **not tested**. Activation stays
blocked until those tests and the exact boot-change approval are complete.

## Acceptance and preview image gates

Source review should check PNG/SVG validity, transparent small-logo readability,
photograph hash/provenance and absence of private metadata. Host acceptance is
separate: verify GNOME light/dark backgrounds, a fresh user's unlocked defaults,
GDM logo, lock/unlock and owner-approved boot/recovery. No such visual or boot
acceptance has been performed by this inventory; package presence alone does not
pass it. No physical GPU, microphone, login or reboot result is inferred from VM
results.

Before an ISO build, follow Prompt F in [ARCH_HANDOFF](ARCH_HANDOFF.md): obtain
approval of the release architecture, clean runtime packaging, installed target
root, package/signing policy, asset licenses, hardware/UEFI scope, offline assets,
updates/recovery and build-space budget. Build from tracked inputs, never this
private live home or Ollama store. Keep Calamares autostart live-only, retain final
target-disk confirmation, and test only disposable VM disks. No ISO was built,
flashed, published or accepted by this branding inventory.


## Sanitized read-only boot inventory helper

The new helper reads only fixed boot-status, boot-directory and recognized
GRUB/systemd-boot/mkinitcpio configuration paths. It never mounts anything,
installs a loader, rebuilds an image, edits a file or changes a service. It emits
JSON with recognized loader product, kernel/initrd paths, menu classes, listed
fallback images and readable preset names. It omits raw kernel arguments,
UUIDs, disk identifiers, unknown filenames, menu titles and raw errors.

Run the nonprivileged inventory from the checkout first:

```bash
~/.ai_os/venv/bin/python scripts/inspect_boot_branding.py
```

The owner approved read-only elevated inspection separately. If permission is
still needed, run both commands in the **same owner terminal** so the sudo
credential timestamp applies there. Authentication stays in that terminal;
`--sudo` itself uses only `sudo -n` and never requests or receives a password:

```bash
sudo -v
~/.ai_os/venv/bin/python scripts/inspect_boot_branding.py --sudo
```

A `sudo_unavailable` status stops after the first authentication failure. A
`budget_exhausted` status stops further commands. The complete inspection shares
a 10-second deadline and 1 MiB combined subprocess-output budget; partial results
remain partial. Unknown/custom boot filenames are intentionally omitted, so this
helper alone cannot identify every active entry or establish bootability,
recovery, ESP free space or safe host activation. Listed images are not checksum
or boot-tested images. Do not infer approval for boot writes from this read-only
inventory. The agent did not run elevated inspection through this helper.

Validation: `~/.ai_os/venv/bin/python -m pytest -q tests/test_boot_inventory.py`
passed **18 tests** with all boot subprocesses mocked. Coverage includes omitted
private identifiers, fixed argv, noninteractive sudo failure, byte/time budgets,
child cleanup and avoiding false fallback claims from symlinks/directories.


The first owner-run elevated attempt still reported `sudo_unavailable`. The
helper had created a new session for each child, which can detach the controlling
terminal used by sudo's credential cache. The corrected POSIX helper retains
that session with `start_new_session=False` and creates an owned process group
with `process_group=0` for bounded cleanup. Python documents these as separate
session/group operations; sudo documents terminal-scoped timestamps and a
parent-process fallback when no terminal exists.
[Python subprocess documentation](https://docs.python.org/3.14/library/subprocess.html),
[upstream sudo timestamp policy](https://github.com/sudo-project/sudo/blob/main/docs/sudoers.man.in).

This is a source fix awaiting another owner-run check in the same terminal;
custom sudo policies may still prevent cache reuse. No authentication policy was
changed and no elevated retry was run by the agent. `sudo_unavailable` now carries
only a fixed `sudo_reason`: `authentication_required`, `policy_denied` or
`execution_unavailable`. A generic sudo warning, such as host-name resolution,
no longer automatically becomes an authentication failure. Raw stderr remains
withheld. The corrected helper passes **33 mocked tests**, including preserving
the session, creating/verifying its own cleanup group, refusing group 0/1 and
classifying known failures without leaking identifiers. Correctness lint passes.

## Approved desktop/GDM application

The owner separately approved and ran both hash-bound installer stages and
`dconf update` in their terminal. Desktop plan:
`2a3fd1499ba17715861d18ba3767fa072c3a87c02658930100b1753c5a31bc6a`; GDM plan:
`5ce984567051387570150e920ddac66ac9b1f111403a7170e21ddd54f7ee9757`. Fresh agent
readback confirms all nine installed files match source and mode 0644, both compiled
databases exist and the GDM logo key selects the reviewed PNG. Owner background
choice remains unchanged. Private backups are on the host and are not tracked.
See [installer/rollback details](BRANDING_DEFAULTS_INSTALL.md). No GDM restart,
logout, boot configuration write or physical visual acceptance was performed.

## Current compact-wordmark source check

The temporary interpreter sources disappeared after a host reboot. The durable
reviewed subset/license/hash manifest is now
`~/.ai_os/build/plymouth-script-check-26.134.222`, pinned to the same upstream
commit. Set `REGENOS_PLYMOUTH_SOURCE_DIR` to that path for all six current tests,
including the landscape wordmark's prompt clearance. Old five-test/tmp commands
above are historical. No package/daemon/boot was installed by those checks.

The owner reported the original square login image hides the password field.
The corrective four-file plan installs compact 144×48 `regenos-wordmark.svg/png`
and points GDM at the named PNG. Hash-bound plan:
`e26d1419c5cdd8ba7b68315478d3f183b2f541add69a22e423030830a336646e`.
The copyable command is provided under prior GDM approval and the explicit repair
request. It is not a second boot/logo activation approval. Current terminal apply
and physical login acceptance remain pending; source tests alone cannot close it.
