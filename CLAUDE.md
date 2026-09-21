# kokoro-voice — working notes

Local text-to-speech plugin for Claude Code, built on Kokoro-82M. macOS only.

## Where things live

| | |
|---|---|
| Code (this repo) | `~/kokoro-voice` — PiotrKarpinski/kokoro-voice on GitHub |
| Runtime + user data | `~/.kokoro` — venv, config.json, transcripts, state files |
| Command on PATH | `kokoro` and `hush`, symlinked from `~/.local/bin` into `bin/` |

`~/kokoro` and the `speak` command are gone — they were the pre-plugin layout.
`/opt/homebrew/bin/speak` is espeak-ng's own binary, not ours. That collision is
why the command is called `kokoro`.

## Dev mode

This machine runs the repo live, not an installed plugin:

- `~/.claude/skills/voice` and `~/.claude/commands/voice.md` are symlinks into
  this repo
- the hook is wired by hand in `~/.claude/settings.json`

So edits take effect on the next command. The daemon and the transcript window
both restart themselves when their own source changes. Do NOT also install the
plugin from the marketplace: the hook fires twice and every skill appears twice.

## Layout

    bin/kokoro          launcher, resolves symlinks, finds ~/.kokoro/.venv
    bin/speak.py        client: flags, config, flattening, archive
    bin/speakd.py       warm daemon: model in RAM, plays audio itself on its MAIN thread
                        (player), listener + generator threads, trimmed joined batches
    bin/hud.py          floating transcript window; class Life animates the face
                        (glances, blinks, brows, tilt, breathing)
    bin/normalize.py    ear rules in code, plus delivery: *emphasis*, pauses by
                        punctuation, slower first and last sentence
    bin/face.py         layered face: base() once, draw_brows/eyes/mouth per frame, tilt, breathe
    bin/platforms/      ALL OS-specific code. darwin.py is the tested backend
    hooks/voice-hook    injects the mode and live speech position each message
    hooks/stop-hook     narrate mode: blocks a working turn with no spoken summary, once
    skills/voice/       the one skill: modes, ear rules, interrupts
    commands/voice.md   /voice [on|narrate|off|status|<text>]
    evals/              run.py + cases.json + fixture/, dry-run graded;
                        test_normalize.py for the text rules, no model needed

## Checking a change

    kokoro --version          +edits means uncommitted changes are running
    kokoro "test"             blocking path
    kokoro --bg "test"        daemon path; then --pause, --where, --resume, --hush
    kokoro --status           daemon warm? RAM?
    claude plugin validate .  manifest check
    claude --plugin-dir . plugin details kokoro-voice   token cost, no install needed
    python3 evals/test_normalize.py && sh evals/test_offline.sh   what CI runs, ~5s, no model

Test through the `kokoro` symlink, not `bin/kokoro` directly: the symlink bug
only shows up that way.

## Persona

`~/.kokoro/persona.md` is the user's own and never committed. The skill reads
it before speaking; the hook injects it in narrate mode only.

## Modes

`mode` in `~/.kokoro/config.json`: `off`, `on-request` (default), `narrate`. The
hook injects it into every message. `off` is enforced in the client, not just in
the skill. The old `.narrate` flag file is still read if no mode is set.

## Evals

    python3 evals/run.py --runs 3

Run it after any change to the skill, the hook, or text handling. Each session
gets its own temp KOKORO_HOME and KOKORO_DRY_RUN=1, so it never plays audio and
never touches your real config.

## Things that already bit us

- **A pause that nobody resumed silenced everything for days.** The player
  never starts new speech while paused, so 116 requests queued behind one
  forgotten pause. New speech now clears a pause older than 10 minutes
  (KOKORO_STALE_PAUSE) and drops what it held back; --status shows a pause.
- **The client's temp sweep deleted the daemon's working folder.** It removes
  `speak.*` dirs older than an hour; the daemon kept one for its whole life,
  so after an idle hour the next job failed and cleanup crashed the daemon.
  The daemon uses `kokoro-daemon.*`, recreates it if missing, and its
  cleanup can no longer raise.

- **The window blinked in and out during narration.** It hid the moment nothing
  was speaking, and narrate beats arrive seconds apart. It now lingers
  (KOKORO_HUD_LINGER, default 6 s). Breathing that moved the head a whole text
  row read as a glitch; it is a brightness pulse now.

- **afplay per sentence cost ~1.2 s of dead air each launch,** plus ~0.6 s of
  Kokoro padding: pauses near 2 s. The daemon now plays in-process (NSSound),
  trims padding, joins ready sentences with a 120 ms gap, and starts the next
  batch 100 ms early. **NSSound only works on the main thread** - driven from a
  background thread it silently does nothing - and needs the Cocoa run loop
  pumped. Start-to-start went 2.9 s to 1.1 s. First sound tracks generation
  speed, which tracks machine load: the same text took 0.8 s or 8.5 s to
  generate depending on what else was running.

- **Tk's `deiconify` activates the app on macOS.** That made showing the window
  pull users out of a full-screen chat onto another desktop - reported twice.
  The window now starts transparent and is never withdrawn; `show_window` orders
  the NSWindow front regardless of activation and `hide_window` makes it
  transparent and click-through. A live window had also drifted to x=-455 and
  lost its floating level, so both are re-applied on every show. Check with
  `~/.kokoro/.venv/bin/python evals/test_window_macos.py` - it measures the
  real window from the window server, including that it never goes frontmost.

- **Two installs on one machine killed each other.** Daemon and window were found
  by script name, so a test install stopped the real one's processes. They are
  now started with `--home <KOKORO_HOME>` and every lookup matches that tag -
  scoped to its install. Audio stop/pause still target `afplay` by name.
- **`off` used to inject nothing,** so sessions asked to "read me" answered in
  text without saying why. Found only when evals ran without dev settings.

- **Test a clean install** (`KOKORO_HOME=/tmp/x ./install.sh`). Two fatal bugs
  were invisible on this machine: the spaCy model fetched at runtime via uv,
  and the `speak` name collision.
- **Long-running processes go stale.** Anything that outlives an edit needs a
  source-mtime restart guard. The window lacked one and its buttons died
  silently after a rename.
- **Never fail silently.** `capture_output=True` swallowed the dead-button error.
- **Hook-driven skills:** rules that must hold go in the hook text. Sessions
  often act from the hook without loading the skill.
- **Pushing:** this repo's git credentials go through `gh` (PiotrKarpinski).
  The global osxkeychain helper answers as a different account and gets a 403.
