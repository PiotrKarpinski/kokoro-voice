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
