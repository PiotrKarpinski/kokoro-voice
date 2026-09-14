#!/usr/bin/env python3
"""Warm Kokoro daemon. Holds the model in RAM and plays the speech itself.

Playback runs IN this process, on the MAIN thread. Launching afplay per
sentence cost about 1.2 s of dead air every time, and macOS's in-process player
(NSSound) silently does nothing when driven from a background thread. Kokoro
also pads each sentence with ~0.6 s of silence, so sentences are trimmed, joined
with a short gap into one sound per batch, and the first sentence starts playing
as soon as it has been generated.

Threads:
  main       player: plays batches, publishes position and loudness, honours
             pause and hush, exits when idle or over the memory ceiling
  listener   accepts socket requests and queues jobs
  generator  turns queued jobs into trimmed sentence audio, ahead of playback

Started automatically by the client; exits after IDLE_EXIT seconds unused.
Listens on a unix socket in the user's own directory - no network port.
"""
import bisect, gc, json, os, pathlib, queue, re, shutil, socket, subprocess, sys, tempfile, threading, time, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

HERE      = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import platforms
DATA      = pathlib.Path(os.environ.get("KOKORO_HOME",
                         pathlib.Path.home()/".kokoro"))
DATA.mkdir(parents=True, exist_ok=True)
SOCK      = DATA/".speakd.sock"
NOW       = DATA/".now-playing"   # what is sounding, for the window and "what was that?"
PAUSE     = DATA/".paused"
HUSH      = DATA/".hush"
IDLE_EXIT = 900          # 15 min unused -> exit and give the RAM back
RSS_CEIL  = 2600         # MB. Torch grows per request; exit when idle above this and
                         # let the client restart us, rather than grow without bound.
SPLIT     = r"(?<=[.!?])\s+"
SR        = 24000
KEEP      = int(0.05 * SR)        # silence kept either side of a sentence
GAP_S     = 0.12                  # pause put back between sentences
PREROLL   = 0.10                  # start the next batch this early: macOS takes ~140 ms to
                                  # start a sound, and the overlap is trimmed silence
THRESH    = 10 ** (-40 / 20)      # below -40 dBFS counts as silence
ENV_HZ    = 20                    # loudness samples per second, for the mouth

import numpy as np, torch, soundfile as sf
from kokoro import KPipeline
from normalize import plain, segments, pause_after, sentence_speed, parse_voice

GAP = np.zeros(int(GAP_S * SR), dtype="float32")

def rss_mb():
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                             capture_output=True, text=True).stdout.strip()
        return int(out) / 1024
    except Exception:
        return 0.0

