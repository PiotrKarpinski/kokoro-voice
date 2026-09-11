"""Linux. SCAFFOLDING - written from the macOS backend, never run.

Signals and pkill are the same here, so pause and resume should work as-is;
the open question is which player is installed and whether it behaves when
signalled. Delete this notice once you have actually run it, and say in the PR
what you tested on.
"""
import shutil, subprocess

# First one present wins. paplay is quietest about missing sound servers.
AUDIO = next((p for p in ("paplay", "aplay", "ffplay") if shutil.which(p)), "aplay")

def play(path):
    cmd = [AUDIO, path]
    if AUDIO == "ffplay":
        cmd = [AUDIO, "-nodisp", "-autoexit", "-loglevel", "quiet", path]
    subprocess.run(cmd, check=False)

def stop_all():
    subprocess.run(["pkill", "-x", AUDIO], check=False)

def pause_all():
    subprocess.run(["pkill", "-STOP", "-x", AUDIO], check=False)

def resume_all():
    subprocess.run(["pkill", "-CONT", "-x", AUDIO], check=False)

def background_app():
    # No equivalent needed: X11 and Wayland do not follow focus across desktops
    # the way macOS Spaces do.
    pass

def float_window(root):
    # tkinter's own -topmost already applies. Sticking the window to every
    # desktop wants _NET_WM_STATE_STICKY via wmctrl or python-xlib; left out
    # deliberately rather than guessed at.
    pass
