# Incremental checkpoint ledger

Updated 2026-10-21, following source baseline `4ec0150` on `main`. Source completion,
installed readback and physical acceptance are separate. Tested source changes
are committed and pushed individually; pending host work does not become accepted
because independent source work advances.

| Checkpoint | Verified evidence | Remaining gate |
| --- | --- | --- |
| 1. Compact login logo | Owner applied the approved four-file correction; source/hash/mode/144×48/key readback and 33 regressions pass. Owner now confirms password field unobstructed and layout usable. See [LOGIN_LOGO_FIX](LOGIN_LOGO_FIX.md). | Reported login layout accepted. Additional display/scaling/error/accessibility cases untested. No forced logout/GDM restart. |
| 2. Boot and recovery | [Bounded helper](BOOT_RECOVERY_INVENTORY.md) passes 95 mocked tests. Owner confirms matching kernel metadata and embedded splash; preset/stock BMP evidence supports the Arch startup image. [Staged REgenOS BMP](UKI_SPLASH_PROPOSAL.md) passes 20 tests plus decoder/visual preview. | Source artwork checkpoint complete; no host boot image changed. Actual firmware rendering, active entry and independently bootable recovery remain unverified. Candidate generation/copy/activation need exact approval. |
| 3. Voice reliability | [Recovery](VOICE_LISTENER_RECOVERY.md), [timings](VOICE_STAGE_TIMINGS.md), [routing](AUDIO_INPUT_SELECTION.md) and [guided progress/private text](VOICE_CHECK_PROGRESS.md) are source-tested: 1388 combined, 286 focused. Approved reload passes unchanged config/listening off. A later owner check completes capture→STT→local model→playback in 22.224s; owner hears response but no transcript. New dialog shows reached text before playback. | Limited hardware execution/audibility observed. Fresh-window transcript display, correct words/relevance/language, Hindi, noise/reconnect, speaker/wake/echo, latency and concurrent VRAM remain. Earlier cancellation is a separate result. |
| 4. Desktop interactions | Source controls, monitor placement, app entries and three previously approved GNOME shortcuts exist. | Owner tests cursor/scaling, unhide, monitor reconnect/transfer, keys, apps and opt-in device reactions. |
| 5. Commands and consent | Bounded runner, timed grants, native reviews and mocked power tests exist. [Bootstrap isolation repair](COMMAND_CONFINEMENT.md) prevents cwd/interpreter-environment module shadowing before Bubblewrap; 79 focused regressions pass and approved core reload is verified. | Actual permission/expiry/revoke/cancel workflows and broader independent argument/confinement review remain; no real shutdown test authorized. |
| 6. Memory and planning | Local explicit/reinforced memory, session history and bounded tool loop exist. [Dispatch deadline repair](PLANNER_DEADLINES.md) passes 55 focused tests, stops stale proposals without repeating completed actions and is loaded by the approved restart. | Trusted offline semantic setup, conflict handling, durable task recovery and owner recall acceptance. Asset downloads require approval. |
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
The later enrollment-fixture regression was reproduced and repaired without a
production workaround; required runs for `3132e4a` and artwork `7d5b138` succeed.
No host dependency changed.

Final native smoke passes nine Settings pages, temporary visible companion and a
local-model reply. These and 1388 passing tests do not close the owner/approval
gates above. No ISO, accepted VM installation or artifact release exists.
