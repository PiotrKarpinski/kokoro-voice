# Porting to Linux or Windows

Everything here works on macOS only today. That is a plumbing limit, not an
engine limit — Kokoro, PyTorch, the daemon, the Unix socket and the pause
mechanism are all portable. What follows is an audit of every platform-specific
call, so you do not have to go looking.

**Nothing below has been tested off macOS.** Treat the Linux notes as a starting
point, not a recipe.

## What is actually macOS-specific

| What | Where | Notes |
|---|---|---|
| `afplay` | `bin/speak.py:385`, `bin/speakd.py:99` | The only two places audio is played |
| `afplay` by name | 5 `pkill` calls in `bin/speak.py`, 1 in `bin/speakd.py` | Stop / pause / resume target the process by name |
| `brew install espeak-ng` | `install.sh` | Kokoro needs espeak-ng for out-of-dictionary words |
| `uname = Darwin` gate | `install.sh:9` | Deliberate; remove it when a platform works |
| Cocoa window behaviour | `bin/hud.py:22`, `:153` | Already wrapped in `try/except` — absent, the window still runs |
| `SF Pro Text` font | `bin/hud.py`, several | Falls back to a default font automatically |

## What already works everywhere

Worth knowing before you start rewriting things that are not broken:

- `pgrep -f`, `pkill -f`, `pkill -x` — standard on Linux.
- `pkill -STOP` / `-CONT` — the instant-pause trick is plain POSIX signals.
- `ps -o rss=` — the daemon's memory ceiling.
- Unix domain sockets, tkinter, Kokoro, PyTorch, soundfile.

## Linux: roughly forty lines

1. **Audio.** Replace the two `afplay` calls with a helper that picks the first
   of `paplay`, `aplay`, `ffplay` that exists, and put the chosen binary's name
   in one constant so the six `pkill` sites use it too. That constant is the
   whole port, really.
2. **Installer.** Swap the Homebrew branch for `apt-get install espeak-ng` or
   `dnf install espeak-ng`, and drop the Darwin gate.
3. **The window.** It will run as-is, minus the all-Spaces and no-focus-stealing
   behaviour, which are Cocoa-only. An X11 equivalent would use
   `_NET_WM_STATE_ABOVE` and `_NET_WM_STATE_STICKY`. Ship without it first.
4. **tkinter** is often a separate package: `apt install python3-tk`.

## Windows: a bigger job

No `afplay`, no `pkill`, and no `SIGSTOP` — so pause cannot work the way it does
here, and process control needs rewriting rather than substituting. The cleaner
route is probably to play audio in-process (`sounddevice`) and control it with
threads instead of signals, which would also simplify the Unix side. Worth doing
properly or not at all.

## If you port it

Open a PR. Keep the platform branches small and obvious — one helper for audio,
one for the installer — rather than scattering `if platform ==` through the
code. And say in the PR what you actually ran it on.
