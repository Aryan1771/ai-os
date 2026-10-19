# Requested work and remaining acceptance

2026-10-19. This maps the owner's requests to actual implementation and remaining
work. It is not a claim that all requests are complete. Older feature checkmarks
and Windows tests do not establish physical acceptance.

| Request | Existing implementation / current repair | Remaining evidence or boundary |
| --- | --- | --- |
| Native social companion and moods | Python/PySide6 chat, style preferences, simulated mood-to-tone guidance, first-person display reactions | Broader conversational quality needs owner evaluation; no consciousness or emotion-driven permission changes |
| Blue rearranging avatar | Persistent blue holographic particles, rings, topic/custom forms and speaking waveform; resident reloaded | Owner visual, multi-monitor dragging, reconnect and compositor checks needed; arbitrary artwork quality is not guaranteed |
| Avatar unhide/quit and application-menu access | Header Unhide, Companion controls, desktop entries; installed native launchers inspected | Owner menu/visibility acceptance needed; old resident apps must reopen to load UI changes |
| Visible cursor | GNOME size 64 applied and read back | Owner visual/hotspot/scaling checks needed |
| Open Brave/YouTube and discover programs | Installed desktop-entry discovery, direct URL/browser tools, model tool schemas | Real desktop launch and owner confirmation of the intended tab remain separate from a launch acknowledgement |
| Run commands and traverse directories | Bounded metadata listing, shell-free argv/cwd commands, installed manuals, native review, timed ordinary-user grants, visible interactive jobs | Not universal arbitrary execution: privileged/system/disk/boot actions need separate approval; scripts/wrappers cannot bypass safeguards |
| Permissions/full access | Discoverable native duration/scope grant and revoke, Bubblewrap required, background approval inbox | Same-account UI is not independent OS authorization; no model self-approval or blanket root/account grant |
| Microphone, same-language voice and latency | One-shot/opt-in listening, saved selected/match modes, five-second ending pause, bounded workers, shared audio lease; specific failures now visible | Guided voice check requires explicit Record clicks; real input/reply correctness, echo, wake detection and accents need owner verification |
| Speaker enrollment | Owner confirmed all five accepted after retries and profile saved; profile metadata preserved | Recognition accuracy, false admission/rejection and Hindi remain unmeasured; filter is separate opt-in and not authentication |
| Better Hindi recognition | Invalid/mismatched transcription fails before action; precise diagnostics | Approval requested for official multilingual Whisper small comparison; no automatic model download or setting switch |
| Same cohesive bilingual voice / own voice pack | Existing separate English/Hindi Piper assets; researched candidate engines and private recording/training guidance | A new synthesis backend/weights needs reviewed compatibility, download/license approval and measured 8 GiB coexistence; enrollment is not cloning |
| Short/long-term memory | Recent local sessions, explicit preferences/notes, repeated-statement reinforcement/decay; new inspected-user-statement pin/edit/remove controls | Explicit durable notes are available; semantic paraphrase consolidation/model training are not implemented. No silent whole-computer activity-content recording |
| Memory consent and legacy semantic stores | Legacy read tools bind to the selected runtime and recheck memory/remote-sharing consent on each call. Semantic compatibility APIs fail closed without importing Chroma, opening existing vectors, downloading embeddings or starting telemetry; included in the final 774-test pass | Trusted offline semantic provisioning is not implemented; legacy stores are preserved. Enabling ordinary memory or installing Chroma does not enable semantic search |
| App/screen understanding | Opt-in local screen OCR, AT-SPI supported-app text and bounded running-app metadata; separate app-name/time usage memory | Owner lock/revoke/app coverage tests needed. Hidden app content, arbitrary images/video and every program's internals are not universally accessible |
| Spoken hardware reactions | Queued localized device/display reactions with current consent checks, shared speech ownership and bounded identity metadata | Owner attach/remove/monitor-spec tests needed; no automatic mounts or driver installation |
| Cited research and spoken explanation | Local Markdown, real Wikipedia/Crossref links, short abstracts and evidence labels, en/hi structure, local tool-free explanation, paragraph picker/back/pause | Live source retrieval tested; owner audible walkthrough needed. Full papers, web-wide literature review and voice-controlled report navigation are incomplete |
| Recoverable learned cleanup | Exact regular-file previews, Trash, explicit narrow directory/pattern rules, expiry/revoke and change detection | Owner disposable-file test needed. Prior deletion is not blanket consent; arbitrary personal-file necessity/system harmlessness cannot be proven |
| Compact typing and transparency | Enter send, Shift+Enter newline, Ctrl+Enter cancel/steer, public operation states, save/dirty feedback | Physical keyboard/stop interaction needs owner acceptance; progress is not hidden chain of thought |
| GitHub access for Codex and REgenOS | Codex connector verified; pinned official MCP, exact repo opt-in, read-only result display, no auto-memory/actions | Account writes are not offered by the REgenOS adapter; explicit developer commit/push is separate |
| GNOME desktop shortcuts | Session-specific review/apply/revert with conflict checks, private backup and stale/concurrent-change guards. Owner approved three Super+Alt shortcuts; actual application/readback passed | Owner physical Settings/Chat/Companion key checks remain; see DESKTOP_SHORTCUTS.md |
| Boot/login/lock branding | Tracked branding and installer skeleton exist | Concrete boot-stack/rollback review and separate privileged approval required; no host boot changes authorized here |
| Preview ISO and graphical installer | Archiso/Calamares source skeleton retained, expected clean target root contract documented | Runtime acceptance and approved Prompt F architecture required first; no clean root/package pipeline/final ISO hash or VM acceptance yet |

The next gates are the microphone/desktop owner checks and the pending model
download decision. Do not bypass these with a general project-wide authorization.
Whisper base, English/Hindi Piper assets and GPU inference are already present
and have limited synthetic evidence; missing assets or the historical NVIDIA
version mismatch are not current blockers. Hindi recognition quality, personal
voice accuracy and concurrent worst-case VRAM remain unverified. The final
full regression run passed **774 tests in 10.53s**, including semantic-memory
and per-call permission changes. Correctness lint, whitespace, installer shell
syntax and Chat/Research desktop-file validation passed. Fresh readiness reports
voice ready with no blockers, continuous listening/wake off; approved shortcut
readback passes without conflicts. Readiness is not physical voice acceptance.
The owner separately approved restarting only `ai-os.service` for these patches.
It is active/running with exit status 0; listening, wake and speaker filtering
remain off. No other service was changed.
Follow `ARCH_HANDOFF.md` in dependency order; never expose host physical disks to
VMs or copy personal configuration/models/memory into an image. Publication and
signing require separate approval.
