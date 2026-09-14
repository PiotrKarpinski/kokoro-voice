#!/usr/bin/env python3
"""Fast checks for bin/normalize.py - no model, no sessions, any python3.

    python3 evals/test_normalize.py
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent/"bin"))
from normalize import for_ear

# (input, must contain, must NOT contain)
CASES = [
    ("Edit scripts/player_movement.py now.", "the player movement script", ".py"),
    ("See README.md for more.",               "the readme file",            ".md"),
    ("Config lives in settings.json",         "the settings file",          ".json"),
    ("Saved to ~/.kokoro/spoken/",            "the spoken folder",          "~"),
    ("It is /opt/homebrew/bin/speak",         "speak",                      "/"),
    ("scripts/body/body_gait.gd changed",     "the body gait script",       "/"),
    ("It uses 300 MB",                        "300 megabytes",              "MB"),
    ("~300 MB free",                          "about 300 megabytes",        "~"),
    ("a 12.8m run-up",                        "12.8 metres",                "12.8m"),
    ("exactly 1 m",                           "1 metre",                    "metres"),
    ("took 250ms",                            "250 milliseconds",           "ms"),
    ("an 82M model",                          "82 million",                 "82M"),
    ("50% faster",                            "50 percent",                 "%"),
    ("on 2026-09-11",                         "September eleventh, 2026",   "-09-"),
    ("at 17:30",                              "17 30",                      ":"),
    ("at 09:05",                              "9 oh 5",                     ":"),
    ("at 12:00",                              "12 hundred",                 ":"),
    ("docs at https://github.com/x/y",        "a link",                     "https"),
    ("Node.js is fine",                       "Node is fine",               "script"),
    ("npm test && npm run build",             "and then",                   "&&"),
    ("input -> output",                       "input to output",            "->"),
    ("run `kokoro --status`",                 "kokoro --status",            "`"),
    ("```\ncode\n```",                        "code block omitted",         "```"),
    ("this is *really* important",           "⟪really⟫",                   "*"),
    ("**ship it** today",                     "⟪ship it⟫",                  "**"),
    ("* a bullet, not emphasis",              "a bullet, not emphasis",     "⟪"),
    # things that must survive untouched
    ("version 2.0.0 shipped",                 "2.0.0",                      "the 2"),
    ("pick one and/or both",                  "and/or",                     "folder"),
    ("e.g. this one",                         "e.g.",                       "file"),
    ("3 steps to go",                         "3 steps",                    "seconds"),
    ("the API returned 404",                  "API returned 404",           "file"),
]

from normalize import segments, pause_after, sentence_speed, plain, parse_voice
def _raises(fn, *args):
    try:
        fn(*args); return False
    except ValueError:
        return True

DELIVERY = [
    (segments("It is ⟪really⟫ fast."), [("It is", False), ("really", True), ("fast.", False)]),
    (pause_after("Shall we ship it?") > pause_after("Shipped."), True),
    (pause_after("Done!") < pause_after("Done."), True),
    ([sentence_speed(i, 4) for i in range(4)], [0.97, 1.0, 1.0, 0.97]),
    ([sentence_speed(i, 2) for i in range(2)], [1.0, 1.0]),
    (plain("It is ⟪really⟫ fast."), "It is really fast."),
    (parse_voice("af_heart"), [("af_heart", 1.0)]),
    ([(n, round(w, 3)) for n, w in parse_voice("af_heart:7,bf_emma:3")], [("af_heart", 0.7), ("bf_emma", 0.3)]),
    ((lambda: (parse_voice("not a voice"), "accepted"))() if False else "raises" if _raises(parse_voice, "not a voice") else "accepted", "raises"),
]

fails = 0
for got, want in DELIVERY:
    if got != want:
        fails += 1
        print(f"FAIL  delivery: got {got!r}, want {want!r}")
for raw, want, avoid in CASES:
    out = for_ear(raw)
    ok = want in out and avoid not in out
    fails += not ok
    if not ok:
        print(f"FAIL  {raw!r}\n      -> {out!r}\n      want {want!r}, avoid {avoid!r}")
print(f"{len(CASES)+len(DELIVERY)-fails}/{len(CASES)+len(DELIVERY)} normaliser and delivery checks passed")
sys.exit(1 if fails else 0)
