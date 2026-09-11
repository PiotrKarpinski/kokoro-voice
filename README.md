# kokoro-voice

Claude Code talks to you. Entirely on your machine — no account, no network, no
audio leaving the laptop.

Ask for a summary out loud and hear it in about a sixth of a second. Switch on
narration and hear short progress beats while work happens. Read along in a
floating transcript that follows you across desktops, and interrupt it mid-sentence
with "wait, what was that?" — it pauses, tells you what you just heard, answers in
text, and picks up exactly where it froze.

Built on [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (Apache-2.0).

## Install

```sh
git clone <this-repo> ~/kokoro-voice
~/kokoro-voice/install.sh
/plugin marketplace add ~/kokoro-voice     # then: /plugin install kokoro-voice
```

The installer builds an isolated Python environment in `~/.kokoro`, installs
`espeak-ng` through Homebrew, and links `kokoro` and `hush` into `~/.local/bin`.
The first thing you speak downloads the model, about 330 MB, once.

**macOS only.** Playback uses `afplay` and the floating window uses Cocoa. The
speech engine itself is portable; the plumbing around it is not.

## Using it

Just ask. "Read me the summary", "say that out loud", "tell me out loud" — the
`kokoro` skill triggers on ordinary phrasing in any project. `/speak` if you would
rather be explicit.

| | |
|---|---|
| `/narrate on` | hear short beats while work happens |
| `kokoro --hud on` | floating transcript, always on top |
| `kokoro --config` | every setting, and which you have changed |
| `kokoro --set speed=1.3` | change one — voice, speed, hud, retention, daemon limits |
| `kokoro --version` | plugin version, commit, and where code and data live |
| `hush` | stop it, instantly, from any terminal |
| `kokoro --list` | transcripts of past summaries |

Everything spoken is archived to `~/.kokoro/spoken/` and pruned after 180 days.

## How it works

A **warm daemon** holds the model in memory, so speech starts in ~150 ms instead
of the ~3.5 s a cold PyTorch import costs. It generates one sentence at a time and
streams them to the player, so you hear sentence one while sentence four does not
exist yet. It exits after 15 idle minutes, restarts itself if its code changes,
and is bounded by a memory ceiling.

A **UserPromptSubmit hook** carries two pieces of state into each turn, and prints
nothing at all when neither applies: whether narration is on, and — while audio is
playing — which sentence you are hearing. That second one is what makes "huh?"
work: Claude can see what you just heard and judge whether your message is about
it, instead of matching against a list of magic phrases.

The **skills** hold the craft: write for the ear, never speak file paths, spell
units out. Those rules are measured, not guessed — `~300 MB` is silently dropped
by the phonemizer, `&&` becomes "and-and", and `player.gd` becomes "player dot
gee dee".

## Known limits

- macOS only, as above.
- The daemon grows about 100 MB per request. It is capped and restarts itself
  rather than growing without bound, but it is capped, not cured.
- The floating window will not appear above a true fullscreen app on another
  Space unless it is already running.
- English voices are the well-tested ones. Kokoro ships others; they are untried
  here.

MIT licensed. Kokoro-82M is Apache-2.0.
