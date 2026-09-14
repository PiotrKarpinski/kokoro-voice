#!/usr/bin/env python3
"""Voice evals. Real headless Claude Code sessions, graded without an LLM judge.

Each case runs in an isolated KOKORO_HOME with KOKORO_DRY_RUN=1, so `kokoro`
records what it would have said instead of making sound. The graders then read
that record and the chat reply.

    python3 evals/run.py                  every case, once
    python3 evals/run.py --runs 3         three runs each - consistency is the point
    python3 evals/run.py --case narrate   cases whose name contains "narrate"

Needs this plugin's `voice` skill and hook active (dev mode or installed), an
installed runtime in ~/.kokoro, and the `claude` CLI.
"""
import argparse, concurrent.futures as cf, datetime, json, os, pathlib, re
import shutil, subprocess, sys, tempfile, time

HERE    = pathlib.Path(__file__).resolve().parent
RUNTIME = pathlib.Path(os.environ.get("KOKORO_RUNTIME", pathlib.Path.home()/".kokoro"))

FILENAME = re.compile(r"\b[\w-]+\.(py|gd|md|json|tscn|sh|js|ts|txt|yaml|toml)\b|(?:\w+/)+\w+", re.I)
PLAYING_TEXT = ["The spring is a timer, not a health bar.",
                "It drains only when you are standing still.",
                "Wallrunning and sliding are where you refuel.",
                "Enemies kill you by stopping you."]

# ---------------------------------------------------------------- graders
def g_answered(r):
    ok = not r.get("errored") and bool(r["chat"].strip())
    return ok, "session answered" if ok else "session errored or returned nothing"
def g_spoke(r):          return bool(r["speaks"]), f"{len(r['speaks'])} speech call(s)"
def g_silent(r):         return not r["speaks"], f"{len(r['speaks'])} speech call(s)"
def g_all_bg(r):
    bad = [s for s in r["speaks"] if not s["bg"]]
    return not bad, f"{len(bad)} without --bg"
def g_titled(r):
    bad = [s for s in r["speaks"] if s["title"] in ("", "project")]
    return not bad, f"{len(bad)} without a real --title"
def g_no_filenames(r):
    hits = [m.group(0) for s in r["speaks"] for m in FILENAME.finditer(s["text"])]
    return not hits, ("clean" if not hits else "spoke: " + ", ".join(sorted(set(hits))[:4]))
def summaries(r):        return [s for s in r["speaks"] if s["words"] >= 40]
def beats(r):            return [s for s in r["speaks"] if s["words"] < 40]
def g_summary_length(r):
    ss = summaries(r) or r["speaks"]
    bad = [s["words"] for s in ss if not 60 <= s["words"] <= 220]
    return bool(ss) and not bad, "words: " + ", ".join(str(s["words"]) for s in ss)
def g_beats_1_to_10(r):  n = len(beats(r)); return 1 <= n <= 10, f"{n} beat(s)"
def g_one_summary(r):    n = len(summaries(r)); return n == 1, f"{n} summary(ies)"
def g_chat_is_blockquote(r):
    lines = [l for l in r["chat"].strip().splitlines() if l.strip()]
    stray = [l for l in lines if not l.lstrip().startswith(">")]
    return bool(lines) and not stray, f"{len(stray)} non-quote line(s)"
def g_chat_not_duplicated(r):
    ss = summaries(r)
    if not ss: return True, "no summary to duplicate"
    probe = " ".join(ss[0]["text"].split()[:12])
    dup = probe and probe in " ".join(r["chat"].replace(">", " ").split())
    return not dup, "summary pasted into chat" if dup else "not duplicated"
def g_chat_mentions_off(r):
    ok = re.search(r"\boff\b", r["chat"], re.I) is not None
    return ok, "mentions off" if ok else "does not say voice is off"
def g_hushed(r):         ok = any(e["kind"] == "hush" for e in r["log"]); return ok, "hush called" if ok else "no hush"
def g_paused_first(r):
    kinds = [e["kind"] for e in r["log"]]
    ok = bool(kinds) and kinds[0] == "pause"
    return ok, "first action: " + (kinds[0] if kinds else "none")
def g_mode_now_narrate(r):
    return r["final_mode"] == "narrate", f"mode is {r['final_mode']}"

