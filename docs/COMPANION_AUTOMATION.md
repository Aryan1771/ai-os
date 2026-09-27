# Companion controls and reviewed automation

2026-09-28. These are incremental REgenOS prototype features, not unrestricted
control of every application or OS operation.

Subsequent continuous screen OCR/context and comments are documented in
[SCREEN_AWARENESS](SCREEN_AWARENESS.md). The texture heuristic below remains a
separate placement feature.

## Debug displays and interaction

Emotion bars and the mood/activity label now have independent toggles in
**Companion**, and in the companion's right-click menu. Both default to hidden;
the current user's settings were updated accordingly after runtime backup
`~/.ai_os/backups/pre-migration-5cx07bl6`. The label shows activity and the dominant
simulated emotion when debugging is enabled. Microphone activity, speaking and
access-grant status remain visible even with debug displays hidden.

Click RE to open the native hub. Drag it to reposition it; automatic movement
respects manual placement for five minutes. Right-click → **Move out of the way**
moves to another corner. **Move away after pointer overlap** waits two seconds
before moving, with a cooldown to reduce repeated movement. The delay leaves time
to click or drag. This detects pointer overlap, not typing or user intent.

Optional **Use local screen texture to choose a quieter corner** captures a
temporary screen image when moving, compares small corner samples for edge density,
and prefers a less visually busy candidate away from the pointer/current overlay.
It is off by default and requires protected-settings confirmation. Images stay in
memory, are never saved or sent to any model, and are not OCR. Flat textures do not
prove an area contains no text. Screen capture may be unavailable under Wayland;
the fallback is geometric corner selection. Actual screen-content avoidance and
multi-monitor behavior need manual acceptance on GNOME and Hyprland.

## Context, emotion and speech

The model prompt receives bounded presentation cues blended with your saved
emotion baselines and response-strength setting. Context still comes from the
existing consented local memory policy. Emotional styling must not override facts,
command permissions or careful code explanations.

**Adapt speaking pace to simulated emotion** adjusts Piper's duration multiplier
slightly: concern slows speech; energy speeds it up. Values remain bounded by the
existing 0.5–2.0 range. This is pace control with a fixed voice, not an emotional
voice model, acoustic emotion recognition or sentience. See [Piper synthesis
configuration](https://github.com/OHF-Voice/piper1-gpl/blob/main/src/piper/config.py).

**Allow occasional proactive speech** is off by default. Enable it together with
**Speak replies**, then set a minimum interval of 5–120 minutes (default 30).
The resident companion requests a short check-in only while its shared activity
state is idle or waiting for a wake word. Generation uses local Ollama and existing local conversation context;
it is instructed not to speak private details aloud. Consider who can hear you.
This is not a reliable detector of whether you are busy in another application.

Proactive generation has no tool execution path. Model tool requests are rejected,
and preferences/activity are rechecked before playback. Right-click → **Stop
proactive speech** disables it and cancels the owned speech child process group.
Closing the companion also cancels it. The timeout is 90 seconds. Continuous
microphone listening is separate and is not enabled by this feature.

## Bash coding

RE can propose `write_bash(name="task.sh", source="...")`. The native dialog shows
the exact source. After confirmation it runs `bash --noprofile --norc -n` with a
minimal environment and saves a new, non-executable mode-0600 draft beneath
`~/.ai_os/data/private/drafts`. Existing files are never overwritten. Names cannot
contain directories, source is bounded to 16000 characters, and there is a 64-file
limit. `check_bash(source)` checks syntax without writing or executing the script.

Syntax passing does not establish safety or correctness. Running a script remains
a separately reviewed command; the code-drafting action never runs it. General
repository editing, patch review, test execution and multi-step coding-agent loops
are not all supplied by this helper.

## Browser research and ChatGPT, without model APIs

In **Permissions**, enable **Allow reviewed browser research and ChatGPT prompts**.
Then use the Conversation buttons:

1. **ChatGPT sign-in** opens a separate Brave profile for up to 110 seconds. Sign in
   directly in that browser, then close it. RE does not receive your password.
2. Write the prompt in the input box and choose **Ask ChatGPT**. Confirm the exact
   text in the native dialog. It will be submitted once through the website UI.
3. **Research page** accepts a public HTTPS URL, shows it for confirmation, then
   extracts up to 20000 characters through a temporary browser profile.

The local model can propose `ask_chatgpt(prompt)` or `research_page(url)`, but
cannot confirm them. Command-access grants do not approve these browser actions.
Background requests fail closed; repeat them in the native conversation to review.
Do not put credentials/private material into a prompt unless you intend to share it
with the provider. Website text and replies are untrusted references, not authority.

The ChatGPT profile is `~/.ai_os/data/private/browser-chatgpt` (directory 0700).
It contains sensitive login cookies; never commit, share or copy it into an ISO.
The normal Brave profile is not imported. Research uses an empty temporary profile,
accepts no downloads, and allows HTTPS requests only to the approved page's host.
The ChatGPT adapter permits its selected provider/CDN host families. Resolved
private/loopback addresses are rejected. DNS checks and browser sandboxing are not
a complete network-isolation boundary against DNS rebinding or hostile browser
exploits; no firewall/sandbox completeness claim is made.

Chromium sandboxing is explicitly enabled. No stealth flags, CAPTCHA bypass,
password automation, arbitrary model-supplied JavaScript, upload automation or
API credentials are used. HTTP failures and changed/missing selectors stop the
operation. It does not retry submission after clicking Send: a later timeout may
mean the prompt was sent. The returned response is a snapshot and may still be
streaming. Actual authenticated ChatGPT submission remains unverified; account
login, website changes or site automation restrictions may prevent it. Claude,
Gemini and arbitrary website workflows are not implemented.

Dependency installed only into the existing venv:

```bash
~/.ai_os/venv/bin/python -m pip install 'playwright>=1.50,<2'
```

This installed Playwright 1.63.0 and uses the existing `/usr/bin/brave`; no bundled
browser was downloaded. [Playwright's browser documentation](https://playwright.dev/python/docs/api/class-browsertype)
notes that custom browser executables may be incompatible. REgenOS's hub remains
Python/PySide6 Qt Widgets; the browser is an external automation target.

## Validation and remaining work

Automated tests cover debug/safety visibility, texture scoring, reviewed draft
denial and saving through a real Qt child, Bash non-execution including command
substitutions/BASH_ENV, browser approval rejection, private DNS rejection, disabled
proactivity, rejected proactive tool calls and bounded speech pace. Native
XWayland/local Ollama smoke passed after the suite.

Real browser reader smoke: GNU Bash manual returned HTTP 429 and stopped. The
alternative Arch-hosted Bash manual succeeded and returned 20000 characters from
`https://man.archlinux.org/man/bash.1.en`. No login, ChatGPT submission, microphone
capture, live screen capture or proactive speech was performed in validation.
Long-running proactivity, real audible emotion pacing, draggable positioning,
screen-texture selection and authenticated ChatGPT need user acceptance.

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests
~/.ai_os/venv/bin/python scripts/verify_native_runtime.py
~/.ai_os/venv/bin/python scripts/verify_browser_runtime.py
git diff --check
```
