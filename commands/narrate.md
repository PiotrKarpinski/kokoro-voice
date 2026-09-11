---
description: Toggle spoken narration of work (on/off/status)
---

Toggle narration mode. Argument (may be empty): $ARGUMENTS

- **"on"**, or empty when currently off — create `~/.kokoro/.narrate`, then confirm
  in one line. Speak a short confirmation beat too: `kokoro --bg "Narration on."`
- **"off"**, or empty when currently on — run `kokoro --hush`, delete
  `~/.kokoro/.narrate`, confirm in one line.
- **"status"** — say whether `~/.kokoro/.narrate` exists, in one line.

The flag is global, so it applies to every project and every new session until
switched off. It takes effect from the user's NEXT message, because the hook that
carries it runs when a prompt is submitted — mention that once when switching on.

Then follow the **narrate** skill for the rest of the session.
