#!/usr/bin/env python3
"""Always-on-top transcript. Shows itself while Kokoro is speaking, hides after.

Reads the daemon's live position, so the current sentence is highlighted in sync
with what you are hearing. Drag to move. Double-click to pause or resume.
"""
import json, os, pathlib, subprocess, sys, tkinter as tk, time

HERE   = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import platforms
DATA   = pathlib.Path(os.environ.get("KOKORO_HOME",
                      pathlib.Path.home()/".kokoro"))
NOW    = DATA/".now-playing"
PAUSED = DATA/".paused"
POS    = DATA/".hud-pos"

BG, FG_PAST, FG_NOW, FG_NEXT, ACCENT = "#16181d", "#5c6370", "#e8eaed", "#8b919c", "#7aa2f7"

def be_background_app():
    try:
        platforms.background_app()
    except Exception as e:
        print(f"policy: {e}", file=sys.stderr)

def point_tk_at_its_libraries():
    """uv's standalone Pythons ship Tcl/Tk inside the base install, but inside a
    venv Tk does not reliably find them and dies with "Can't find a usable
    init.tcl". It worked, then stopped, within one session. Say where they are
    instead of hoping they are found."""
    for var, name in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
        if os.environ.get(var):
            continue
        for base in (sys.base_prefix, sys.prefix):
            cand = pathlib.Path(base)/"lib"/name
            if (cand/("init.tcl" if name.startswith("tcl") else "tk.tcl")).exists():
                os.environ[var] = str(cand)
                break

point_tk_at_its_libraries()
root = tk.Tk()
be_background_app()
root.title("Transcript")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.configure(bg=BG)

W, H = 470, 250
DEFAULT_POS = (root.winfo_screenwidth() - W - 28, 48)
try:
    x, y = json.loads(POS.read_text())
    try:
        if not platforms.on_screen(int(x), int(y), W, H):   # its monitor is gone
            x, y = DEFAULT_POS
    except Exception:
        pass
except Exception:
    x, y = DEFAULT_POS
root.geometry(f"{W}x{H}+{int(x)}+{int(y)}")

bar = tk.Frame(root, bg=BG, height=26)
bar.pack(fill="x", padx=10, pady=(8, 0))
title = tk.Label(bar, text="● speaking", bg=BG, fg=ACCENT,
                 font=("SF Pro Text", 11, "bold"))
title.pack(side="left")
subject = tk.Label(bar, text="", bg=BG, fg=FG_PAST, font=("SF Pro Text", 11))
subject.pack(side="left", padx=(8, 0))

def say(*args):
    """Run a kokoro command. Never fail silently - a dead button with no
    feedback is worse than an error."""
    exe = HERE/"kokoro"
    cmd = [str(exe), *args] if exe.exists() else ["kokoro", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "failed").strip().splitlines()[0][:40])
    except Exception as e:
        title.config(text=f"! {e}", fg="#e06c75")
        root.after(4000, lambda: title.config(fg=ACCENT))

def button(glyph, cmd, fg=FG_NEXT, size=13):
    b = tk.Label(bar, text=glyph, bg=BG, fg=fg, cursor="pointinghand",
                 font=("SF Pro Text", size), padx=7)
    b.pack(side="right")
    b.bind("<Button-1>", lambda e: cmd())
    b.bind("<Enter>",    lambda e: b.config(fg=FG_NOW))
    b.bind("<Leave>",    lambda e: b.config(fg=fg))
    return b

def close():
    say("--hush")
    root.destroy()
button("✕", close, FG_PAST, 12)   # stopping the voice is what ✕ must mean
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

MY_STAMP = pathlib.Path(__file__).stat().st_mtime

def tick():
    global shown, last_key
    try:                      # the daemon restarts itself on a code change;
        if pathlib.Path(__file__).stat().st_mtime != MY_STAMP:   # so must this
            os.execv(sys.executable, [sys.executable, __file__])
    except OSError:
        pass
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
    try:
        platforms.float_window(root)
    except Exception as e:
        print(f"spaces: {e}", file=sys.stderr)

root.withdraw()
root.after(400, join_all_spaces)      # NSWindow must exist first
tick()
root.mainloop()
