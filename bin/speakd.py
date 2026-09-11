#!/usr/bin/env python3
"""Warm Kokoro daemon. Holds the model in RAM so speaking starts instantly.

Started automatically by `speak`; exits on its own after IDLE_EXIT seconds of
silence, so it is not a permanent resident. Listens on a unix socket in the
user's own directory - no network port.
"""
import gc, json, os, pathlib, queue, shutil, socket, subprocess, sys, tempfile, threading, time, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

HERE      = pathlib.Path(__file__).resolve().parent
DATA      = pathlib.Path(os.environ.get("KOKORO_HOME",
                         pathlib.Path.home()/".kokoro"))
DATA.mkdir(parents=True, exist_ok=True)
SOCK      = DATA/".speakd.sock"
IDLE_EXIT = 900          # 15 min unused -> exit and give the RAM back
RSS_CEIL  = 2600         # MB. Torch grows ~100MB per request; exit and let the
                         # client restart us rather than grow without bound.
SPLIT     = r"(?<=[.!?])\s+"

import torch, soundfile as sf
from kokoro import KPipeline

def rss_mb():
    try:
        out = subprocess.run(["ps","-o","rss=","-p",str(os.getpid())],
                             capture_output=True, text=True).stdout.strip()
        return int(out)/1024
    except Exception:
        return 0.0

def sweep(mine):
    """Drop temp dirs whose client died before it could clean up."""
    now = time.time()
    for d in list(mine):
        try:
            if now - os.path.getmtime(d) > 600:
                shutil.rmtree(d, ignore_errors=True); mine.discard(d)
        except OSError:
            mine.discard(d)

GEN = threading.Lock()        # one generation at a time; torch shares the pipeline
BG  = queue.Queue()           # fire-and-forget narration beats, played in order
NOW   = DATA/".now-playing"   # what is sounding right now, for "what was that?"
PAUSE = DATA/".paused"

pipes = {}
def pipeline(lang):
    if lang not in pipes:
        pipes[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    return pipes[lang]

pipeline("a")            # preload the common case

def bg_worker():
    """Speak queued narration without making the caller wait."""
    while True:
        job = BG.get()
        if job is None:
            break
        tmp = tempfile.mkdtemp(prefix="speak.")
        started = time.time()
        import re as _re
        sents = [x for x in _re.split(r"(?<=[.!?])\s+", job["text"]) if x.strip()]
        def hushed():
            try:
                return os.path.getmtime(str(DATA/".hush")) > started
            except OSError:
                return False
        try:
            if hushed():
                shutil.rmtree(tmp, ignore_errors=True); BG.task_done(); continue
            with GEN, torch.inference_mode():
                chunks = [a for _,_,a in pipeline(job["voice"][0])(
                    job["text"], voice=job["voice"], speed=job.get("speed",1.0),
                    split_pattern=SPLIT)]
            for i, audio in enumerate(chunks):
                if hushed():
                    break
                while PAUSE.exists():        # hold between sentences while paused
                    if hushed():
                        break
                    time.sleep(0.1)
                if hushed():
                    break
                wav = f"{tmp}/{i:04d}.wav"
                sf.write(wav, audio, 24000)
                # Publish position BEFORE playing, so "what was that?" resolves to
                # the sentence the user actually just heard.
                try:
                    NOW.write_text(json.dumps({
                        "index": i, "total": len(chunks),
                        "current": sents[i] if i < len(sents) else "",
                        "sentences": sents, "at": time.time(),
                        "title": job.get("title", "")}))
                except OSError:
                    pass
                subprocess.run(["afplay", wav], check=False)
        except Exception as e:
            print(f"bg error: {e}", flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            if BG.empty():
                NOW.unlink(missing_ok=True)
            BG.task_done()

threading.Thread(target=bg_worker, daemon=True).start()

if SOCK.exists():
    SOCK.unlink()
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
srv.bind(str(SOCK))
os.chmod(SOCK, 0o600)
srv.listen(4)
srv.settimeout(30)

# Restart if the code changed underneath us, so an edited script never runs stale.
STAMP = max(p.stat().st_mtime for p in (HERE/"speakd.py", HERE/"speak.py") if p.exists())
print(f"ready pid={os.getpid()}", flush=True)

last, mine = time.time(), set()
while True:
    try:
        conn, _ = srv.accept()
    except socket.timeout:
        sweep(mine)
        if time.time() - last > IDLE_EXIT and BG.empty():
            break
        continue
    last = time.time()
    with conn:
        f = conn.makefile("rw")
        try:
            req = json.loads(f.readline())
            if req.get("ping"):
                f.write(json.dumps({"stamp": STAMP, "queued": BG.qsize()})+"\n")
                f.flush(); continue
            if req.get("bg"):
                BG.put({"text": req["text"], "voice": req.get("voice","af_heart"),
                        "speed": req.get("speed",1.0), "title": req.get("title","")})
                f.write(json.dumps({"queued": BG.qsize()})+"\n"); f.flush(); continue
            if req.get("drain"):          # stop narration mid-flight
                try:
                    while True: BG.get_nowait(); BG.task_done()
                except queue.Empty: pass
                subprocess.run(["pkill","-f","^afplay"], check=False)
                f.write(json.dumps({"drained": True})+"\n"); f.flush(); continue
            tmp = tempfile.mkdtemp(prefix="speak."); mine.add(tmp)
            voice = req.get("voice", "af_heart")
            # inference_mode stops autograd from retaining a graph per call,
            # which is most of the per-request growth.
            with GEN, torch.inference_mode():
                for i, (_, _, audio) in enumerate(pipeline(voice[0])(
                        req["text"], voice=voice, speed=req.get("speed", 1.0),
                        split_pattern=SPLIT)):
                    p = f"{tmp}/{i:04d}.wav"
                    sf.write(p, audio, 24000)
                    f.write(json.dumps({"wav": p})+"\n"); f.flush()
            f.write(json.dumps({"done": True})+"\n"); f.flush()
            gc.collect()
        except Exception as e:
            try:
                f.write(json.dumps({"error": str(e)})+"\n"); f.flush()
            except Exception:
                pass
    last = time.time()
    sweep(mine)
    if rss_mb() > RSS_CEIL and BG.empty():   # bounded lifetime; client restarts us
        print(f"rss {rss_mb():.0f}MB over ceiling, exiting", flush=True)
        break

srv.close()
for d in mine:
    shutil.rmtree(d, ignore_errors=True)
SOCK.unlink(missing_ok=True)
