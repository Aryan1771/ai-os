# REgenOS artwork — Aurora Ridge

The mark is original editable SVG: mountain peaks under aurora ribbons, using
blue, teal and violet from the owner's current desktop image. PNG app/Plymouth
and Calamares logos are rasterizations of that same SVG. Source paths remain
compatible with the existing installers. Native apps resolve generic installed
paths first, then source artwork while developing.

`wallpapers/default.png` is the owner's nature photograph enhanced with an AI
added aurora. On 2026-10-20 the owner requested its adoption for REgenOS and
identified it as their own photograph. No Creative Commons license is implied;
AI-provider terms and a formal public redistribution notice still need release
review. Do not claim unrestricted third-party licensing or include unverified
assets in a published image. No personal home directory is an ISO asset source.

The original PNG (1672×941,2,867,511 bytes) remains untouched outside Git.
Original SHA256: `51959b66c6dc7012be4a3b826a7e9bab1c7b964d9950f6f076c3615b247be97d`.
The tracked copy removes only its ancillary `caBX` provenance container, without
printing it or changing IHDR/IDAT pixel bytes, to avoid publishing embedded private
metadata. Published copy:2,838,412 bytes; SHA256
`ddce8ca177f43fc929ffec37563526e5ce29073256b2bf1219067a5d910be4d9`.
No EXIF/text metadata chunks remain. Keep the photographic/AI origin disclosed.

`wallpapers/default.svg` and `lockscreen.svg` are original vector companion art;
the photographic PNG is preferred for the default desktop. A lock artwork file
alone does not configure GNOME's native lock screen. The companion atlas remains
historical concept art; it is not the live renderer. The live avatar is native
persistent particles, with optional 3D presentation and a low-cost 2D default.

Reproduce logo and vector raster previews without installing anything:

```bash
~/.ai_os/venv/bin/python scripts/render_branding.py --output /tmp/regenos-art-review
```

See [the staged host branding proposal](../docs/REGENOS_BRANDING_PROPOSAL.md).
No boot splash, login configuration, system identity or recovery image is changed
by editing or rendering these assets.

The separate landscape **REgenOS** wordmark is `regenos-wordmark.svg/png`:
explicit 144×48 native size, approximately 3:1 like Arch's installed text mark.
It contains original outlined lettering and is used for GDM/installer/boot-theme
source; square icons remain for apps. GNOME 51 does not clamp a large login image:
never substitute the 512×512 app icon for this wordmark. The GDM installer now
checks this constraint. PNG SHA256:
`3817b717f0ec749c88fd48ede237ad5c5f713832dbad2569ebbfd9af0281b9e0`.
