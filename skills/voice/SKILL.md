---
name: voice
description: The local Kokoro voice - speak to the user out loud instead of, or alongside, text. Use whenever the user wants to HEAR something ("read me the summary", "read it to me", "say it out loud", "tell me out loud", any request starting with "read me" - which means aloud, never read a file), when they want work narrated as it happens ("narrate", "running commentary", "tell me what you're doing"), when they want to switch voice on, off or to narration ("voice mode", "voice off", "stop narrating"), and when speech is playing and they want it stopped or interrupted ("stop", "be quiet", "enough", "wait", "what was that?", "say that again"). One skill for all spoken output.
---

# Voice

One voice, one set of rules, three modes. The mode is a setting, and it arrives
at the top of each of the user's messages from a hook as `<voice mode="...">`.
If you do not see that block, check with `kokoro --config`.

| mode | what you do |
|---|---|
| `off` | Never speak. If asked to, say voice is off and how to turn it on. `kokoro` refuses anyway. |
| `on-request` | Speak only when the user asks to hear something. The default. |
| `narrate` | Short spoken beats while working, one spoken summary at the end. |

Change it with `kokoro --set mode=narrate` (or `on-request`, `off`). Do that when
the user asks: "narrate this", "voice off", "stop narrating", "voice mode on".
It takes effect from their next message.

## Writing for the ear

Every word that goes to `kokoro` follows these rules, in every mode. They are
measured against the phonemiser, not guessed. It gets them wrong silently.

- **Plain prose.** No markdown, bullets, headings or backticks. Short sentences,
  one idea each. Commas and full stops set the pacing.
- **Never a filename, path or extension.** `player.gd` comes out "player dot gee
  dee". Say what the file does: "the player movement script", "one of the body
  scripts".
- **Never code, commands or flags.** `&&` becomes "and-and". Describe the action.
- **Spell out units.** `300 MB` is "em bee", `12.8m` is "em". Write "three hundred
  megabytes", "twelve point eight metres".
- **No tilde before a number.** It deletes the number. Write "about three hundred".
- **Dates and times in words.** "September eleventh", "half past five".
- Acronyms (API, GDD, npm) and plain numbers are safe.

`kokoro` also rewrites filenames, paths, units, dates, times and links before
speaking, as a safety net. Still write for the ear: it can turn `player.gd` into
"the player script", but only you know it is "the movement script".

## Speaking on request

Compose a NEW text for speech. Never feed the chat answer into the voice. Lead
with the outcome. 100 to 180 words, which is 30 to 60 seconds.

```bash
cat > /tmp/voice.txt <<'EOF'
<the spoken text>
EOF
kokoro --bg --title "<three or four word subject>" < /tmp/voice.txt
```

Then **print the same text in the chat, verbatim, as a blockquote, and nothing
else**. No preamble, no recap, no follow-up offer, no second written answer. The
blockquote is the answer. If speaking failed, say so in one line instead.

## Narrating

The user is listening while you work and probably not watching.

**Beats.** Three to eight words, at meaningful steps: starting a phase, finding
the thing, making a change that matters, a result arriving, a surprise that
changes the plan. Not every tool call. Three to eight beats per task.

```bash
kokoro --bg --title "<subject>" "Found it - the timer resets on landing."
```

**Summary.** When the task is done, queue one spoken summary written for the ear,
100 to 180 words, with `--bg`. It plays after the beats. If a turn that did real work ends
without one, a Stop hook asks for it - so send it yourself rather than be asked.

**Chat.** Answer exactly as you normally would. Narration is an extra channel.
Do not paste the spoken summary into the chat as well.

**Trivial questions** ("what's the file called?") get a text answer and no voice.

## Always

- **Always `--bg`.** Plain `kokoro` holds the turn open until playback ends, and
  the user cannot interrupt a frozen chat.
- **Always `--title`**, three or four words. It labels the floating transcript
  window so the user can tell which conversation is talking.
- **Never pass `-s` or `-v`** unless the user asks for this one to differ. Speed
  and voice are their saved settings.

## Stopping and interrupting

Audio keeps playing after your turn ends, until something stops it. When speech
is playing, a `<speaking-now>` block shows what the user just heard.

- **Stop** ("stop", "be quiet", "enough"): run `kokoro --hush` first, then one
  short line.
- **Interrupt** ("wait", "what was that?", "huh?"): run `kokoro --pause` first,
  before thinking. `kokoro --where` shows the sentence they heard. Answer in text,
  because hearing it again will not help. Then `kokoro --resume`, or `--hush` if
  they have moved on.
- **"Say that again"**: pause, speak just that sentence with `--bg`, resume.

## Useful

`kokoro --config` settings · `kokoro --list` past speech · `kokoro --replay` the
last one · `kokoro --status` daemon · `kokoro --hud on` floating transcript.
