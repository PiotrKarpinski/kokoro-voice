#!/usr/bin/env python3
"""Always-on-top transcript. Shows itself while Kokoro is speaking, hides after.

Reads the daemon's live position, so the current sentence is highlighted in sync
with what you are hearing. Drag to move. Double-click to pause or resume.
"""
import json, math, os, pathlib, random, subprocess, sys, tkinter as tk, time

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
root.attributes("-alpha", 0.0)         # invisible until there is speech; never withdrawn
root.configure(bg=BG)

W, H = 470, 600
DEFAULT_POS = (root.winfo_screenwidth() - W - 28, 48)

def target_pos():
    """The saved position if it is on a connected display, else the default."""
    try:
        x, y = (int(v) for v in json.loads(POS.read_text()))
    except Exception:
        return DEFAULT_POS
    try:
        if not platforms.on_screen(x, y, W, H):
            return DEFAULT_POS
    except Exception:
        pass
    return x, y

x, y = target_pos()
root.geometry(f"{W}x{H}+{x}+{y}")

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

# ---- the face: a composed executive under the transcript (bin/face.py) -----
import face
FACE_FRAMES = face.frames()                       # every mouth step, eyes open and shut

def _darker(hexcol, f=0.72):
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (int(r * f), int(g * f), int(b * f))

PALETTE = {                                       # the window's blues, by part of the picture
    "s0": "#1f2f52", "s1": "#34508c", "s2": "#5a7fcf", "s3": ACCENT, "s4": "#d2e0ff",   # skin
    "cable": "#2f4f96", "cable2": "#1e3466", "node": "#9fbcff", "pulse": "#d6e4ff",   # cable hair
    "iris": "#5a82d6", "pupil": "#0f1a33", "white": "#6d8cc8",   # soft, not glowing
    "lid": "#16244a", "brow": "#2a4478",
    "lip": "#b3c9ff", "void": "#0b1224", "teeth": "#e6eeff",
    "cloth": "#1a2744", "lapel": "#5a7fcf", "shirt": "#d2e0ff", "bg": BG,
}
head = tk.Text(root, bg=BG, bd=0, highlightthickness=0, height=face.ROWS, width=face.COLS,
               font=("Menlo", 7), cursor="arrow", padx=0, pady=0, wrap="none",
               spacing1=0, spacing2=0, spacing3=0)
head.pack(side="bottom", pady=(0, 10))
for kind, colour in PALETTE.items():
    head.tag_config(kind, foreground=colour)
    head.tag_config(kind + "_scan", foreground=_darker(colour, 0.88))   # faint scanlines
    head.tag_config(kind + "_dim", foreground=_darker(colour, 0.50))    # paused
blink = {"until": 0.0, "next": time.time() + random.uniform(2, 5)}

def render_head(level, paused):
    now = time.time()
    if now >= blink["next"]:
        blink["until"], blink["next"] = now + 0.13, now + random.uniform(3, 7)
    eyes = not (paused or now < blink["until"])
    step = 0 if paused else min(face.JAW_STEPS - 1, int(level * face.JAW_STEPS))
    rows = FACE_FRAMES[(step, eyes)]
    phase = int(now * 10)                             # light pulses run down the cables
    args = []
    for r, row in enumerate(rows):
        suffix = "_dim" if paused else ("_scan" if r % 2 else "")
        run, tag = "", None
        for c, (ch, kind) in enumerate(row):
            if not paused and kind in ("cable", "cable2") and (r - phase + c % 5) % 9 == 0:
                kind = "pulse"
            t = kind + suffix
            if t != tag and run:
                args += [run, tag]; run = ""
            tag = t; run += ch
        if run:
            args += [run, tag]
        if r < len(rows) - 1:
            args += ["\n", "bg"]
    head.config(state="normal")
    head.delete("1.0", "end")
    head.insert("end", *args)
    head.config(state="disabled")

def mouth_level(st, paused):
    """The player publishes the real loudness; until it does, fake the chatter."""
    if paused:
        return 0.0
    lvl = st.get("level")
    if isinstance(lvl, (int, float)):
        return max(0.0, min(1.0, float(lvl)))
    return abs(math.sin(time.time() * 11)) * random.uniform(0.45, 1.0)

txt = tk.Text(root, bg=BG, fg=FG_NEXT, bd=0, highlightthickness=0, wrap="word",
              font=("SF Pro Text", 13), spacing1=3, spacing3=3, padx=12, pady=8,
              cursor="arrow")
txt.pack(fill="both", expand=True, padx=4, pady=(4, 2))
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
for w in (bar, title, txt, head):
    w.bind("<Button-1>", start_drag)
    w.bind("<B1-Motion>", on_drag)
    w.bind("<ButtonRelease-1>", end_drag)
    w.bind("<Double-Button-1>", toggle)

shown, last_key = False, None

def ensure_on_screen():
    """macOS can move a window while it is hidden: a live one was found at
    x=-455 with a saved position of 1246. Put it back before every show."""
    try:
        root.update_idletasks()
        if not platforms.on_screen(root.winfo_x(), root.winfo_y(), W, H):
            px, py = target_pos()
            root.geometry(f"+{px}+{py}")
    except Exception:
        pass

MY_STAMP = pathlib.Path(__file__).stat().st_mtime

def tick():
    global shown, last_key
    try:                      # the daemon restarts itself on a code change;
        if pathlib.Path(__file__).stat().st_mtime != MY_STAMP:   # so must this
            os.execv(sys.executable, [sys.executable, *sys.argv])   # keep the --home tag
    except OSError:
        pass
    st = None
    try:
        st = json.loads(NOW.read_text())
        # "at" only moves when a sentence starts, so a pause freezes it. Staleness
        # means "nothing is really playing" - never true while paused on purpose.
        if not PAUSED.exists() and time.time() - st.get("at", 0) > 90:
            st = None
    except Exception:
        st = None

    if st is None:
        if shown:
            try:
                platforms.hide_window(root)
            except Exception as e:
                print(f"hide: {e}", file=sys.stderr); root.withdraw()
            shown = False
        root.after(200, tick); return

    if not shown:
        ensure_on_screen()
        try:                      # never Tk's deiconify on macOS: it activates the app
            platforms.show_window(root)          # and pulls you out of a full-screen chat
        except Exception as e:
            print(f"show: {e}", file=sys.stderr); root.deiconify()
        shown = True

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
    render_head(mouth_level(st, paused), paused)
    root.after(80, tick)

def join_all_spaces():
    try:
        platforms.float_window(root)
    except Exception as e:
        print(f"spaces: {e}", file=sys.stderr)

root.update()                          # mapped, but still fully transparent
platforms.hide_window(root)
root.after(400, join_all_spaces)      # NSWindow must exist first
tick()
root.mainloop()
