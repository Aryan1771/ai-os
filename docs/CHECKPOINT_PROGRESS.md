# Incremental checkpoint ledger

2026-10-20, following source baseline `4ec0150` on `main`. Source completion,
installed readback and physical acceptance are separate. Tested source changes
are committed and pushed individually; pending host work does not become accepted
because independent source work advances.

| Checkpoint | Verified evidence | Remaining gate |
| --- | --- | --- |
| 1. Compact login logo | Owner applied the approved four-file correction and dconf update; independent source/hash/mode/144×48 readback and compiled key pass. 33 installer regressions pass. See [LOGIN_LOGO_FIX](LOGIN_LOGO_FIX.md). | Installation checkpoint complete. Normal-login password-field/scaling appearance remains owner verification. No forced logout/GDM restart. |
| 2. Boot and recovery | [Improved bounded helper](BOOT_RECOVERY_INVENTORY.md) passes 60 mocked tests and a nonprivileged smoke. Owner elevated report identifies current UKI evidence, readable standard/Zen files and missing known fallback UKI; only default presets enabled, no Plymouth hook. | Inspection checkpoint complete. UKI branding/embedded settings need narrow inspection; active entry and independently bootable recovery remain unverified. Package/hook/boot changes need exact approval. |
| 3. Voice reliability | [Capture recovery](VOICE_LISTENER_RECOVERY.md) and [separate stage timings](VOICE_STAGE_TIMINGS.md) are source-tested; 119 focused voice tests and the final 1150-test local suite pass. Separately approved core restart passes with unchanged config/listening off. | Real English/Hindi, genuine/impostor speaker checks, wake/echo, latency and concurrent VRAM acceptance remain. No listening enabled. |
| 4. Desktop interactions | Source controls, monitor placement, app entries and three previously approved GNOME shortcuts exist. | Owner tests cursor/scaling, unhide, monitor reconnect/transfer, keys, apps and opt-in device reactions. |
| 5. Commands and consent | Bounded command runner, timed grants, native reviews and mocked power tests exist. | Actual permission/expiry/revoke/cancel workflows, independent argument/confinement review; no real shutdown test authorized. |
| 6. Memory and planning | Local explicit/reinforced memory, session history and bounded tool loop exist. | Trusted offline semantic setup, conflict handling, durable task recovery and owner recall acceptance. Asset downloads require approval. |
| 7. Context and isolation | Ephemeral opt-in OCR/AT-SPI and final consent guards are source-tested. | Physical lock/revoke coverage and independent isolation review; system security changes require exact approval. |
| 8. Clean onboarding | Native six-page wizard and live/completion guards are source-tested. | Clean installed-target/new-user acceptance; host setup autostart not installed. |
| 9. Preview architecture and packaging | Tracked proposal/skeleton only. | Architecture approval, licensed assets, clean production packages/root and exact-version Calamares integration. |
| 10. Final ISO/VM acceptance | No ISO built; no VM installation accepted. | Approved build resources, private-data audit, supported disposable-disk cases and installed reboot/recovery tied to final ISO hash. |

The complete scope, including every A001–A100 item and later requests, remains in
[REMAINING_TASKS](REMAINING_TASKS.md). Do not treat this concise ledger as removing
those requirements. No physical-disk operation, signing or release publication is
authorized by checkpoint progression.

CI checkpoint: headless browser/dependency isolation fixes pass locally and all
hosted Python assertions now pass. Hosted teardown still exits 139; a strict
PySide 6.11.2/6.12.0 comparison with faulthandler is underway. See
[CI_VALIDATION](CI_VALIDATION.md); do not call remote CI passed until its exit and
remaining workflow steps pass.
