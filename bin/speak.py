#!/usr/bin/env python3
"""Speak text aloud with Kokoro (local, PyTorch + misaki).

  echo "hello" | speak          speak "hello" -v am_michael -s 1.1
  speak --list                  recent spoken texts
  speak --replay                say the last one again
  speak --status / --stop       inspect or stop the warm daemon

Uses a warm daemon so the voice starts immediately. If the daemon cannot be
started for any reason, generation falls back in-process - slower to start,
but it always speaks.
"""
import argparse, datetime, json, os, pathlib, queue, re, shutil, socket, subprocess, sys, tempfile, threading, time, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

HERE      = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import platforms                   # all OS-specific behaviour lives here
DATA      = pathlib.Path(os.environ.get("KOKORO_HOME",
                         pathlib.Path.home()/".kokoro"))
DATA.mkdir(parents=True, exist_ok=True)
ARCHIVE   = DATA/"spoken"
SOCK      = DATA/".speakd.sock"
LOG       = DATA/".speakd.log"
BEATS     = DATA/".beats.log"
HUSHF     = DATA/".hush"          # touched by --hush; consumers stop at it
SPEEDF    = DATA/".speed"         # persistent default speaking rate
NOW       = DATA/".now-playing"   # what is sounding right now
PAUSE     = DATA/".paused"
HUDON     = DATA/".hud-on"        # transcript window follows along automatically
CONFIG    = DATA/"config.json"    # every tunable lives here

DEFAULTS = {
    "voice":             "af_heart",
    "speed":             1.0,
    "hud":               False,     # floating transcript window
    "keep_days":         180,       # transcript retention
    "idle_exit_seconds": 900,       # daemon quits after this long unused
    "rss_ceiling_mb":    2600,      # daemon restarts above this
    "mode":              "on-request",  # off | on-request | narrate
}

def load_config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG.read_text()))
    except (OSError, ValueError):
        pass
    # honour the older single-value files so nothing breaks on upgrade
    try:
        cfg["speed"] = float((DATA/".speed").read_text().strip())
    except (OSError, ValueError):
        pass
    if HUDON.exists():
        cfg["hud"] = True
    try:
        explicit = "mode" in json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        explicit = False
    if not explicit and (DATA/".narrate").exists():
        cfg["mode"] = "narrate"
    return cfg

def save_config(cfg):
    CONFIG.write_text(json.dumps({k: v for k, v in cfg.items()
                                  if DEFAULTS.get(k) != v}, indent=2) + "\n")
START     = time.time()

def hushed():
    """True once --hush has been called since this run started."""
    try:
        return HUSHF.stat().st_mtime > START
    except OSError:
        return False
KEEP_DAYS = 180   # overridden by config
SPLIT     = r"(?<=[.!?])\s+"

ap = argparse.ArgumentParser()
ap.add_argument("text", nargs="*")
ap.add_argument("-v", "--voice", default="af_heart")
ap.add_argument("-s", "--speed", type=float, default=None)
ap.add_argument("--save", metavar="WAV", help="also keep the audio here")
ap.add_argument("--list", action="store_true")
ap.add_argument("--replay", action="store_true")
ap.add_argument("--status", action="store_true", help="is the daemon warm?")
ap.add_argument("--stop", action="store_true", help="stop the daemon, free its RAM")
ap.add_argument("--no-daemon", action="store_true", help="generate in-process")
ap.add_argument("--bg", action="store_true",
                help="queue it and return at once - for narration, never blocks")
ap.add_argument("--hush", action="store_true", help="stop speaking right now")
ap.add_argument("--set-speed", type=float, metavar="N",
                help="save the default speaking rate, e.g. 1.2 (1.0 = normal)")
ap.add_argument("--pause", action="store_true", help="freeze playback instantly")
ap.add_argument("--resume", action="store_true", help="carry on from where it froze")
ap.add_argument("--where", action="store_true",
                help="what was just said, for answering 'what was that?'")
ap.add_argument("--follow", action="store_true", help="live transcript as it speaks")
ap.add_argument("--hud", choices=["on","off"], nargs="?", const="on",
                help="floating always-on-top transcript window")
ap.add_argument("--title", metavar="TEXT",
                help="what this speech is about; shown in the transcript window")
ap.add_argument("--config", action="store_true", help="show every setting")
ap.add_argument("--set", metavar="KEY=VALUE", action="append",
                help="change a setting, e.g. --set speed=1.2 --set voice=am_michael")
ap.add_argument("--version", action="store_true")
a = ap.parse_args()

ARCHIVE.mkdir(parents=True, exist_ok=True)
MODES = ("off", "on-request", "narrate")
CFG = load_config()

DRY = os.environ.get("KOKORO_DRY_RUN")
def dry_log(kind, **kw):
    """Eval harness: record what would have happened instead of making sound."""
    with open(DATA/"dryrun.jsonl", "a") as f:
        f.write(json.dumps({"kind": kind, "at": time.time(), **kw}) + "\n")

