"""Screen text in, speakable text out.

Every rule here exists because Kokoro's phonemiser gets the original wrong
silently: `player.gd` comes out "player dot gee dee", `300 MB` as "em bee",
`~300` drops the number. The voice skill tells Claude to write for the ear;
this is the safety net for when it doesn't, so correctness does not depend on a
model remembering a rule.

Pure `re`, no dependencies - evals/test_normalize.py runs it with any python3.
"""
import re

CODE_EXT = ("py gd js mjs cjs ts tsx jsx sh bash zsh rb go rs swift kt java c cc "
            "cpp h hpp cs php lua").split()
DATA_EXT = ("json md markdown yaml yml toml txt csv tscn tres cfg ini lock log xml "
            "html css svg png jpg jpeg gif env plist").split()
EXT = "|".join(sorted(CODE_EXT + DATA_EXT, key=len, reverse=True))

UNITS = {
    "KB": ("kilobyte", "kilobytes"), "MB": ("megabyte", "megabytes"),
    "GB": ("gigabyte", "gigabytes"), "TB": ("terabyte", "terabytes"),
    "kHz": ("kilohertz", "kilohertz"), "Hz": ("hertz", "hertz"),
    "ms": ("millisecond", "milliseconds"), "sec": ("second", "seconds"),
    "min": ("minute", "minutes"), "hrs": ("hour", "hours"), "hr": ("hour", "hours"),
    "fps": ("frame per second", "frames per second"), "px": ("pixel", "pixels"),
    "km": ("kilometre", "kilometres"), "cm": ("centimetre", "centimetres"),
    "mm": ("millimetre", "millimetres"), "m": ("metre", "metres"),
    "s": ("second", "seconds"), "h": ("hour", "hours"),
}
UNIT_RE = "|".join(sorted(map(re.escape, UNITS), key=len, reverse=True))
SCALE = {"K": "thousand", "M": "million", "B": "billion"}

MONTHS = ("January February March April May June July August September "
          "October November December").split()
ORDINALS = ("first second third fourth fifth sixth seventh eighth ninth tenth "
            "eleventh twelfth thirteenth fourteenth fifteenth sixteenth "
            "seventeenth eighteenth nineteenth twentieth twenty-first "
            "twenty-second twenty-third twenty-fourth twenty-fifth twenty-sixth "
            "twenty-seventh twenty-eighth twenty-ninth thirtieth thirty-first").split()


def _words(name):
    """player_movement / playerMovement / player-movement -> player movement"""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return " ".join(w.lower() for w in re.split(r"[_\-.\s]+", name) if w)


def _file(m):
    path = m.group(0)
    name = path.rstrip("/").split("/")[-1]
    stem, _, ext = name.rpartition(".")
    ext = ext.lower()
    if ext == "js" and stem[:1].isupper():          # Node.js, Vue.js: a name, not a file
        return stem
    kind = "script" if ext in CODE_EXT else "file"
    return f"the {_words(stem) or ext} {kind}"


def _dir(m):
    path = m.group(0)
    name = path.rstrip("/").split("/")[-1].lstrip("~.")
    if not name:
        return "the home folder" if path.startswith("~") else "that folder"
    return f"the {_words(name)} folder" if path.endswith("/") else _words(name)


def _unit(m):
    num, unit = m.group(1), m.group(2)
    one, many = UNITS[unit]
    return f"{num} {one if num == '1' else many}"


def _date(m):
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return m.group(0)
    return f"{MONTHS[mo-1]} {ORDINALS[d-1]}, {y}"


def _time(m):
    h, mm = int(m.group(1)), m.group(2)
    if mm == "00":
        return f"{h} hundred"
    if mm.startswith("0"):
        return f"{h} oh {int(mm)}"
    return f"{h} {mm}"


def for_ear(raw):
    t = raw
    # structure that should never be read out
    t = re.sub(r"```.*?```", " code block omitted. ", t, flags=re.S)
    t = re.sub(r"https?://\S+", "a link", t)
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)          # [label](url) -> label
    t = re.sub(r"`([^`]*)`", r"\1", t)                        # unwrap, then clean inside
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.M)            # bullets
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.M)           # headings
    t = re.sub(r"\*\*(.+?)\*\*", r"⟪\1⟫", t)                 # **key phrase** is spoken a touch slower
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"⟪\1⟫", t)

    # symbols the phonemiser mangles
    t = re.sub(r"~\s*(?=[\d.])", "about ", t)                 # ~300 silently drops the 300
    t = re.sub(r"\s*&&\s*", " and then ", t)                  # && -> "and-and"
    t = re.sub(r"\s*(?:->|=>)\s*", " to ", t)
    t = re.sub(r"(\d)\s?%", r"\1 percent", t)

    # dates and times before numbers get touched
    t = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", _date, t)
    t = re.sub(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?\b", _time, t)

    # files and folders, before underscores are stripped
    t = re.sub(rf"(?<![\w@])(?:~|\.{{1,2}})?/?(?:[\w.-]+/)*[\w-][\w.-]*\.(?:{EXT})\b",
               _file, t, flags=re.I)
    t = re.sub(r"(?<![\w@/])(?:~|\.{1,2})?/(?:[\w.-]+/)*[\w.-]*/?", _dir, t)
    t = re.sub(r"(?<![\w@/])[\w.-]+(?:/[\w.-]+){2,}/?", _dir, t)

    # units and scales
    t = re.sub(rf"(?<![\w.])(\d+(?:\.\d+)?)\s?({UNIT_RE})\b", _unit, t)
    t = re.sub(r"(?<![\w.])(\d+(?:\.\d+)?)([KMB])\b", lambda m: f"{m.group(1)} {SCALE[m.group(2)]}", t)

    # leftovers and whitespace
    t = re.sub(r"[*_~>|]", "", t)
    t = re.sub(r"\n{2,}", ". ", t)
    t = re.sub(r"\.(\s*\.)+", ".", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------- delivery
EMPHASIS = re.compile(r"⟪(.+?)⟫")
PAUSE_AFTER = {"?": 0.24, "!": 0.13, ".": 0.16, ":": 0.12, ";": 0.12, ",": 0.08}

def plain(sentence):
    """The sentence as shown and archived: emphasis markers removed."""
    return sentence.replace("⟪", "").replace("⟫", "")

def segments(sentence):
    """[(text, emphasised)] - an emphasised phrase is generated on its own, slower."""
    out, pos = [], 0
    for m in EMPHASIS.finditer(sentence):
        if m.start() > pos:
            out.append((sentence[pos:m.start()], False))
        out.append((m.group(1), True))
        pos = m.end()
    if pos < len(sentence):
        out.append((sentence[pos:], False))
    return [(txt.strip(), emph) for txt, emph in out if txt.strip()]

def pause_after(sentence):
    """Seconds of silence after a sentence: a question gets a beat to land."""
    return PAUSE_AFTER.get(plain(sentence).rstrip()[-1:], 0.14)

def sentence_speed(index, count):
    """Set it up and land it: the first and last sentence of a longer passage slower."""
    return 0.92 if count > 2 and index in (0, count - 1) else 1.0
