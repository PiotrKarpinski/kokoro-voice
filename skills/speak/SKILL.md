---
name: speak
description: Speak a summary or answer out loud through the local Kokoro voice instead of writing it in the chat. Use whenever the user asks to HEAR something rather than read it. Triggers include "read me the summary", "read me that", "read it to me", "read that back", any request starting with "read me", plus "say the summary", "say it out loud", "tell me out loud", "out loud", "voice mode", "speak it", "summarise this out loud", "give me the rundown out loud". The phrase "read me" means read ALOUD to the user, never read a file. Also use when the user has switched the conversation into voice mode and has not switched back. ALSO use this skill to STOP speech that is already playing - "stop talking", "be quiet", "shut up", "stop the audio", "stop reading", "that's enough", "silence", "hush", "enough" - because audio plays detached from the turn and keeps going until something runs the hush command. ALSO use it to INTERRUPT speech that is playing - "wait", "hold on", "what was that?", "say that again", "repeat that", "go back", "pause" - which should pause the audio and answer, not stop it dead.
---

# Speaking out loud

The user wants this in their ears, not on their screen. Two things make that work:
writing for the ear, and staying quiet in the chat afterwards.

## 1. Write for the ear

Compose a NEW text for speech. Never pipe a normal chat answer into the voice -
it reads bullet markers, slashes and punctuation aloud and sounds broken.

Length: 30-60 seconds, which is 100-180 words. A spoken summary is shorter than a
written one; cut to what the user actually needs to hear. Lead with the outcome.

Plain prose only. No bullets, headings, bold, backticks or markdown of any kind.
Short sentences, one idea each. If you would not say it aloud to someone standing
next to you, rewrite it.

### What Kokoro gets wrong (measured, not guessed)

These are verified against the phonemizer. They corrupt silently - the audio just
comes out wrong, with no error.

- **Never speak file paths.** `./scripts/player.gd` becomes "dot skripts slash
  player dot gee dee". Say "the player movement script".
- **Never speak code, commands or flags.** `&&` becomes "and-and". Describe what
  the command does instead.
- **Spell out every unit.** `300 MB` is "em bee", `12.8m` is "em", `1h 20m` is
  "one aitch twenty em". Write "three hundred megabytes", "twelve point eight
  metres", "an hour and twenty minutes".
- **A tilde before a number deletes the number.** Write "about three hundred".
- **Write dates and times as spoken words.** `2026-09-11` becomes "twenty twenty
  six-zero-nine-eleven"; `17:30` keeps the colon. Say "September eleventh" and
  "half past five".
- Acronyms are safe - GDD, API and npm are correctly spelled out letter by letter.
- Plain numbers are safe - `404` becomes "four hundred four". Decimals become
  "point five", which is fine.

Commas and full stops are what give the voice its pacing, so punctuate generously.

## 2. Say it

Write to a temp file and pipe it, so quoting and newlines cannot break the shell:

```bash
cat > /tmp/speak.txt <<'EOF'
<the spoken text>
EOF
speak --bg < /tmp/speak.txt
```

Pass `--title` with a short subject - three or four words naming what this is
about ("spring economy", "CI failure", "migration plan"). It shows in the floating
transcript window, so the user can tell at a glance which conversation is talking
when more than one is. Without it the window falls back to the project folder name.

**Always `--bg`.** It hands the text to the daemon and returns in about thirty
milliseconds, so your turn ends straight away and the user can type while it is
still speaking. Without it the turn stays open for the whole minute of audio and
the chat is frozen - they could not even ask you to stop. The audio plays on
regardless of whether the turn, or the session, has ended.

Options: `-v <voice>` (default `af_heart`; `am_michael`, `bf_emma`, `af_bella`
also work).

**Do not pass `-s`.** The speaking rate is a saved user preference - overriding it
means speaking at a speed they did not choose. Only pass it if they ask for this
one to be faster or slower, and use `--set-speed N` if they want it changed for good.

**Stopping.** If the user says stop, be quiet, that's enough, or anything else
meaning they do not want to hear the rest, run `speak --hush` as the very
first thing in your reply - before answering, before explaining. It halts playback
immediately and abandons whatever is left. Then reply normally in one short line.
Treat a bare "stop" during speech as meaning the audio, not the work.
It speaks sentence by sentence, so the voice starts in about two tenths of a second
however long the text is - never pre-chunk the text yourself, just pipe it in whole.

`speak --list` shows recent spoken texts; `--replay` says the last one again.

A warm daemon holds the model in memory, so speech normally begins in about
a sixth of a second. The very first call after a reboot takes around six seconds
while the daemon loads - that is expected, not a fault, and needs no comment.
The daemon starts itself, restarts itself if the code changed, falls back to
in-process generation if it cannot start, and exits after fifteen idle minutes.
`--status` reports it and `--stop` frees its memory.

## 3. Print the transcript, and nothing else

**Print the spoken text in the chat, verbatim, as a blockquote.** The user reads
along while listening, and can look back at a sentence that went past too fast.

    > Here is where we are. The data sources panel was showing warnings on
    > sources that were working fine. It turns out almost nothing was broken.

Verbatim matters. It is the SAME words the voice is saying - not a written-up
version, not an expanded one, not a tidied one. If the two differ, the user cannot
follow along, which is the entire point.

Then stop. Nothing else in the turn:

    - no preamble before it ("You meant out loud. Let me speak it.")
    - no recap, bullets or headings after it
    - no "let me know if you want more"
    - no second, longer written answer alongside it

The transcript replaces the written answer; it is not printed in addition to one.
You composed that text for the ear, so it is short - that is the point, and it is
why this does not flood the chat.

If the speaking itself fails, say so plainly in one line instead - the user heard
nothing and needs to know.

Every spoken text is archived to `~/.kokoro/spoken/` under a timestamp, and the most
recent is also at `~/.kokoro/last-spoken.txt`, so nothing is lost by staying silent.
Show it only if the user asks; to find an older one, list that folder by date.

## When they interrupt: "wait, what was that?"

Audio cannot be rewound by ear, so this is the most common thing they will say.
Handle it in this order, and do the pause FIRST - every second you spend thinking
is another sentence they have to listen past:

```bash
speak --pause      # instant; freezes mid-word
speak --where      # the sentence they just heard, with context
```

`--where` prints the two sentences before, the current one marked `>>`, and the
one after. That is what "that" refers to. Answer from it.

Then:

- **Answer in the chat, as text.** They asked because listening did not work the
  first time; saying it again out loud is the one thing guaranteed not to help.
  Keep it short.
- **Then `speak --resume`** so the summary carries on from exactly where
  it froze, and say in your one line that it is running again.
- **Unless they have moved on.** If the interruption turned into a new question or
  a new instruction, run `speak --hush` instead and drop the rest - do
  not resume a summary they have stopped caring about.

"Say that again" is different: they want to HEAR it, not read it. Pause, then
speak just that one sentence with `--bg`, then resume.

## Letting them read along

`speak --follow` prints each sentence in the terminal as it is spoken,
which is the answer to "I want to see it as well as hear it". Mention it if they
say they cannot keep up. It is a separate terminal command - it does not change
what you print in the chat.

## Staying in voice mode

If the user says they want voice mode on, keep using this skill for substantive
answers until they say otherwise. Keep obeying short factual interruptions
("what's the file called?") in text - speaking a one-line fact is slower than
reading it.
