# Incremental checkpoint ledger

2026-10-20, following source baseline `4ec0150` on `main`. Source completion,
installed readback and physical acceptance are separate. Tested source changes
are committed and pushed individually; pending host work does not become accepted
because independent source work advances.

| Checkpoint | Verified evidence | Remaining gate |
| --- | --- | --- |
| 1. Compact login logo | Owner applied the approved four-file correction and dconf update; independent source/hash/mode/144×48 readback and compiled key pass. 33 installer regressions pass. See [LOGIN_LOGO_FIX](LOGIN_LOGO_FIX.md). | Installation checkpoint complete. Normal-login password-field/scaling appearance remains owner verification. No forced logout/GDM restart. |
| 2. Boot and recovery | [Bounded helper](BOOT_RECOVERY_INVENTORY.md) passes 95 mocked tests. Owner confirms matching kernel metadata and embedded splash; preset/stock BMP evidence supports the Arch startup image. [Staged REgenOS BMP](UKI_SPLASH_PROPOSAL.md) passes 20 tests plus decoder/visual preview. | Source artwork checkpoint complete; no host boot image changed. Actual firmware rendering, active entry and independently bootable recovery remain unverified. Candidate generation/copy/activation need exact approval. |
| 3. Voice reliability | [Capture recovery](VOICE_LISTENER_RECOVERY.md), [stage timings](VOICE_STAGE_TIMINGS.md) and [explicit input routing](AUDIO_INPUT_SELECTION.md) are source-tested. Latest routing/enrollment checkpoint passes 223 focused tests, with asynchronous cancellable selection and no fallback. Earlier approved listener-only restart passes unchanged config/listening off. | New input/deadline source is not yet loaded in resident core. Real English/Hindi, input reconnect/noise, genuine/impostor speaker checks, wake/echo, latency and concurrent VRAM acceptance remain. No listening enabled. |
| 4. Desktop interactions | Source controls, monitor placement, app entries and three previously approved GNOME shortcuts exist. | Owner tests cursor/scaling, unhide, monitor reconnect/transfer, keys, apps and opt-in device reactions. |
| 5. Commands and consent | Bounded runner, timed grants, native reviews and mocked power tests exist. [Bootstrap isolation repair](COMMAND_CONFINEMENT.md) prevents cwd/interpreter-environment module shadowing before Bubblewrap; 79 focused regressions pass. | Reload required for resident core. Actual permission/expiry/revoke/cancel workflows and broader independent argument/confinement review remain; no real shutdown test authorized. |
| 6. Memory and planning | Local explicit/reinforced memory, session history and bounded tool loop exist. [Dispatch deadline repair](PLANNER_DEADLINES.md) passes 55 focused tests and stops stale proposals without repeating completed actions. | New deadline source not yet loaded in resident core. Trusted offline semantic setup, conflict handling, durable task recovery and owner recall acceptance. Asset downloads require approval. |
| 7. Context and isolation | Ephemeral opt-in OCR/AT-SPI and final consent guards are source-tested. | Physical lock/revoke coverage and independent isolation review; system security changes require exact approval. |
| 8. Clean onboarding | Native six-page wizard and live/completion guards are source-tested. | Clean installed-target/new-user acceptance; host setup autostart not installed. |
| 9. Preview architecture and packaging | Tracked proposal/skeleton only. | Architecture approval, licensed assets, clean production packages/root and exact-version Calamares integration. |
| 10. Final ISO/VM acceptance | No ISO built; no VM installation accepted. | Approved build resources, private-data audit, supported disposable-disk cases and installed reboot/recovery tied to final ISO hash. |

The complete scope, including every A001–A100 item and later requests, remains in
[REMAINING_TASKS](REMAINING_TASKS.md). Do not treat this concise ledger as removing
those requirements. No physical-disk operation, signing or release publication is
authorized by checkpoint progression.

CI checkpoint: headless browser/dependency isolation fixes pass locally. Two
controlled comparisons show 6.11.2 completes Python/build/syntax checks, while
6.12.0 exits 139 after its assertions. Paired desktop/screen bounds now exclude
6.12; supported-only CI retains faulthandler. See [CI_VALIDATION](CI_VALIDATION.md).
Required supported-version runs for `6a7f6ee`, `82e89b2` and `945f3fc` now all
complete successfully, including Python exit, historical C++ tests and syntax.
Later source checkpoints require their own CI evidence; no host dependency changed.
