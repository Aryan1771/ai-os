# Personal interaction checkpoint — 2026-10-19

These changes are source-tested, not newly hardware-verified. The user reports
that microphone capture now works, but unrelated replies/language switching remain
reported failures until a real utterance-to-reply test succeeds.

## Language and voice

Native Voice settings now label `whisper_language` as **Conversation and recognition
language**. English is the new-install default; existing explicit saved choices
are preserved by loading. English/Hindi selects Whisper's `-l en`/`-l hi` and adds
that reply-language preference to the model prompt, with explicit user translation
requests allowed. Automatic remains selectable; it can misidentify short speech.
This is prompt guidance, not a guarantee of model compliance.

Whisper's documented language switch: https://github.com/ggml-org/whisper.cpp/blob/master/examples/cli/README.md

`Speak once` uses the listener's energy gate and endpointing rather than always
waiting a fixed recording duration. Three voiced 80-ms frames start an utterance;
400-ms preroll retains its beginning. **Finish after silence** defaults to five
seconds of contiguous silence (range 1–10); resumed speech resets that counter.
**Wait for speech to start** remains 2–30 seconds. The separate **Maximum utterance**
is 10–120 seconds, default 120, including preroll and the ending pause. Reaching
that maximum without a completed silence endpoint fails with `utterance_too_long`
and submits no partial command. The native request timeout includes recording,
transcription, model and playback budgets; Cancel remains available. Recorder stalls remain
bounded to three seconds and recorder cleanup runs in `finally`. Energy gating is
not a trained VAD and needs real noisy-room testing. No new model is downloaded.

The native conversation shows **Heard:** from the one-shot result, allowing the
user to distinguish recognition mistakes from reply mistakes. It appears after
the request completes; continuous recognition text is not exported to a status
file. Known non-speech markers such as `[BLANK_AUDIO]` no longer reach the agent.
Short social replies are encouraged. Voice synthesizes one sentence before
playing it instead of synthesizing the whole response first; model output is
still nonstreaming, and each sentence starts a Piper process. A 400-ms playback
tail gate now also applies after synchronous replies, and capture discards an
utterance if competing playback begins. Pending asynchronous speech counts as
busy before playback starts; stopping a queue discards unheard items. Current
resident, native, device and proactive speech paths coordinate using a nonblocking
local process lock. This is coordination, not authentication or acoustic echo cancellation.

The selected language now explicitly overrides old-history language in the prompt,
which also prioritizes the current question. A synthetic trace proves current
transcript → current request → that response's speech; the user's reported wrong
reply still needs a real acceptance test. After waiting for the full five-second
pause, capture trims all but 200 ms of trailing silence before Whisper, reducing
the processed audio without shortening the pause. No measured latency improvement
is claimed. Inference is still nonstreaming and begins after the completed
transcript; speculative reasoning during speech is pending. Five seconds of
silence deliberately adds five seconds before transcription begins.

## Memory

Recent conversation retrieval, explicit preferences, and context notes already
exist. New `reinforced_memory_enabled` is off by default and protected by trusted
native confirmation. With memory saving enabled, exact normalized user statements
12–500 characters long become candidates. Three occurrences spaced at least ten
minutes apart qualify for longer retrieval. Assistant statements never reinforce
facts. Case/whitespace/punctuation normalization is not semantic understanding;
paraphrases are not automatically merged, and recurrence does not prove truth.

Candidates are limited to 256, session-scoped, expire 180 days after last
reinforcement, and are included only as relevant untrusted reference data within
the existing context budget. Repeated statements refresh that expiry. Explicit
preferences and notes provide user-controlled important facts independently.
Expired reinforcement is purged before adding new evidence; an occurrence after
a 180-day gap starts at one hit instead of reviving an expired hit count.
Nothing trains model weights or autonomously authorizes actions. Turning this
option off stops collection/retrieval but preserves records until forgotten.
Native Memory inspection shows qualified records; Forget, Clear session and Clear
all also delete matching/corresponding reinforcement records. Revision guards
prevent late requests from restoring forgotten information. Existing databases
are privately backed up before the new table is created. Backups remain separate
from active-record deletion. The existing secret heuristic is conservative and
cannot guarantee detection of every secret; do not intentionally give it secrets.

## Hardware reactions

