# Research, recoverable cleanup and compact chat

2026-10-19. These are native Python/PySide6 features with automated regression
coverage. Source implementation is not complete physical desktop/voice acceptance.

## Research reports

Launch `regenos-research` or choose **Conversation → Research reports**. A request
such as “research giant panda conservation” can propose `research_topic` through
tool discovery. Clarify ambiguous “pandas” (animal or Python library) first.
The native default-No dialog shows the exact topic before any online request.
Only that topic is sent to fixed public Wikipedia/Crossref APIs; chat, files,
memory and account cookies are not sent. No remote model is enabled.

Voice/background requests never approve themselves. A two-minute proposal appears
as **Review requested task…** in the matching native Conversation session. The same
inbox supports cleanup and interactive commands. Expiry/storage failures fail closed;
the model has no inbox-confirmation tool. Each native dialog still validates the
actual topic, command or file preview before execution.

Reports are private Markdown files in `~/.ai_os/data/research/<report-id>.md`, with
actual returned source links, numbered references, source types and limitations.
The native reader lists saved reports, opens files in the desktop editor and
opens source links only when clicked. HTTPS endpoints, response size/time,
redirects, public address checks and private regular-file reads are bounded.
At most 128 reports are created before asking the user to review/export them.

This implementation compiles encyclopedia introductions, attributed publisher
abstract quotations of at most 25 words, and scholarly metadata. Evidence counts
distinguish these types; API availability is not a redistribution license.
English/Hindi report structure is selectable; excerpts retain their original
language and local explanation interprets them in the selected language.
It does not read full papers, establish consensus, cover the
whole web, or guarantee relevance. Missing results fail without inventing sources.
Retrieved text never becomes tool instructions or consent. Search requires a
network; saved reports and provisioned speech assets can be used offline.

**Read paragraph** reads the current block once and pauses. **Next paragraph**
advances and reads once; the paragraph selector and **Previous paragraph** allow
explicit revisiting. The reader follows the selected block. **Stop / pause** stops
its worker/audio; a synthetic process test covers a separate playback child too.
**Explain & read**
uses local Ollama without tools, memory, remote providers or saved model reasoning,
then speaks a short interpretation in the chosen English/Hindi language. An
explanation is model-generated interpretation, not extra verified research; check
it against the source. Voice pause/next commands and full automated literature
review remain pending. No online or audible hardware acceptance is claimed from
the mocked API/speech tests. A later real public-query smoke succeeded for giant
panda conservation: 7 sources (3 encyclopedia, 2 abstract excerpts, 2 metadata),
1.70s, no warnings. The temporary report was removed; no source text was logged.

## Cleanup that can remember a narrowly approved permission

Request e.g. “delete Python files in ~/Downloads/scratch”. `cleanup_files` previews
an exact filename or extension such as `*.py` in one owned directory below home.
It never recursively crawls, removes directories, permanently erases, calls sudo,
or touches a physical disk device. Hidden/runtime/application paths, Git
repositories, Python environments, symlinks and shared hard-linked files are
excluded. Whole-home/system cleanup is outside this feature. RE cannot prove that
an arbitrary personal file is unnecessary; the native preview explicitly says so.

First use shows every matched filename/size. The two-minute preview binds the
directory identity and file stat metadata; changing files invalidates it.
Approval runs `/usr/bin/gio trash -- <exact files>` with a 30-second bound and
`shell=False`. Restore files using desktop Trash. Failure can be partial: inspect
both locations before retrying. Trashing is recoverable, not guaranteed rollback
or a race-proof filesystem sandbox.

The unchecked **Allow this exact directory + pattern again** option creates a
30-day, 20-use rule anchored to that directory's device/inode. Future explicit
cleanup requests matching it can skip a new prompt. Limits are shown in the
dialog: at most the original count or ten files (whichever is greater), and the
original total or 10 MiB. Global limits remain 200 files/1 GiB. Different patterns,
replaced directories, expiration, exhausted uses or larger requests require a new
preview. Neither models nor a voice match create/expand these rules. One earlier
deletion does not grant a whole-computer deletion permission.

Inspect/revoke using **Permissions → Remembered cleanup permissions…**. Rules and
single-use preview metadata stay in private runtime state. The ordinary command
runner is a separate capability; the prompt instructs RE not to use `rm` to bypass
cleanup review. This is application policy, not independent OS confinement.

## Compact chat, activity and settings feedback

Launch `regenos-chat` or **Conversation → Compact chat**. Enter sends, Shift+Enter
adds a line, and Ctrl+Enter stops/reaps the current bridge before sending the
correction in the same session. Stale child callbacks cannot consume the new
reply. Cancellation unwinds ordinary bounded command cleanup; actions already
completed and separately approved visible terminal jobs are not undone.

The compact header shows a live pixel avatar, microphone state and speaker-filter
state. Conversation/access options and operational activity expand on demand.
Activity reports model preparation, tool names, approval and completion/error,
not private internal reasoning, command output, arguments, screen text or passwords.

Settings display an unsaved-change count, disable Save when current, show explicit
save feedback and preserve protected native confirmation. AI/style changes apply
on the next request; a currently running process keeps its imported code until
reopened/restarted. Shared native styling adds focus/pressed states and status
colors. Not every underlying Arch setting or desktop shortcut is implemented.

Speaking drives a bounded animated blue aperture and waveform, preserving topic
forms during speech. Cadence follows the speaking phase, not measured phonemes/audio
amplitude. Motion/animation controls still apply. Mood bars guide tone, warmth,
focus and care; they never change facts, permissions or model weights. RE can say
“I'm excited about the extra space” in character without repeating a disclaimer.
If explicitly asked about conscious feelings, it must describe the state as
simulated. These presentation mechanics are not consciousness or guaranteed
reasoning improvements.
