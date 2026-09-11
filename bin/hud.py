#!/usr/bin/env python3
"""Always-on-top transcript. Shows itself while Kokoro is speaking, hides after.

Reads the daemon's live position, so the current sentence is highlighted in sync
with what you are hearing. Drag to move. Double-click to pause or resume.
"""
import json, os, pathlib, subprocess, sys, tkinter as tk, time

HERE   = pathlib.Path(__file__).resolve().parent
DATA   = pathlib.Path(os.environ.get("KOKORO_HOME",
                      pathlib.Path.home()/".kokoro"))
NOW    = DATA/".now-playing"
PAUSED = DATA/".paused"
POS    = DATA/".hud-pos"

BG, FG_PAST, FG_NOW, FG_NEXT, ACCENT = "#16181d", "#5c6370", "#e8eaed", "#8b919c", "#7aa2f7"

def be_background_app():
    """Accessory apps cannot take foreground focus, so showing the window never
    switches the user's Space."""
    try:
        from AppKit import NSApp, NSApplicationActivationPolicyAccessory
        NSApp().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception as e:
        print(f"policy: {e}", file=sys.stderr)

root = tk.Tk()
be_background_app()
root.title("Transcript")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.configure(bg=BG)

W, H = 470, 250
try:
    x, y = json.loads(POS.read_text())
except Exception:
    x, y = root.winfo_screenwidth() - W - 28, 48
root.geometry(f"{W}x{H}+{int(x)}+{int(y)}")

bar = tk.Frame(root, bg=BG, height=26)
bar.pack(fill="x", padx=10, pady=(8, 0))
title = tk.Label(bar, text="● speaking", bg=BG, fg=ACCENT,
                 font=("SF Pro Text", 11, "bold"))
title.pack(side="left")
subject = tk.Label(bar, text="", bg=BG, fg=FG_PAST, font=("SF Pro Text", 11))
subject.pack(side="left", padx=(8, 0))

def say(*args):
    subprocess.run([str(HERE/"kokoro"), *args], capture_output=True)

def button(glyph, cmd, fg=FG_NEXT, size=13):
    b = tk.Label(bar, text=glyph, bg=BG, fg=fg, cursor="pointinghand",
                 font=("SF Pro Text", size), padx=7)
    b.pack(side="right")
    b.bind("<Button-1>", lambda e: cmd())
    b.bind("<Enter>",    lambda e: b.config(fg=FG_NOW))
    b.bind("<Leave>",    lambda e: b.config(fg=fg))
    return b

button("✕", root.destroy, FG_PAST, 12)          # hide the window itself
button("■", lambda: say("--hush"))               # stop speaking for good
btn_play = button("❚❚", lambda: say("--resume" if PAUSED.exists() else "--pause"))

txt = tk.Text(root, bg=BG, fg=FG_NEXT, bd=0, highlightthickness=0, wrap="word",
              font=("SF Pro Text", 13), spacing1=3, spacing3=3, padx=12, pady=8,
              cursor="arrow")
txt.pack(fill="both", expand=True, padx=4, pady=(4, 10))
txt.tag_config("past",  foreground=FG_PAST)
txt.tag_config("now",   foreground=FG_NOW, font=("SF Pro Text", 13, "bold"))
txt.tag_config("next",  foreground=FG_NEXT)
txt.config(state="disabled")

def start_drag(e):
    root._dx, root._dy = e.x_root - root.winfo_x(), e.y_root - root.winfo_y()
def on_drag(e):
    root.geometry(f"+{e.x_root - root._dx}+{e.y_root - root._dy}")
def end_drag(e):
    try: POS.write_text(json.dumps([root.winfo_x(), root.winfo_y()]))
    except OSError: pass
def toggle(e):
    subprocess.run([str(HERE/"kokoro"), "--resume" if PAUSED.exists() else "--pause"],
                   capture_output=True)
for w in (bar, title, txt):
    w.bind("<Button-1>", start_drag)
    w.bind("<B1-Motion>", on_drag)
    w.bind("<ButtonRelease-1>", end_drag)
    w.bind("<Double-Button-1>", toggle)

shown, last_key = False, None

def tick():
    global shown, last_key
    st = None
    try:
        st = json.loads(NOW.read_text())
        if time.time() - st.get("at", 0) > 90:
            st = None
    except Exception:
        st = None

    if st is None:
        if shown:
            root.withdraw(); shown = False
        root.after(200, tick); return

    if not shown:
        root.deiconify()          # topmost is set once at startup; re-asserting
        shown = True              # it here would activate the app and switch Space

    paused = PAUSED.exists()
    title.config(text="paused" if paused else "● speaking",
                 fg=FG_PAST if paused else ACCENT)
    subj = st.get("title", "")
    subject.config(text=f"· {subj}" if subj else "")
    btn_play.config(text="▶" if paused else "❚❚")

    key = (st["index"], len(st["sentences"]), paused)
    if key != last_key:
        last_key = key
        i, sents = st["index"], st["sentences"]
        txt.config(state="normal"); txt.delete("1.0", "end")
        for n, line in enumerate(sents):
            tag = "past" if n < i else ("now" if n == i else "next")
            txt.insert("end", line + "\n\n", tag)
        txt.config(state="disabled")
        txt.see(f"{max(1, 2*i+1)}.0")
    root.after(120, tick)

def join_all_spaces():
    """Without this the window lives on one Space and vanishes when you switch."""
    try:
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
    except Exception as e:
        print(f"spaces: {e}", file=sys.stderr)

root.withdraw()
root.after(400, join_all_spaces)      # NSWindow must exist first
tick()
root.mainloop()
