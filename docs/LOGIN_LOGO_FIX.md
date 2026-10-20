# GNOME 51 login logo correction — 2026-10-20

The owner reported that the installed square REgenOS logo obstructed the password
area. The previous assumption that GDM would reduce any logo to 48 pixels high
was wrong for this host. Earlier file/hash readbacks verified installation, not
visual acceptance. No password, lock-screen image or screenshot was captured
during this investigation.

## Installed behavior and cause

Read-only inspection confirmed GNOME Shell `1:51.1-1` and GDM `51.0-1`. At the
time of investigation, `/etc/dconf/db/gdm.d/90-regenos-logo` selected
`/usr/share/regenos/branding/regenos-mark.png`. That installed PNG was **512 ×
512**, SHA256
`ab5291e0631aad54db9491d6a3fdaaa9d5c131be9dba5bd5aa353af374dac9fb`.

The installed JavaScript resource is
`/org/gnome/shell/gdm/loginDialog.js`, embedded in the `.gresource.shell_js_resources`
section of `/usr/lib/gnome-shell/libshell-51.so`. Its `_updateLogoTexture` requests
the image with width/height `-1, -1`, then adds it as a child without a size cap.
`_getLogoBinAllocation` uses its natural preferred width/height. The installed
dark and light theme resources both give `.login-dialog-logo-bin` only vertical
margins of `3em`; they do **not** impose a 48px height. Those facts explain why a
512px square could consume a large part of the login layout. They do not prove
the exact physical overlap on every display or scaling setting.

The installed code matches the versioned upstream
[GNOME Shell 51.1 login dialog](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/51.1/js/gdm/loginDialog.js).
The generic [GNOME greeter-logo guide](https://help.gnome.org/system-admin-guide/login-logo.html)
describes a 48px scale, but that sizing statement must not override the observed
implementation. Its supported `org.gnome.login-screen.logo` configuration route
still applies; an asset with safe intrinsic dimensions is required here.

The installed Arch wordmarks `/usr/share/pixmaps/archlinux-logo-text.svg` and
`archlinux-logo-text-dark.svg` both use `viewBox="0 0 256 85.085"`, approximately
**3.009:1**. They are reference dimensions, not REgenOS assets to copy or replace.
The square Arch mark has a separate `256 × 256` viewBox.

## Compact source correction

Use a separate landscape wordmark for GDM. The new source asset
`branding/regenos-wordmark.svg` has the same `256 × 85.085` viewBox with explicit
intrinsic `width="144" height="48"`; its rendered PNG is **144 × 48**, 4,788 bytes:

```text
branding/regenos-wordmark.png
SHA256 3817b717f0ec749c88fd48ede237ad5c5f713832dbad2569ebbfd9af0281b9e0
```

The compact native size avoids relying on GDM to shrink a 512px texture. It is a
conservative source correction, not a guarantee of visibility at every DPI. Keep
the square application/Plymouth mark separate. The reviewed privileged update
should install the compact asset at
`/usr/share/regenos/branding/regenos-wordmark.png`, change only the owned GDM
logo key to that path, regenerate dconf and verify the resulting file/key.
Installer validation should reject a missing, oversized or mismatched compact
asset instead of silently using the square mark.

The owner explicitly requested this correction under the already approved GDM
branding scope. The reviewed replacement still needs to be executed by the owner
in their terminal; it is not blocked on a fresh approval request. Preserve the
prior owned file/key values and hashes in the existing private rollback record.
Do not change PAM, password masking,
authentication policy, automatic login, GNOME Shell CSS or resource bundles.
Do not restart GDM, force logout or trigger a lock merely to preview the logo.
Rollback must remain scoped to REgenOS-owned files/values and refuse to overwrite
later unrelated changes. Restoring the known obstructive 512px logo is not an
acceptable visual recovery; remove/disable the owned logo override or select the
reviewed compact asset through the approved procedure.

The regular lock dialog is separate: installed `ui/unlockDialog.js` and
`ui/screenShield.js` contain no logo references, and `ui/sessionMode.js` maps the
greeter to `LoginDialog` and a user session to `UnlockDialog`. Changing this GDM
key does **not** establish that ordinary lock-screen branding has changed. No
independent lock-logo implementation or physical lock acceptance is claimed.

## Reproducible read-only checks

These commands inspect public installed resources and file metadata. They do not
read credentials, invoke authentication, start a greeter or alter any setting.
The `gresource` CLI is not installed on this host; existing GJS/Gio can read the
resources without installing another package. The first GJS import attempt
omitted the Mutter typelib path and failed; the complete version-specific paths
below succeeded.

```bash
pacman -Q gnome-shell gdm
rg -n '^logo=' /etc/dconf/db/gdm.d
```

Inspect both installed CSS variants:

```bash
/usr/bin/gjs -c '
const Gio = imports.gi.Gio;
const resource = Gio.Resource.load("/usr/share/gnome-shell/gnome-shell-theme.gresource");
for (const style of ["dark", "light"]) {
    const path = `/org/gnome/shell/theme/gnome-shell-${style}.css`;
    const data = resource.lookup_data(path, 0);
    const lines = new TextDecoder().decode(data.toArray()).split("\n");
    const index = lines.findIndex(line => line.trim() === ".login-dialog-logo-bin {");
    print(style + ":\n" + lines.slice(index, index + 3).join("\n"));
}'
```

Inspect the installed natural-size load and allocation methods; importing the
Shell namespace registers its public resources without starting a Shell session:

```bash
env GI_TYPELIB_PATH=/usr/lib/gnome-shell:/usr/lib/gnome-shell/girepository-1.0:/usr/lib/mutter-51 \
  LD_LIBRARY_PATH=/usr/lib/gnome-shell:/usr/lib/mutter-51 /usr/bin/gjs -c '
const Gio = imports.gi.Gio;
const Shell = imports.gi.Shell;
void Shell.Global;
const data = Gio.resources_lookup_data("/org/gnome/shell/gdm/loginDialog.js", 0);
const lines = new TextDecoder().decode(data.toArray()).split("\n");
for (const name of ["_getLogoBinAllocation(dialogBox)", "_updateLogoTexture(cache, file)"]) {
    const index = lines.findIndex(line => line.trim() === `${name} {`);
    print(lines.slice(index, index + 20).join("\n"));
}'
```

Check source wordmark dimensions/hashes with the existing venv:

```bash
~/.ai_os/venv/bin/python - <<'PY'
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from PySide6.QtGui import QImageReader

for name in ("/usr/share/pixmaps/archlinux-logo-text.svg", "branding/regenos-wordmark.svg"):
    root = ET.fromstring(Path(name).read_bytes())
    print(name, {key: root.get(key) for key in ("width", "height", "viewBox")})
path = Path("branding/regenos-wordmark.png")
size = QImageReader(str(path)).size()
print(path, size.width(), size.height(), sha256(path.read_bytes()).hexdigest())
PY
```

## Remaining acceptance

After approved installation, read back the compact file's dimensions/hash and
exact GDM key. On the next owner-initiated normal login, verify the password field,
masked input, error/retry text, recovery/accessibility controls and compact logo
remain visible. Repeat on the relevant displays at the saved normal/high-DPI
scales. Source checks and file hashes cannot substitute for this physical result.
Record the owner's result, including failures, before marking login appearance
accepted. Boot still displaying Arch is a separate pending Plymouth/boot-stack
integration task; this correction makes no initramfs, bootloader or disk change.
