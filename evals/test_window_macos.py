#!/usr/bin/env python3
"""The transcript window, measured from outside. macOS only; needs a logged-in
desktop, so it is not in CI.

Runs the real window in a throwaway KOKORO_HOME, drives it with fake speech
state, and checks with the window server - not by eye - the things that broke:

- it never becomes the frontmost app (that is what yanked users out of a
  full-screen chat onto another desktop)
- it floats above normal windows while shown
- it is on screen while speech shows, invisible when it does not
- a saved position off the edge of the display comes back on screen

    ~/.kokoro/.venv/bin/python evals/test_window_macos.py
"""
import ctypes, json, os, pathlib, shutil, subprocess, sys, tempfile, threading, time

import objc
from AppKit import NSScreen, NSWorkspace

ROOT = pathlib.Path(__file__).resolve().parent.parent
cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
ON_SCREEN_ONLY, ALL = 1, 0

PASS = FAIL = 0
def check(label, ok, detail=""):
    global PASS, FAIL
    PASS += ok; FAIL += not ok
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))

def windows_of(pid):
    on = {w["kCGWindowNumber"] for w in objc.objc_object(c_void_p=cg.CGWindowListCopyWindowInfo(ON_SCREEN_ONLY, 0))}
    return [dict(number=w["kCGWindowNumber"], layer=w["kCGWindowLayer"], alpha=float(w.get("kCGWindowAlpha", 1)),
                 x=w["kCGWindowBounds"]["X"], y=w["kCGWindowBounds"]["Y"],
                 width=w["kCGWindowBounds"]["Width"], onscreen=w["kCGWindowNumber"] in on)
            for w in objc.objc_object(c_void_p=cg.CGWindowListCopyWindowInfo(ALL, 0))
            if w["kCGWindowOwnerPID"] == pid]

def speech(home, on):
    f = home/".now-playing"
    if not on:
        f.unlink(missing_ok=True); return
    s = ["Running the test suite first.", "Found it.", "All tests pass now."]
    f.write_text(json.dumps({"index": 1, "total": 3, "current": s[1], "sentences": s,
                             "at": time.time(), "title": "window test"}))

def main():
    home = pathlib.Path(tempfile.mkdtemp(prefix="kv-window-"))
    screen_w = NSScreen.mainScreen().frame().size.width
    (home/".hud-pos").write_text("[-455, 124]")        # the position a live window drifted to
    env = dict(os.environ, KOKORO_HOME=str(home))
    proc = subprocess.Popen([sys.executable, str(ROOT/"bin/hud.py"), "--home", str(home)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    stole = []
    watching = True
    def watch():                                        # sample the frontmost app the whole time
        while watching:
            fa = NSWorkspace.sharedWorkspace().frontmostApplication()
            if fa and fa.processIdentifier() == proc.pid:
                stole.append(time.time())
            time.sleep(0.05)
    threading.Thread(target=watch, daemon=True).start()

    try:
        time.sleep(2.5)
        check("window process starts", proc.poll() is None)
        ws = windows_of(proc.pid)
        check("hidden while nothing is spoken", bool(ws) and all(w["alpha"] == 0 for w in ws),
              f"alpha={[w['alpha'] for w in ws]}")

        for round_ in (1, 2):
            speech(home, True); time.sleep(1.0)
            ws = [w for w in windows_of(proc.pid) if w["width"] > 100]
            w = ws[0] if ws else {}
            check(f"show {round_}: visible", bool(w) and w["alpha"] == 1 and w["onscreen"],
                  f"alpha={w.get('alpha')} onscreen={w.get('onscreen')}")
            check(f"show {round_}: floats above normal windows", w.get("layer", 0) >= 3, f"layer={w.get('layer')}")
            check(f"show {round_}: on the display, not off the edge",
                  bool(w) and 0 <= w["x"] <= screen_w - 100, f"x={w.get('x')} display width={screen_w:.0f}")
            speech(home, False); time.sleep(1.0)
            ws = windows_of(proc.pid)
            check(f"hide {round_}: invisible again", bool(ws) and all(x["alpha"] == 0 for x in ws))

        check("never became the frontmost app", not stole, f"{len(stole)} samples frontmost" if stole else "")
    finally:
        watching = False
        proc.terminate()
        try:
            err = proc.communicate(timeout=3)[1]
        except subprocess.TimeoutExpired:
            proc.kill(); err = ""
        errs = [l for l in (err or "").splitlines() if l.strip() and "Task policy" not in l]
        check("no errors from the window", not errs, errs[-1] if errs else "")
        shutil.rmtree(home, ignore_errors=True)

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)

if __name__ == "__main__":
    if sys.platform != "darwin":
        sys.exit("macOS only")
    main()
