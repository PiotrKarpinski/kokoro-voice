"""Windows. NOT IMPLEMENTED - see PORTING.md.

The signal-based pause has no equivalent here, so this backend wants a
different shape: play in-process with `sounddevice` and control it with
threads rather than signals. That approach would suit the other platforms too,
so a good Windows port probably simplifies all three.
"""
_MSG = ("kokoro-voice has no Windows backend yet. See PORTING.md - it needs "
        "in-process playback rather than a player process, because Windows "
        "has no SIGSTOP.")

AUDIO = ""
def play(path):      raise NotImplementedError(_MSG)
def stop_all():      raise NotImplementedError(_MSG)
def pause_all():     raise NotImplementedError(_MSG)
def resume_all():    raise NotImplementedError(_MSG)
def background_app(): pass
def float_window(root): pass

def on_screen(x, y, w, h):
    # No display enumeration yet; trust the saved position.
    return True
