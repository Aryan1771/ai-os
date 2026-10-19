# REgenOS interaction harness checkpoint

The current assistant is a text model connected to tools, local memory and native
Qt applications. Its earlier problems included missing website navigation,
no result-follow-up loop, disabled desktop context, and listening enabled without
a selected activation mode. A larger model cannot repair those missing paths.
This checkpoint implements source changes; live acceptance remains incomplete.

## Conversation and action execution

- Native function schemas are generated from the registered Python functions;
  internal approval, home-directory and sandbox parameters are hidden. Legacy JSON
  calls still work. Unknown tools and invalid native calls fail closed.
- Ten initial schemas keep room for conversation. `discover_tools` supplies extra
  capabilities when needed. Current full/initial schema JSON lengths are 8745/3056
  characters, about 65% less initial schema text. This is not a token or latency
  benchmark. Prompt budgeting is still an estimate, not exact tokenization.
- At most three tool steps per request. Real results feed the next inference using
  native tool-role messages. Repeated identical calls are not executed twice.
  Failed actions and approval requests stop the loop. There is no durable planner,
  automatic recovery of interrupted effects, or proof that every request succeeds.
- Installed system desktop entries can be discovered by name and launched using
  exact IDs. HTTP(S) sites open through the default browser. Launch acceptance does
  not prove page load/focus and does not provide browser account automation.
- `running_applications` exposes same-user process names/counts, not command lines,
  program memory or every application's internal behavior. `runtime_status` checks
  readiness without recording or capturing a screen.
- Companion settings provide warm, calm, playful and focused styles plus optional
  human-authored style notes. Relevant saved context supports continuity. This is
  retrieval/prompting, not model-weight training, feelings or consciousness.

## Microphone and speech

In Settings → Voice, choose microphone listening plus **Require wake word**, or
explicitly enable **Conversation listening without a wake word**. The latter
captures nearby speech after an energy/silence gate; it does not identify speakers.
No activation choice produces a visible `needs_activation_choice` status.
Wake recognition quality, noise tolerance and false activations need live tests.

The running daemon reloads voice configuration. Its owned worker group includes
recording, STT, inference and speech; disabling listening stops the group. Stalled
reads have a three-second deadline, utterances end after silence or the saved cap,
and playback audio/backlog is discarded before listening resumes. This is not
full-duplex interruption or proven acoustic echo cancellation. Parent-owned private
temporary directories are cleaned on ordinary stop/cancel. Power-loss cleanup is
not guaranteed, and private runtime backups are separate from active recordings.

Conversation → **Speak once** captures only after a click; continuous listening
must be off to avoid duplicate requests. Cancel stops its process group and removes
its owned temporary audio. Whisper/Piper files remain the user's existing assets.
Per-turn failures surface in status, and listener restarts are bounded by a retry
interval. Detailed microphone/device/voice quality remains unverified here.

Read-only diagnostics (existing venv):

```bash
cd ~/src/ai-os
~/.ai_os/venv/bin/python -m ai_os.runtime_health
~/.ai_os/venv/bin/regenos-settings
```

**Check readiness** in Voice runs the same report. It exposes booleans/status only,
does not open the microphone, and never prints private conversations or raw logs.
The daemon must be restarted once to load the new supervisor; later voice setting
changes reload. Service changes require the user's approval.

## Desktop context without screen sharing

Companion → **Read focused app through GNOME accessibility** is a separate,
protected opt-in. It uses AT-SPI to query the active window's exposed visible text.
No screen-sharing stream or screenshot is created. A bounded isolated helper uses
the distro's `/usr/bin/python` GI/AT-SPI bindings; it installs nothing and leaves
system Python unchanged. These bindings are available on the inspected host.

The helper checks the GNOME lock state before/after reading, limits traversal and
text size, excludes password/editable subtrees and common password-manager apps,
and times out after four seconds. Unknown session/lock state fails closed. It is a
GNOME prototype: browsers/toolkits may expose incomplete data or require explicit
accessibility configuration. It cannot see pictures/video, hidden app internals,
or reliably reconstruct every application. Do not enable GNOME settings or browser
flags automatically to make it work.

Screen questions first try the existing portal OCR reader, then the optional
accessibility reader. Both inference paths are local Ollama only, have no tools,
save neither observed text nor derived replies to conversation memory, and discard
responses if observation/permission changes. The companion shows enabled-context
indicators. The existing portal reader remains available for screenshot OCR.

## Consented activity memory

Memory → **Remember focused app usage** defaults off. It records only app names
and approximate foreground time, aggregated by UTC day in private
`data/private/activity.sqlite3`. It does not store titles, URLs, screen text,
recordings, clipboard contents or keystrokes. Foreground time is not proof of
attention, work, intent or emotion. Collection also requires ordinary memory on.

Retention is 1–30 days (default seven), with a 2000-row cap. **Inspect app usage**
and **Clear app usage** are explicit native controls. Disable collection to stop
future records; clearing does not disable it. Local Ollama may receive bounded
usage summaries to improve conversation; remote model requests do not receive
automatic activity summaries. Already generated conversation replies may mention
usage; those follow ordinary conversation-memory retention/deletion controls.
The companion displays an indicator while the option is enabled.

## Temporary broad user access

Enable supervised commands in Permissions, then choose Conversation → **Broad user
access…**, a duration, and review the native confirmation. Grants are session-bound,
expire and can be revoked. Models cannot grant or confirm them. Background requests
without a suitable grant remain pending and can be reviewed in Conversation.

Ordinary account-level commands run through `/usr/bin/bwrap`: read-only system
tree, writable user home, private devices and `/tmp`, hidden system/session D-Bus,
dropped capabilities and no inherited API-key/display environment. There is no
ordinary-execution fallback if containment fails. Direct privilege, mount and
disk commands retain barriers. Existing service restrictions still apply.

This is deliberately broad access to the current user's files, including private
files under home; it is not isolation from those files or automatic authorization
for every online account. Network access is not isolated. Browser research and
submissions retain separate exact native approvals. Adversarial containment and
cross-service authority tests remain pending; this is not a complete OS sandbox.

## Model selection and next acceptance

Keep the existing Qwen2.5 model until a measured comparison justifies a change.
Qwen3.5 4B and 9B are current candidates with tools/vision support in the official
library; that does not establish quality or VRAM fit on this laptop. The 4B model
is the smaller candidate; test actual combined context/voice/vision load before
selecting either. Image inference is not wired into this text-context checkpoint.
No model was downloaded, replaced, or set as a fallback automatically.

The synthetic comparison command checks only already-installed names and never
executes a tool or downloads an absent model:

```bash
~/.ai_os/venv/bin/python -m ai_os.model_probe \
  qwen2.5:7b-instruct-q4_K_M qwen3.5:4b qwen3.5:9b
```

It measures greeting/tool selection and request duration, not subjective social
quality, full task acceptance or peak VRAM. Evaluate conversation quality manually
and measure GPU memory separately. Host microphone, audio, AT-SPI, website/app
launches, device hotplug and proactive speech still require real acceptance.

References: [Ollama tool/result protocol](https://docs.ollama.com/capabilities/tool-calling),
[GNOME accessibility](https://developer.gnome.org/documentation/guidelines/accessibility.html),
[AT-SPI API](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/index.html),
[Qwen3.5 4B](https://ollama.com/library/qwen3.5:4b),
[Qwen3.5 9B](https://ollama.com/library/qwen3.5:9b).