if DRY and (a.hush or a.pause or a.resume or a.where):
    kind = "hush" if a.hush else "pause" if a.pause else "resume" if a.resume else "where"
    dry_log(kind)
    print({"hush": "hushed", "pause": "paused", "resume": "resumed",
           "where": "nothing is playing"}[kind])
    sys.exit(0)

if a.version:
    try:
        man = json.loads((HERE.parent/".claude-plugin/plugin.json").read_text())
        line = f"{man['name']} {man['version']}"
    except (OSError, ValueError, KeyError):
        line = "kokoro-voice (unpackaged)"
    rev = subprocess.run(["git","-C",str(HERE.parent),"rev-parse","--short","HEAD"],
                         capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git","-C",str(HERE.parent),"status","--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    if rev:
        line += f"  ({rev}{'+edits' if dirty else ''})"
    print(line)
    print(f"code  {HERE.parent}")
    print(f"data  {DATA}")
    sys.exit(0)

if a.config:
    print(f"settings in {CONFIG}\n")
    for k in DEFAULTS:
        v, d = CFG[k], DEFAULTS[k]
        print(f"  {k:<18} {str(v):<12} {'(default)' if v == d else '(changed)'}")
    print("\nchange one with:  speak --set speed=1.2")
    sys.exit(0)

if a.set:
    for pair in a.set:
        if "=" not in pair:
            sys.exit(f"expected KEY=VALUE, got {pair!r}")
        k, v = pair.split("=", 1)
        k = k.strip()
        if k not in DEFAULTS:
            sys.exit(f"unknown setting {k!r}. Known: {', '.join(DEFAULTS)}")
        d = DEFAULTS[k]
        try:
            CFG[k] = (v.strip().lower() in ("1","true","yes","on")) if isinstance(d, bool) \
                     else type(d)(v)
        except ValueError:
            sys.exit(f"{k} expects a {type(d).__name__}")
        if k == "voice":
            from normalize import parse_voice
            try:
                parse_voice(CFG[k])
            except ValueError as e:
                sys.exit(f"voice: {e}. Use a name like af_heart, or a blend like af_heart:0.7,bf_emma:0.3")
        if k == "mode":
            if CFG[k] not in MODES:
                sys.exit(f"mode must be one of: {', '.join(MODES)}")
            (DATA/".narrate").unlink(missing_ok=True)
            if CFG[k] == "off":
                subprocess.run([sys.executable, __file__, "--hush"], capture_output=True)
        print(f"{k} = {CFG[k]}")
    save_config(CFG)
    (DATA/".speed").unlink(missing_ok=True)      # superseded by config.json
    HUDON.touch() if CFG["hud"] else HUDON.unlink(missing_ok=True)
    sys.exit(0)

if a.set_speed is not None:
    SPEEDF.write_text(str(a.set_speed))
    print(f"default speaking rate set to {a.set_speed}")
    sys.exit(0)

# What this speech is about, shown in the transcript window. Falls back to the
# project directory, which is usually the right answer anyway.
TITLE = (a.title or pathlib.Path.cwd().name or "")[:60]

if a.speed is None:
    a.speed = CFG["speed"]
if not a.voice or a.voice == "af_heart":
    a.voice = CFG["voice"]

# ---------------------------------------------------------------- maintenance
def maintain():
    """Cheap, self-healing, never fatal. Runs every invocation."""
    now = time.time()
    for d in pathlib.Path(tempfile.gettempdir()).glob("speak.*"):
        try:
            if now - d.stat().st_mtime > 3600:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass
    cutoff = now - CFG["keep_days"]*86400
    for f in ARCHIVE.glob("*.txt"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass
    for f in (LOG, BEATS):
        if f.exists() and f.stat().st_size > 1_000_000:
            f.unlink(missing_ok=True)
maintain()

# --------------------------------------------------------------------- daemon
def mine(script):
    """pgrep pattern for a daemon or window belonging to THIS install only.
    Matching on the script name alone let a second install on the same machine
    find, restart and kill the first one's processes."""
    return f"{script} --home {re.escape(str(DATA.resolve()))}$"

def pids(script):
    out = subprocess.run(["pgrep", "-f", mine(script)], capture_output=True, text=True).stdout
    return [int(x) for x in out.split()]

def connect(timeout=2.0):
    if not SOCK.exists():
        return None
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(SOCK))
        return s
    except OSError:
        SOCK.unlink(missing_ok=True)      # stale socket from a killed daemon
        return None

def code_stamp():
    return max(p.stat().st_mtime for p in (HERE/"speakd.py", HERE/"speak.py") if p.exists())

def daemon_is_current():
    s = connect()
    if not s:
        return False
    try:
        f = s.makefile("rw")
        f.write(json.dumps({"ping": 1})+"\n"); f.flush()
        return json.loads(f.readline()).get("stamp", 0) >= code_stamp()
    except Exception:
        return False
    finally:
        s.close()

def stop_daemon():
    try:
        found = pids("speakd.py")
        for pid in found:
            os.kill(pid, 15)
        SOCK.unlink(missing_ok=True)
        return len(found)
    except Exception:
        return 0

def start_daemon(wait=90):
    with open(LOG, "a") as log:
        subprocess.Popen([sys.executable, str(HERE/"speakd.py"), "--home", str(DATA.resolve())], stdout=log, stderr=log,
                         start_new_session=True)
    deadline = time.time() + wait
    while time.time() < deadline:
        if (s := connect()):
            return s
        time.sleep(0.15)
    return None

def hud_running():
    return bool(pids("hud.py"))

if a.status:
    s = connect()
    if s:
        s.close()
        fresh = "current" if daemon_is_current() else "STALE (will restart on next use)"
        rss = subprocess.run(["ps","-o","rss=","-p", str(pids("speakd.py")[0])],
              capture_output=True, text=True).stdout.strip()
        print(f"daemon: warm, {fresh}, {int(rss)/1024:.0f} MB resident")
    else:
        print("daemon: not running (next speak starts it, ~4s)")
    if CFG["hud"]:
        if hud_running():
            print("window: running")
        else:
            why = ""
            try:
                tail = [l for l in (DATA/".hud.log").read_text().splitlines()
                        if l.strip() and "Task policy set failed" not in l]
                why = tail[-1][:100] if tail else ""
            except OSError:
                pass
            print("window: NOT running" + (f" - last error: {why}" if why else " (starts on next speech)"))
    else:
        print("window: off (kokoro --hud on)")
    sys.exit(0)

if a.stop:
    print(f"stopped {stop_daemon()} daemon process(es)")
    sys.exit(0)

def hud_start():
    if not hud_running():
        subprocess.Popen([sys.executable, str(HERE/"hud.py"), "--home", str(DATA.resolve())], stdout=open(DATA/".hud.log", "a"),
                         stderr=subprocess.STDOUT, start_new_session=True)

if a.hud:
    if a.hud == "on":
        HUDON.touch(); hud_start(); print("transcript window on")
    else:
        HUDON.unlink(missing_ok=True)
        [os.kill(pid, 15) for pid in pids("hud.py")]
        print("transcript window off")
    sys.exit(0)

if HUDON.exists() and not (a.list or a.status or a.where):
    hud_start()

if a.pause:
    PAUSE.touch()
    platforms.pause_all()
    print("paused")
    sys.exit(0)

if a.resume:
    PAUSE.unlink(missing_ok=True)
    platforms.resume_all()
    print("resumed")
    sys.exit(0)

if a.where:
    try:
        st = json.loads(NOW.read_text())
    except (OSError, ValueError):
        sys.exit("nothing is playing")
    i, sents = st["index"], st["sentences"]
    lo = max(0, i-2)
    for n in range(lo, min(len(sents), i+2)):
        mark = ">>" if n == i else "  "
        print(f"{mark} {sents[n]}")
    print(f"\n(sentence {i+1} of {st['total']}"
          f"{', paused' if PAUSE.exists() else ''})")
    sys.exit(0)

if a.follow:
    print("following (ctrl-c to stop)\n")
    seen = -1
    try:
        while True:
            try:
                st = json.loads(NOW.read_text())
                if st["index"] != seen:
                    seen = st["index"]
                    print(f"  {st['current']}", flush=True)
            except (OSError, ValueError):
                pass
            time.sleep(0.15)
    except KeyboardInterrupt:
        sys.exit(0)

if a.hush:
    PAUSE.unlink(missing_ok=True)
    platforms.resume_all()   # un-freeze first
    NOW.unlink(missing_ok=True)
    HUSHF.touch()                       # stops in-flight clients between chunks
    s = connect()
    if s:
        try:
            f = s.makefile("rw")
            f.write(json.dumps({"drain": 1})+"\n"); f.flush(); f.readline()
        finally:
            s.close()
    platforms.stop_all()
    print("hushed")
    sys.exit(0)

# ----------------------------------------------------------------- input text
if a.list:
    files = sorted(ARCHIVE.glob("*.txt"), reverse=True)[:15]
    if not files:
        sys.exit("nothing spoken yet")
    for f in files:
        print(f"{f.stem}  {f.read_text().strip().splitlines()[0][:78]}")
    sys.exit(0)

if CFG["mode"] == "off":
    sys.exit("voice is off - turn it on with: kokoro --set mode=on-request")

raw = (DATA/"last-spoken.txt").read_text() if a.replay else \
      (" ".join(a.text) if a.text else sys.stdin.read())

from normalize import for_ear           # the ear rules, enforced in code
t = for_ear(raw)
if not t:
    sys.exit("nothing to say")

if len(t.split()) >= 40:                 # long enough to be a summary
    try:
        (DATA/".last-summary").write_text(str(time.time()))
    except OSError:
        pass

if DRY:
    dry_log("speak", bg=bool(a.bg), title=globals().get("TITLE", ""), text=t,
            words=len(t.split()), mode=CFG["mode"])
    sys.exit(0)

# --------------------------------------------------------- fire and forget
if a.bg:
    if not daemon_is_current():
        stop_daemon(); start_daemon()
    s = connect(timeout=10)
    if s:
        try:
            f = s.makefile("rw")
            f.write(json.dumps({"bg": 1, "text": t, "voice": a.voice,
                                "speed": a.speed, "title": TITLE})+"\n"); f.flush()
            f.readline()
            with open(BEATS, "a") as bl:
                bl.write(f"{datetime.datetime.now():%H:%M:%S}  {t}\n")
            # Beats are throwaway; a queued SUMMARY is not, so archive by length.
            if len(t.split()) >= 40:
                stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
                (ARCHIVE/f"{stamp}.txt").write_text(t + "\n")
                (DATA/"last-spoken.txt").write_text(t + "\n")
            sys.exit(0)
        finally:
            s.close()
    a.bg = False           # daemon unreachable - fall through and speak inline

# ------------------------------------------------------------------ playback
q, parts, tmpdirs = queue.Queue(), [], set()
SENTS = [x for x in re.split(SPLIT, t.replace("⟪", "").replace("⟫", "")) if x.strip()]

def publish(i):
    try:
        NOW.write_text(json.dumps({
            "index": i, "total": len(SENTS),
            "current": SENTS[i] if i < len(SENTS) else "",
            "sentences": SENTS, "at": time.time(),
            "title": globals().get("TITLE", ""), "pid": os.getpid()}))
    except OSError:
        pass

def player():
    i = 0
    while (p := q.get()) is not None:
        if hushed():
            continue                     # drain the rest without playing it
        publish(i); i += 1
        platforms.play(p)
    try:                                 # clear it only if it is still ours
        if json.loads(NOW.read_text()).get("pid") == os.getpid():
            NOW.unlink()
    except (OSError, ValueError):
        pass
def via_daemon():
    """Ask the daemon to speak and wait until it has. The daemon plays the audio
    itself now - trimmed, joined, no player launched per sentence."""
    if a.no_daemon:
        return False
    if not daemon_is_current():
        stop_daemon()                      # stale code, or nothing there
        if not start_daemon():
            return False
    s = connect(timeout=10)
    if not s:
        return False
    try:
        s.settimeout(None)                 # speaking can outlast any fixed timeout
        f = s.makefile("rw")
        f.write(json.dumps({"text": t, "voice": a.voice, "speed": a.speed, "title": TITLE,
                            "save": str(pathlib.Path(a.save).resolve()) if a.save else None})+"\n")
        f.flush()
        for line in f:
            m = json.loads(line)
            if m.get("done"):
                if a.save:
                    print(a.save)
                return True
            if "error" in m:
                print(f"daemon error: {m['error']}", file=sys.stderr)
                return False
        return False
    except Exception:
        return False
    finally:
        s.close()

def in_process():
    import soundfile as sf
    from kokoro import KPipeline
    tmp = tempfile.mkdtemp(prefix="speak."); tmpdirs.add(tmp)
    pipe = KPipeline(lang_code=a.voice[0], repo_id="hexgrad/Kokoro-82M")
    from normalize import parse_voice
    mix = parse_voice(a.voice)
    voice = mix[0][0] if len(mix) == 1 else sum(w * pipe.load_voice(n) for n, w in mix)
    for i, (_, _, audio) in enumerate(pipe(t.replace("⟪", "").replace("⟫", ""), voice=voice, speed=a.speed,
                                           split_pattern=SPLIT)):
        if hushed():
            break
        p = f"{tmp}/{i:04d}.wav"
        sf.write(p, audio, 24000); parts.append(p); q.put(p)

spoken_by_daemon = via_daemon()
if not spoken_by_daemon:                   # fallback: generate and play right here
    th = threading.Thread(target=player); th.start()
    in_process()
    q.put(None)
    if a.save and parts:
        import numpy as np, soundfile as sf
        sf.write(a.save, np.concatenate([sf.read(p)[0] for p in parts]), 24000)
        print(a.save)

if not a.replay:
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    (ARCHIVE/f"{stamp}.txt").write_text(t + "\n")
(DATA/"last-spoken.txt").write_text(t + "\n")

if not spoken_by_daemon:
    th.join()
for d in tmpdirs:
    shutil.rmtree(d, ignore_errors=True)
