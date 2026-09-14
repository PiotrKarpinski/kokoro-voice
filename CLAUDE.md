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

- `~/.claude/skills/{speak,narrate}` and `~/.claude/commands/{speak,narrate}.md`
  are symlinks into this repo
- the hook is wired by hand in `~/.claude/settings.json`

So edits take effect on the next command. The daemon and the transcript window
both restart themselves when their own source changes. Do NOT also install the
plugin from the marketplace: the hook fires twice and every skill appears twice.

## Layout

    bin/kokoro          launcher, resolves symlinks, finds ~/.kokoro/.venv
    bin/speak.py        client: flags, config, flattening, archive
    bin/speakd.py       warm daemon: model in RAM, sentence streaming, bg queue
    bin/hud.py          floating transcript window
    bin/platforms/      ALL OS-specific code. darwin.py is the tested backend
    hooks/voice-hook    injects narration mode and live speech position
    skills/, commands/  what Claude reads

## Checking a change

    kokoro --version          +edits means uncommitted changes are running
    kokoro "test"             blocking path
    kokoro --bg "test"        daemon path; then --pause, --where, --resume, --hush
    kokoro --status           daemon warm? RAM?
    claude plugin validate .  manifest check

Test through the `kokoro` symlink, not `bin/kokoro` directly: the symlink bug
only shows up that way.

## Things that already bit us

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