GRADERS = {k[2:]: v for k, v in globals().items() if k.startswith("g_") and k != "g_answered"}

# ---------------------------------------------------------------- one run
def run_case(case, timeout):
    home = pathlib.Path(tempfile.mkdtemp(prefix="kv-eval-"))
    try:
        (home/".venv").symlink_to(RUNTIME/".venv")
        (home/"config.json").write_text(json.dumps({"mode": case["mode"]}))
        if case.get("playing"):
            (home/".now-playing").write_text(json.dumps({
                "index": 1, "total": len(PLAYING_TEXT), "current": PLAYING_TEXT[1],
                "sentences": PLAYING_TEXT, "at": time.time(), "title": "spring economy"}))
        project = home/"project"
        shutil.copytree(HERE/"fixture", project)

        env = dict(os.environ, KOKORO_HOME=str(home), KOKORO_DRY_RUN="1")
        t0 = time.time()
        p = subprocess.run(["claude", "-p", case["prompt"], "--output-format", "json"],
                           cwd=project, env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=timeout)
        try:
            out = json.loads(p.stdout)
            chat, errored = out.get("result", "") or "", bool(out.get("is_error"))
        except ValueError:
            chat, errored = p.stdout, True
        log = []
        if (home/"dryrun.jsonl").exists():
            log = [json.loads(l) for l in (home/"dryrun.jsonl").read_text().splitlines() if l.strip()]
        try:
            final_mode = json.loads((home/"config.json").read_text()).get("mode", "on-request")
        except ValueError:
            final_mode = "?"
        r = {"chat": chat, "log": log, "speaks": [e for e in log if e["kind"] == "speak"],
             "final_mode": final_mode, "seconds": round(time.time()-t0), "errored": errored}
        # Every case must actually have run. Without this, a crashed session
        # passes any "silent" check for the wrong reason.
        r["grades"] = {"answered": g_answered(r)}
        r["grades"].update({g: GRADERS[g](r) for g in case["expect"]})
        return r
    except subprocess.TimeoutExpired:
        return {"chat": "", "log": [], "speaks": [], "final_mode": "?", "seconds": timeout,
                "grades": {g: (False, "timed out") for g in ["answered", *case["expect"]]}}
    finally:
        shutil.rmtree(home, ignore_errors=True)

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--case", default="")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=420)
    a = ap.parse_args()

    for g in {g for c in json.loads((HERE/"cases.json").read_text()) for g in c["expect"]}:
        assert g in GRADERS, f"unknown grader {g}"
    cases = [c for c in json.loads((HERE/"cases.json").read_text()) if a.case in c["name"]]
    jobs = [(c, i) for c in cases for i in range(a.runs)]
    print(f"{len(cases)} case(s) x {a.runs} run(s) = {len(jobs)} session(s)\n", flush=True)

    results = {}
    with cf.ThreadPoolExecutor(a.parallel) as ex:
        futs = {ex.submit(run_case, c, a.timeout): (c, i) for c, i in jobs}
        for f in cf.as_completed(futs):
            c, i = futs[f]
            r = f.result()
            results.setdefault(c["name"], []).append(r)
            ok = all(v[0] for v in r["grades"].values())
            print(f"  {'PASS' if ok else 'FAIL'}  {c['name']}  (run {i+1}, {r['seconds']}s)", flush=True)

    print()
    total = passed = 0
    for c in cases:
        runs = results.get(c["name"], [])
        print(f"{c['name']}")
        for g in ["answered", *c["expect"]]:
            n = sum(1 for r in runs if r["grades"][g][0])
            total += len(runs); passed += n
            detail = runs[-1]["grades"][g][1] if runs else ""
            print(f"   {'✓' if n == len(runs) else '✗'} {g:<22} {n}/{len(runs)}   {detail}")
    print(f"\n{passed}/{total} checks passed ({100*passed//max(total,1)}%)")

    out = HERE/"results"; out.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    (out/f"{stamp}.json").write_text(json.dumps(
        {name: [{k: v for k, v in r.items()} for r in rs] for name, rs in results.items()},
        indent=2, default=str))
    print(f"details: evals/results/{stamp}.json")
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
