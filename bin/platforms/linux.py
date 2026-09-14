"""Linux. SCAFFOLDING - written from the macOS backend, never run.

Signals and pkill are the same here, so pause and resume should work as-is;
the open question is which player is installed and whether it behaves when
signalled. Delete this notice once you have actually run it, and say in the PR
what you tested on.
"""
import os, shutil, signal, subprocess, time

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

def on_screen(x, y, w, h):
    # No display enumeration yet; trust the saved position.
    return True

def show_window(root):
    root.attributes("-alpha", 1.0)
    root.deiconify()
    root.attributes("-topmost", True)

def hide_window(root):
    root.withdraw()

class Sound:
    """SCAFFOLDING, never run. A player process per sound, paused with signals,
    position estimated from the wall clock."""

    def __init__(self, path):
        self.path = str(path); self.p = None; self.t0 = 0.0; self.paused_at = None; self.paused_for = 0.0

    def play(self):
        cmd = [AUDIO, self.path]
        if AUDIO == "ffplay":
            cmd = [AUDIO, "-nodisp", "-autoexit", "-loglevel", "quiet", self.path]
        self.p = subprocess.Popen(cmd); self.t0 = time.time()

    def pause(self):
        if self.p and self.paused_at is None:
            os.kill(self.p.pid, signal.SIGSTOP); self.paused_at = time.time()

    def resume(self):
        if self.p and self.paused_at is not None:
            os.kill(self.p.pid, signal.SIGCONT); self.paused_for += time.time() - self.paused_at; self.paused_at = None

    def stop(self):
        if self.p and self.p.poll() is None:
            self.resume(); self.p.terminate()

    def position(self):
        end = self.paused_at or time.time()
        return max(0.0, end - self.t0 - self.paused_for)

    def duration(self):
        return 0.0

    def finished(self):
        return self.p is None or (self.paused_at is None and self.p.poll() is not None)


def pump(seconds):
    time.sleep(seconds)
