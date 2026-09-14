"""macOS. The reference backend - this one is tested."""
import subprocess

AUDIO = "afplay"

def play(path):
    subprocess.run([AUDIO, path], check=False)

def stop_all():
    subprocess.run(["pkill", "-x", AUDIO], check=False)

def pause_all():
    subprocess.run(["pkill", "-STOP", "-x", AUDIO], check=False)

def resume_all():
    subprocess.run(["pkill", "-CONT", "-x", AUDIO], check=False)

def background_app():
    """Accessory apps cannot take foreground focus, so showing the transcript
    window never drags the user to another Space."""
    from AppKit import NSApp, NSApplicationActivationPolicyAccessory
    NSApp().setActivationPolicy_(NSApplicationActivationPolicyAccessory)

def float_window(root):
    from AppKit import (NSApp, NSWindowCollectionBehaviorCanJoinAllSpaces,
                        NSWindowCollectionBehaviorStationary,
                        NSWindowCollectionBehaviorFullScreenAuxiliary,
                        NSFloatingWindowLevel)
    for w in NSApp().windows():
        w.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces |
            NSWindowCollectionBehaviorStationary |
            NSWindowCollectionBehaviorFullScreenAuxiliary)
        w.setLevel_(NSFloatingWindowLevel)
        try:
            w.setHidesOnDeactivate_(False)
            w.resignKeyWindow()
        except Exception:
            pass

def on_screen(x, y, w, h):
    """Is the window's title strip on any connected display? Saved positions
    outlive monitors; without this a window dragged to an unplugged screen
    opens where nobody can see it."""
    from AppKit import NSScreen
    screens = NSScreen.screens()
    main_h = screens[0].frame().size.height        # Cocoa is bottom-left, Tk top-left
    cx, ty = x + w / 2, y + 12
    for sc in screens:
        f = sc.frame()
        left, top = f.origin.x, main_h - (f.origin.y + f.size.height)
        if left <= cx <= left + f.size.width and top <= ty <= top + f.size.height:
            return True
    return False

def _windows():
    from AppKit import NSApp
    return list(NSApp().windows())

def show_window(root):
    """Show WITHOUT activating the app. Tk's deiconify makes Python the
    frontmost app, which drags a user out of a full-screen chat to another
    desktop. Ordering the NSWindow front regardless does not activate - checked
    against the frontmost-app list, step by step."""
    from AppKit import NSFloatingWindowLevel
    float_window(root)                       # re-assert: the level had been lost on a live window
    for w in _windows():
        w.setLevel_(NSFloatingWindowLevel)
        w.setIgnoresMouseEvents_(False)
        w.setAlphaValue_(1.0)
        w.orderFrontRegardless()

def hide_window(root):
    """Transparent and click-through instead of withdrawn, so showing it again
    never has to go through Tk's activating deiconify."""
    for w in _windows():
        w.setAlphaValue_(0.0)
        w.setIgnoresMouseEvents_(True)