`hardware_notifications_enabled` controls monitoring; `hardware_speech_enabled`
is a separate opt-in and also requires speech enabled. Desktop `notify-send`
popups were removed from the project. Sanitized latest-event/error status appears
in Hardware policy. Up to eight reactions can wait while the assistant is busy;
they expire after 60 seconds and are discarded on permission or language changes.
Delivery is not guaranteed. Generic USB, storage and audio notices use friendly,
localized fixed categories; they do not recognize individual USB identities.
Display reactions are also factual templates. Attaching devices never mounts,
executes or formats media.

Monitor facts come from bounded read-only `/sys/class/drm` status, EDID and modes.
Existing displays establish a startup baseline and are not announced as new.
The private bounded known-display store hashes valid EDID; unavailable/invalid
EDID falls back to connector identity, which cannot distinguish replacements.
Identical EDIDs may also be indistinguishable. Reconnects differ from newly seen
displays. Higher maximum advertised pixel count can be compared with previously
seen displays. “Supports 3840 by 2160” describes advertised capability, not active
mode, refresh rate, HDR, quality or actual rendering performance. No device-supplied
text becomes model instructions. Connector timing/hotplug and speech need real
monitor/USB acceptance; no physical attach test was performed here.
Periodic DRM polling retries details that arrive after udev events; transient
missing modes do not erase known capabilities. Exact 3840×2160 or 4096×2160
capabilities can be called 4K. Device reactions never grant permission to use media.

## Cursor and saved user preferences

Cursor size is now a validated 24–96 native Appearance control, default 48.
Generated GTK, environment, Xresources and Hyprland preferences use the selected
size and preserve existing backup behavior. Existing install/branding scripts now
request 48 rather than 32. GTK file preference does not replace GNOME's live
`org.gnome.desktop.interface cursor-size` setting.

At the user's request, `backup_runtime` saved private backup
`~/.ai_os/backups/pre-migration-7ju7empq` before saving:

- `whisper_language=en`
- `cursor_size=64` (desired preference, not verified desktop state)
- `voice_silence_seconds=5`
- `voice_max_utterance_seconds=120`

At inspection the saved language was Hindi; English is now selected. Existing
reinforced-memory and hardware-speech switches were already enabled. Listening
was off and remains off; speech, provider and command-access choices were preserved. No runtime
service was restarted. The venv imports this checkout, but running Python
processes can retain old modules until restarted.

`python -m ai_os.cursor_size --size 64` failed verified readback: live GNOME still
reports **48**. Run `~/.ai_os/venv/bin/python -m ai_os.cursor_size --size 64` in the
actual graphical terminal to apply and verify. Original backup remains in
`~/.ai_os/backups/cursor-size.json`; 48 is this checkpoint's pre-change live value.
Actual artwork sizing requires visual confirmation.

## Access and context boundaries

See [COMMAND_ACCESS](COMMAND_ACCESS.md) for the existing timed native **Broad user
access** grant, expiry/revocation and Bubblewrap isolation. Saving a language or
memory choice does not activate that grant. Sudo, physical-disk, boot and security
changes retain separate safeguards. Universal command/task success is not promised.

Existing opt-in AT-SPI and portal/OCR context remain local, ephemeral and read-only.
Running app process names are available separately. These are not a complete view
of every program, general GUI control, or continuous visual understanding. No new
screen permissions were enabled by this checkpoint.

## Verification and next acceptance

Full suite: **350 passed, 1 failed, 7 errors**. All eight unsuccessful checks
require local sockets denied by this environment. No tests were disabled.

Focused command (134 passed):

```bash
QT_QPA_PLATFORM=offscreen ~/.ai_os/venv/bin/python -m pytest -q \
  tests/test_voice_endpointing.py tests/test_voice_reply_grounding.py tests/test_voice_settings.py \
  tests/test_memory_decay.py tests/test_hardware_reactions.py tests/test_speech_lease.py \
  tests/test_personal_interaction.py tests/test_listener.py tests/test_voice_languages.py \
  tests/test_settings_recovery.py tests/test_access_grants.py tests/test_desktop_context.py
~/.ai_os/venv/bin/python -m ruff check --select E4,E7,E9,F ai_os tests scripts/apply_user_branding.py
git diff --check
```

Re-run the full suite on the host where Unix sockets are permitted. Then review
and request approval for restarting the resident user service. In the real native
session: apply/verify 64-pixel cursor, repeat one English sentence with **Heard:** shown,
verify relevant English reply, measure end-of-speech → recognition → first audible
reply, test silence/noisy-room feedback and microphone stop, then attach/reconnect
a monitor and USB. Check memory promotion/forget with synthetic statements only.
Do not proceed to ISO acceptance while runtime checks remain blocked.
