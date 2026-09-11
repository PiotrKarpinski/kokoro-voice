---
name: narrate
description: Narrate work aloud as it happens - short spoken beats while working ("reading the config", "tests passing"), then a spoken summary at the end. Use when narration mode is switched on, or when the user asks to be told what you are doing as you do it, to follow along out loud, or for a running commentary. Builds on the speak skill. Not for one-off requests to say something aloud - that is the speak skill alone.
---

# Narrating work out loud

The user is listening while you work, probably not watching the screen. Narration
is a progress signal, not a transcript.

## The beats

Speak a beat with `--bg`, which queues it and returns in about thirty
milliseconds. It never blocks, and beats always play in the order you sent them:

```bash
speak --bg --title "what you are working on" "Reading the movement script."
```

**Never use plain `speak` for a beat.** That waits for playback and would stall
the work. `--bg` only.

### What a beat sounds like

Three to eight words. A fragment is fine. Say what you are doing, and why only
when the why is not obvious:

    Reading the movement script.
    Found it - the timer resets on landing.
    Patching that now.
    Tests passing.
    Committing.

### When to speak one

Narrate **meaningful steps**, not tool calls. Good moments:

- starting a distinct phase of the work
- finding the thing you were looking for, or finding out you were wrong
- making a change that matters
- a result arriving: tests, a build, a benchmark
- hitting something unexpected that changes the plan

Stay quiet for: reading a second file, listing a directory, thinking, retrying,
anything that happens in under a second.

**Aim for three to eight beats in a normal task.** Under three and the user is
listening to silence; over about ten and it turns into chatter they cannot skim
past. Audio cannot be skimmed - that is the whole reason to be sparing.

### Never speak aloud

Paths, code, commands, flags, identifiers, long numbers, or anything from a
credential or key. The ear rules in the **speak** skill apply to every beat - read
it for the pronunciation traps, especially units and decimals.

**Filenames are the one that slips through.** A file extension spoken aloud comes
out letter by letter and sounds like nonsense. Name the file by what it DOES:

    WRONG  The longest is player dot g d, at sixteen hundred lines.
    RIGHT  The longest is the player movement script, sixteen hundred lines.

    WRONG  Editing kit underscore piece dot g d.
    RIGHT  Editing the kit piece script.

    WRONG  Found it in body underscore gait dot g d.
    RIGHT  Found it in the gait script.

If a file has no meaningful role you can name, say "one of the body scripts" or
just omit it. The user can read the exact name on screen; the beat exists to tell
them where you are, not to dictate a path.

## The summary at the end

When the work is done, speak a closing summary the same way the **speak** skill
describes - written for the ear, roughly 100 to 180 words - but send it with
`--bg` as well, so the turn is not held open waiting for playback:

```bash
cat > /tmp/speak.txt <<'EOF'
<the spoken summary>
EOF
speak --bg < /tmp/speak.txt
```

It is queued behind the beats, so it plays last no matter when you send it.

## What goes in the chat

Narration replaces nothing on screen. Answer in the chat exactly as you normally
would - narration mode is an extra channel, not a substitute. The one-short-line
rule from the **speak** skill does NOT apply here; that rule is for when speech
IS the answer.

The exception is the closing summary: having spoken it, do not also write it out
in full. A normal, useful chat response is right; a duplicated summary is not.

## Stopping

`speak --hush` drops anything queued and stops playback immediately.
Use it the moment the user says stop, be quiet, or shut up.
