# Porting to Linux or Windows

Everything here works on macOS only today. That is a plumbing limit, not an
engine limit — Kokoro, PyTorch, the daemon, the Unix socket and the pause
mechanism are all portable. What follows is an audit of every platform-specific
call, so you do not have to go looking.

**Nothing below has been tested off macOS.** Treat the Linux notes as a starting
point, not a recipe.

## Where the OS-specific code lives

All of it is in `bin/platforms/`. One module per platform:

    bin/platforms/__init__.py   picks a backend from sys.platform
    bin/platforms/darwin.py     macOS - the tested one
    bin/platforms/linux.py      scaffolding, never run
    bin/platforms/windows.py    not implemented

A backend is seven functions:

| | |
|---|---|
| `AUDIO` | name of the player process, for stopping it by name |
| `play(path)` | play one wav, blocking until done |
| `stop_all()` | kill playback now |
| `pause_all()` / `resume_all()` | freeze and unfreeze, resumably |
| `background_app()` | stop the transcript window stealing focus |
| `float_window(root)` | keep it above others, on every desktop |

The last two may be no-ops — the window still works without them.

**If you are writing `if sys.platform` anywhere outside that package, that is
the bug.** The rest of the codebase should never know what it is running on.

## What already works everywhere

Worth knowing before you rewrite things that are not broken:

- `pgrep -f`, `pkill -f`, `pkill -x` - standard on Linux.
- `pkill -STOP` / `-CONT` - the instant-pause trick is plain POSIX signals.
- `ps -o rss=` - the daemon's memory ceiling.
- Unix domain sockets, tkinter, Kokoro, PyTorch, soundfile.

## Linux: mostly written already

`bin/platforms/linux.py` exists as scaffolding - player detection, and the same
signal-based pause, which should carry over unchanged. It has never been run.
What is left:

1. **Try it.** Check your player actually survives being signalled mid-file.
2. **Installer.** Swap the Homebrew branch in `install.sh` for `apt-get install
   espeak-ng` or `dnf install espeak-ng`, and drop the `uname = Darwin` gate.
3. **tkinter** is often a separate package: `apt install python3-tk`.
4. **The window** runs as-is, minus all-Spaces and focus behaviour. An X11
   version would set `_NET_WM_STATE_ABOVE` and `_NET_WM_STATE_STICKY` in
   `float_window()`. Ship without it first.

Then delete the "never run" notice at the top of the module and say in the PR
what you tested on.

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
