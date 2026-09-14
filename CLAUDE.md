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
    bin/speakd.py       warm daemon: model in RAM, sentence streaming, bg queue
    bin/hud.py          floating transcript window
    bin/normalize.py    ear rules in code: paths, units, dates, times, links
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
