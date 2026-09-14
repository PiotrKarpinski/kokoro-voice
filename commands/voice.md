---
description: Voice - speak a summary, or switch mode (on / narrate / off / status)
---

Follow the **voice** skill. Argument (may be empty): $ARGUMENTS

- **empty** - speak a summary of this session: what was asked, what changed, the
  outcome, and anything still open. On-request rules: `--bg`, `--title`, then the
  transcript as a blockquote and nothing else.
- **`on`** - `kokoro --set mode=on-request`
- **`narrate`** - `kokoro --set mode=narrate`
- **`off`** - `kokoro --set mode=off` (this also stops anything playing)
- **`status`** - report the mode from `kokoro --config`, in one line.
- **anything else** - literal text to read, or a subject to summarise aloud.

After a mode change, confirm in one line and mention it takes effect from the
next message, because the hook carrying the mode runs when a message is sent.