GEN   = threading.Lock()
pipes = {}
def pipeline(lang):
    if lang not in pipes:
        pipes[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    return pipes[lang]

pipeline("a")            # preload the common case before accepting anyone

_VOICES = {}
def voice_for(spec):
    """A voice name, or a weighted blend of several: their style vectors
    averaged once and cached. A blend costs one small download per extra voice."""
    if spec not in _VOICES:
        mix = parse_voice(spec)
        if len(mix) == 1:
            _VOICES[spec] = mix[0][0]
        else:
            p = pipeline(mix[0][0][0])
            _VOICES[spec] = sum(w * p.load_voice(name) for name, w in mix)
    return _VOICES[spec]

# ---------------------------------------------------------------- jobs
class Job:
    def __init__(self, req):
        self.text      = req["text"]
        self.voice     = req.get("voice", "af_heart")
        self.speed     = req.get("speed", 1.0)
        self.title     = req.get("title", "")
        self.save      = req.get("save")
        self.marked    = [x for x in re.split(SPLIT, self.text) if x.strip()]   # with emphasis
        self.sentences = [plain(x) for x in self.marked]                        # as shown
        self.created   = time.time()
        self.chunks    = queue.Queue()      # (sentence index, trimmed audio, pause before), then None
        self.done      = threading.Event()  # set once spoken, stopped, or dropped
        self.audio     = []                 # everything played, for --save

JOBS     = queue.Queue()        # waiting to be played, in order
GENQ     = queue.Queue()        # waiting to be generated, same order
ENQUEUE  = threading.Lock()     # keeps those two orders identical
STOP_AT  = [0.0]                # drain time: jobs created before it are dropped
ACTIVE   = [time.time()]

def hushed(job):
    if STOP_AT[0] > job.created:
        return True
    try:
        return HUSH.stat().st_mtime > job.created
    except OSError:
        return False

def trim(audio):
    a = np.asarray(audio, dtype="float32")
    loud = np.flatnonzero(np.abs(a) > THRESH)
    if loud.size == 0:
        return a[:0]
    return a[max(0, loud[0] - KEEP): loud[-1] + KEEP]

def envelope(audio):
    step = SR // ENV_HZ
    n = len(audio) // step
    if n == 0:
        return np.zeros(1)
    rms = np.sqrt(np.mean(audio[:n * step].reshape(n, step) ** 2, axis=1))
    peak = rms.max() or 1.0
    return (rms / peak) ** 0.6              # lift quiet syllables so the mouth moves

class _Stop(Exception):
    pass

def generator():
    """Sentence by sentence, phrase by phrase: the first and last sentence a
    little slower, emphasised phrases slower still, and a pause after each
    sentence that suits its punctuation."""
    while True:
        job = GENQ.get()
        try:
            if not hushed(job):
                count = len(job.marked)
                with GEN, torch.inference_mode():
                    for i, sentence in enumerate(job.marked):
                        speed = job.speed * sentence_speed(i, count)
                        pause = pause_after(job.marked[i - 1]) if i else 0.0
                        for j, (text, emph) in enumerate(segments(sentence)):
                            for _, _, audio in pipeline(job.voice[0])(
                                    text, voice=voice_for(job.voice), speed=speed * (0.95 if emph else 1.0),
                                    split_pattern=r"\n+"):
                                if hushed(job) or job.done.is_set():
                                    raise _Stop
                                job.chunks.put((i, trim(audio), pause if j == 0 else 0.03))
                                pause = 0.03
                gc.collect()
        except _Stop:
            pass
        except Exception as e:
            print(f"generate error: {e}", flush=True)
        finally:
            job.chunks.put(None)

# ---------------------------------------------------------------- player (main thread)
def publish(job, index, level, paused):
    try:
        NOW.write_text(json.dumps({
            "index": index, "total": len(job.sentences),
            "current": job.sentences[index] if index < len(job.sentences) else "",
            "sentences": job.sentences, "at": time.time(), "title": job.title,
            "level": round(float(level), 3), "pid": os.getpid()}))
    except OSError:
        pass

def play(job, tmp):
    pending, generated = [], False
    sound, offsets, indices, env = None, [], [], None
    tails = []                        # earlier sounds still finishing their last silence
    paused, last_pub = False, 0.0
    while True:
        platforms.pump(0.01)
        if hushed(job):
            for x in [sound, *tails]:
                if x:
                    x.stop()
            return
        tails = [x for x in tails if not x.finished()]
        while True:                                   # collect what has been generated
            try:
                item = job.chunks.get_nowait()
            except queue.Empty:
                break
            if item is None:
                generated = True
            else:
                pending.append(item)

        want_pause = PAUSE.exists()
        if sound and want_pause != paused:
            sound.pause() if want_pause else sound.resume()
            paused = want_pause

        near_end = (sound is not None and pending and not paused and sound.duration() > 0
                    and sound.duration() - sound.position() < PREROLL)
        if (sound is None or sound.finished() or near_end) and not want_pause:
            if pending:                               # everything ready plays as one sound
                parts, offsets, indices, pos = [], [], [], 0
                for n, (i, a, pause) in enumerate(pending):
                    if n or sound is not None:            # the first pause only between batches
                        gap = np.zeros(int(pause * SR), dtype="float32")
                        parts.append(gap); pos += len(gap)
                    offsets.append(pos / SR); indices.append(i)
                    parts.append(a); pos += len(a)
                audio = np.concatenate(parts)
                job.audio.append(audio)
                path = os.path.join(tmp, f"{job.created:.6f}-{indices[0]:04d}.wav")
                sf.write(path, audio, SR)
                if sound is not None and not sound.finished():
                    tails.append(sound)               # keep it alive: releasing it stops it
                sound, env, pending = platforms.Sound(path), envelope(audio), []
                sound.play()
                publish(job, indices[0], 0.0, False); last_pub = time.time()
            elif generated and not tails:
                return
            else:
                sound = None                          # playback caught up with generation

        if sound and time.time() - last_pub > 0.08:
            p = sound.position()
            k = max(0, bisect.bisect_right(offsets, p) - 1)
            level = 0.0 if paused else env[min(len(env) - 1, int(p * ENV_HZ))]
            publish(job, indices[k], level, paused)
            last_pub = time.time()

# ---------------------------------------------------------------- listener
def handle(conn):
    with conn:
        f = conn.makefile("rw")
        try:
            req = json.loads(f.readline())
            if req.get("ping"):
                f.write(json.dumps({"stamp": STAMP, "queued": JOBS.qsize()}) + "\n"); f.flush()
                return
            if req.get("drain"):                      # stop now, drop the queue
                STOP_AT[0] = time.time()
                platforms.stop_all()                  # an in-process client's player, if any
                f.write(json.dumps({"drained": True}) + "\n"); f.flush()
                return
            job = Job(req)
            with ENQUEUE:
                GENQ.put(job); JOBS.put(job)
            ACTIVE[0] = time.time()
            if req.get("bg"):
                f.write(json.dumps({"queued": JOBS.qsize()}) + "\n"); f.flush()
                return
            job.done.wait()                           # plain request: answer once spoken
            f.write(json.dumps({"done": True}) + "\n"); f.flush()
        except Exception as e:
            try:
                f.write(json.dumps({"error": str(e)}) + "\n"); f.flush()
            except Exception:
                pass

def listen(srv):
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        threading.Thread(target=handle, args=(conn,), daemon=True).start()

# ---------------------------------------------------------------- start
if SOCK.exists():
    SOCK.unlink()
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
srv.bind(str(SOCK))
os.chmod(SOCK, 0o600)
srv.listen(8)

# The client restarts us if the code changed underneath, so edits never run stale.
STAMP = max(p.stat().st_mtime for p in (HERE/"speakd.py", HERE/"speak.py") if p.exists())
threading.Thread(target=generator, daemon=True).start()
threading.Thread(target=listen, args=(srv,), daemon=True).start()
print(f"ready pid={os.getpid()}", flush=True)

tmp = tempfile.mkdtemp(prefix="speak.")
try:
    while True:
        try:
            job = JOBS.get_nowait()
        except queue.Empty:
            platforms.pump(0.05)
            if time.time() - ACTIVE[0] > IDLE_EXIT:
                break
            continue
        ACTIVE[0] = time.time()
        try:
            if not hushed(job):
                play(job, tmp)
            if job.save and job.audio:
                sf.write(job.save, np.concatenate(job.audio), SR)
        except Exception as e:
            print(f"play error: {e}", flush=True)
        finally:
            job.done.set()
            for name in os.listdir(tmp):
                try:
                    os.remove(os.path.join(tmp, name))
                except OSError:
                    pass
            if JOBS.empty():
                NOW.unlink(missing_ok=True)
            ACTIVE[0] = time.time()
        if JOBS.empty() and rss_mb() > RSS_CEIL:     # bounded lifetime; client restarts us
            print(f"rss {rss_mb():.0f}MB over ceiling, exiting", flush=True)
            break
finally:
    srv.close()
    shutil.rmtree(tmp, ignore_errors=True)
    SOCK.unlink(missing_ok=True)
