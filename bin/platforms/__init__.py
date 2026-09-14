"""Platform layer. Everything OS-specific lives here and nowhere else.

Adding a platform means writing one module with the functions below and adding
it to the table in `backend()`. If you find yourself writing `if sys.platform`
anywhere outside this package, that is the bug.

A backend provides:

    AUDIO                name of the player process, for stop/pause by name
    play(path)           play one wav, blocking until it finishes
    stop_all()           kill any playback right now
    pause_all()          freeze playback, resumable
    resume_all()         unfreeze
    background_app()     stop the transcript window taking foreground focus
    float_window(root)   keep it above other windows, on every desktop
    on_screen(x,y,w,h)   is a saved window position on a connected display
    show_window(root)    make the window visible without taking focus
    hide_window(root)    make it invisible
    Sound(path)          a playable sound in this process: play/pause/resume/stop,
                         position(), duration(), finished()
    pump(seconds)        let the platform's event loop run while waiting on a Sound

The last three may be trivial; the window still works without them.
"""
import sys, time

def backend():
    if sys.platform == "darwin":
        from . import darwin as b
    elif sys.platform.startswith("linux"):
        from . import linux as b
    elif sys.platform in ("win32", "cygwin"):
        from . import windows as b
    else:
        raise RuntimeError(
            f"kokoro-voice has no backend for {sys.platform!r}. "
            "See PORTING.md - adding one is a single module.")
    return b

_b = backend()
AUDIO          = _b.AUDIO
play           = _b.play
stop_all       = _b.stop_all
pause_all      = _b.pause_all
resume_all     = _b.resume_all
background_app = _b.background_app
float_window   = _b.float_window
on_screen      = getattr(_b, "on_screen", lambda x, y, w, h: True)
show_window    = getattr(_b, "show_window", lambda root: (root.attributes("-alpha", 1.0), root.deiconify()))
hide_window    = getattr(_b, "hide_window", lambda root: root.withdraw())
Sound          = getattr(_b, "Sound", None)
pump           = getattr(_b, "pump", time.sleep)
