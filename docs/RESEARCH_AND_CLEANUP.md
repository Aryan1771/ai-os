# Research, recoverable cleanup and compact chat

2026-10-19. These are native Python/PySide6 features with automated regression
coverage. Source implementation is not complete physical desktop/voice acceptance.

## Research articles and optional reports

Launch `regenos-research` or choose **Conversation → Research reports**. The default
**Search articles** mode returns citations without creating a file. Select sources
and click **Open selected articles** (at most three), or approve a chat proposal
whose dialog explicitly says it will search and open up to three articles. To save
Markdown, explicitly ask for a report/document or choose **Save report**; merely
asking to research a topic does not authorize a file. Ambiguous topics need clarification. A request
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

Explicitly requested reports are private Markdown files in `~/.ai_os/data/research/<report-id>.md`, with
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
it against the source. Full automated literature review remains pending.
No online or audible hardware acceptance is claimed from
the mocked API/speech tests. A later real public-query smoke succeeded for giant
panda conservation: 7 sources (3 encyclopedia, 2 abstract excerpts, 2 metadata),
1.70s, no warnings. The temporary report was removed; no source text was logged.

### One-shot voice navigation

Load a saved report in the Research app, then click **Voice command once…**. A
default-No native prompt shows its title, report ID and current paragraph. It
authorizes one bounded local microphone command and the resulting report
narration/explanation only. It does not authorize research uploads, arbitrary
files, account access, shell commands or continuous listening. The visible
**Active report** label identifies the only report that can be controlled.

Say one short phrase: **next paragraph**, **previous paragraph**, **repeat**,
**pause** or **explain this paragraph**. Equivalent exact phrases include
**अगला पैराग्राफ**, **पिछला अनुच्छेद**, **दोबारा पढ़ो**, **रुको** and
**इसे समझाओ**. A few explicit Romanized Hindi forms are also accepted. This
bounded local grammar rejects compound requests and general computer commands;
there is no model deciding which files or actions to control.

Saved selected/match language and speaker-filter preferences still apply. Match
mode must identify English or Hindi; unknown/mismatched speech fails closed.
Explanation follows the recognized language. Source narration retains its source
language. The known Hindi Whisper-base issue can still prevent Hindi commands;
the navigation feature does not fix recognition accuracy or download models.

Each accepted click records once, with at most eight seconds to begin and a
15-second utterance bound, preserving the saved ending-silence pause. The worker
has a 160-second overall GUI timeout, including bounded transcription. Continuous
listening must be off, and the worker takes the shared speech lease before
recording. Another conversation holding it causes a visible failure instead of
overlapping microphone/output turns. Existing narration stops after approval and
before capture to avoid recognizing RE's own voice. This is push-to-talk
navigation, not hands-free interruption: **pause** confirms that reading remains
paused, and every subsequent microphone command needs another explicit click.

Commands are bound to a report SHA256, starting paragraph, one-use nonce and
three-minute native expiry. Changing/reloading a report, moving the paragraph,
expired/replayed responses, or changed voice settings discards the command.
Only canonical navigation metadata returns from the worker; raw recognition
text is neither displayed nor saved as history/memory. Report/source text is not
parsed as a navigation command. Explanations remain local, tool-free and untrusted.
Stop/close cancels recording, transcription and audio children. Linux group
cancellation verifies a fresh owned worker group before signalling; it never
signals PID zero or the desktop process group.

Source verification:

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q \
  tests/test_research_navigation.py tests/test_research_reports.py tests/test_pending_review.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F \
  ai_os/research_reports.py ai_os/research_widget.py tests/test_research_navigation.py
```

These tests use synthetic capture/results and disposable report files, including
consent denial, speech ownership, report replacement, settings revocation, expiry,
replay and hostile non-navigation input. Physical microphone accuracy, Hindi
commands and an audible walkthrough remain owner acceptance checks. No microphone
was opened automatically to validate this feature.

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

## Corrections while a chat request is active

Ctrl+Enter stops the owned active child before sending the correction. The native
client can pass the immediately interrupted chat text as a separate bounded
reference, keeping the latest correction as the current instruction. This does
not replay old application/website intents or approval phrases. It excludes voice,
approval jobs, loaded history and other sessions. Failed cancellation sends no
correction; stale callbacks cannot consume the new reply. Context is cleared on
completion, failure, cancellation or a new ordinary send.

The original interrupted text is not copied into the saved user turn. The latest
correction and resulting answer follow ordinary memory settings; memory-off
stays off. Explicit active context can work locally without persistent memory.
Sending that reference to a remote provider requires separate saved remote-memory
sharing consent, checked again before submission. An answer derived from it may
still appear on screen and, when memory is enabled, in normal reply history.
