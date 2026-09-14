"""The assistant's face, in text: a confident woman with cable hair.

Built in layers so she can move. A base - skin, hair, clothes - is shaded once
from a height field lit softly from the front. Brows, eyes and mouth are drawn
over it every frame with whatever gaze, brow lift and mouth opening the moment
needs, and tilt() and breathe() move the head on top of that.

No Tk here, so it previews in a terminal:  python3 bin/face.py
"""
import math

ROWS, COLS = 36, 76
CELL = 0.5                       # a character cell is about half as wide as tall
RAMP = " .:-=+*#%@"
JAW_STEPS = 6

Y0, A = -0.10, 0.56              # face centre and half-height (hairline to chin)
W0 = 0.52                        # face half-width at the cheekbones
DY = 2.0 / ROWS
COLW = 2.0 / COLS * (COLS / ROWS) * CELL

def _g(x, y, cx, cy, rx, ry):
    return math.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))

def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))

def col_x(c):
    return (-1 + (c + 0.5) * 2.0 / COLS) * (COLS / ROWS) * CELL

def x_col(x):
    return int(round((x / ((COLS / ROWS) * CELL) + 1) * COLS / 2 - 0.5))

def row_y(r):
    return -1 + (r + 0.5) * DY

def row_of(y):
    return int(round((y + 1) / DY - 0.5))

def face_half_width(y):
    """Structured, not an oval: temples, cheekbones, a jaw angle, a squared chin."""
    t = (y - Y0) / A
    if t <= -1 or t >= 1:
        return 0.0
    if t < -0.55:
        return W0 * 0.90 * math.sqrt(max(0.0, 1 - ((t + 0.55) / 0.45) ** 2)) ** 0.6
    if t < 0.10:
        return W0 * (0.90 + 0.10 * _clamp((t + 0.55) / 0.65))
    if t < 0.55:
        return W0 * (1.00 - 0.12 * (t - 0.10) / 0.45)
    k = (t - 0.55) / 0.45
    return W0 * (0.88 - 0.52 * k ** 1.3)

def face_height(x, y):
    w = face_half_width(y)
    if w <= 0 or abs(x) >= w:
        return None
    t, u = (y - Y0) / A, x / W0
    z = math.sqrt(max(0.0, 1 - (x / w) ** 2)) * 0.8
    for su in (-0.40, 0.40):
        z -= 0.08 * _g(u, t, su, -0.18, 0.24, 0.08)            # soft eye hollows
        z += 0.10 * _g(u, t, su * 1.40, 0.00, 0.20, 0.10)      # cheekbones
        z += 0.08 * _g(u, t, su * 1.15, 0.24, 0.16, 0.10)      # raised cheeks: she is smiling
    z += 0.16 * math.exp(-(u / 0.07) ** 2) * _clamp((t + 0.16) / 0.06) * _clamp((0.20 - t) / 0.03)
    z += 0.06 * _g(u, t, 0.0, 0.18, 0.10, 0.05)                # nose tip
    z += 0.05 * _g(u, t, 0.0, 0.86, 0.18, 0.07)                # chin
    return z

def body(x, y):
    """Neck, blazer and shirt collar. Returns (kind, brightness) or None."""
    if 0.46 < y < 0.70 and abs(x) < 0.17:
        shade = 0.30 + 0.28 * math.cos(x / 0.17 * math.pi / 2)
        return "s", shade * (0.6 if y < 0.53 else 1.0)
    if y >= 0.64:
        if abs(x) > min(1.05, 0.24 + (y - 0.64) * 2.6):
            return None
        v = 0.03 + 0.30 * (y - 0.64) / 0.36
        if abs(x) < v:
            return "shirt", 0.85
        if abs(x) < v + 0.05:
            return "lapel", 0.9
        return "cloth", 0.25 + 0.15 * (1 - abs(x) / 1.05)
    return None

def _cables():
    """Cable hair: strands spread along a rounded crown that fall almost
    straight down, curving only to go around the face. Computed once."""
    cells = {}
    n = 11
    for side in (-1, 1):
        for k in range(n):
            f = (k + 0.5) / n
            vary = ((k * 7 + (3 if side > 0 else 11)) % 10) / 10.0
            x0 = 0.64 * f
            y_top = -0.92 + 0.30 * f ** 2
            y_end = 0.30 + 0.45 * vary
            thick = k % 3 == 1
            prev = None
            for r in range(max(0, int((y_top + 1) / DY)), min(ROWS - 1, int((y_end + 1) / DY)) + 1):
                y = row_y(r)
                x = x0 + 0.08 * _clamp((y + 0.2) / 0.9)
                if x < face_half_width(y) + COLW:
                    x = face_half_width(y) + COLW * (1 + k % 2)
                x = min(x, 0.80)
                c = x_col(side * x)
                if not 0 <= c < COLS:
                    continue
                d = 0 if prev is None else c - prev
                if abs(d) >= 1:
                    ch, kind = ("\\" if d > 0 else "/"), "cable"
                elif (r + k) % 7 == 0 and not thick:
                    ch, kind = "o", "node"
                else:
                    ch, kind = ("┃" if thick else "│"), "cable"
                cells[(r, c)] = (ch, kind)
                if thick and abs(d) < 1 and 0 <= c + side < COLS:
                    cells[(r, c + side)] = ("│", "cable2")
                prev = c
    return cells

CABLES = _cables()

def in_cap(x, y):
    """The dark cap of hair under the crown, so the top of the head is not bare."""
    top = Y0 - A
    if y >= top:
        return False
    k = (top - y) / 0.32
    return k < 1 and abs(x) < 0.66 * math.sqrt(max(0.0, 1 - k * k))

NECK_ROW = row_of(0.50)          # rows above this move with the head

def base():
    """Skin, hair and clothes, with no features. ROWS lists of (char, kind)."""
    L = (-0.22, -0.34, 0.91)
    n = math.sqrt(sum(v * v for v in L)); L = tuple(v / n for v in L)
    rows = []
    for r in range(ROWS):
        y = row_y(r)
        row = []
        for c in range(COLS):
            x = col_x(c)
            if (r, c) in CABLES:
                row.append(CABLES[(r, c)]); continue
            if in_cap(x, y):
                row.append((":" if (r + c) % 2 else ".", "cap")); continue
            z = face_height(x, y)
            if z is None:
                bd = body(x, y)
                if bd:
                    kind, b = bd
                    ch = {"shirt": "#", "lapel": "/" if x < 0 else "\\"}.get(kind, RAMP[min(9, int(b * 10))])
                    row.append((ch, f"s{min(4, int(b * 5))}" if kind == "s" else kind)); continue
                row.append((" ", "bg")); continue
            zx = (face_height(x + COLW, y) or 0) - (face_height(x - COLW, y) or 0)
            zy = (face_height(x, y + DY) or 0) - (face_height(x, y - DY) or 0)
            nx, ny = -zx / (2 * COLW), -zy / (2 * DY)
            nn = math.sqrt(nx * nx + ny * ny + 1)
            lit = _clamp((nx * L[0] + ny * L[1] + L[2]) / nn)
            b = _clamp((0.38 + 0.62 * lit) * (0.62 + 0.38 * _clamp(z)))
            row.append((RAMP[min(8, int(b * 10))], f"s{min(4, int(b * 5))}"))   # '@' is kept for pupils
        rows.append(row)
    return rows

_BASE = None
def base_rows():
    global _BASE
    if _BASE is None:
        _BASE = base()
    return _BASE

def _put(rows, r, c, ch, kind):
    if 0 <= r < ROWS and 0 <= c < COLS:
        rows[r][c] = (ch, kind)

# ---------------------------------------------------------------- features
def draw_brows(rows, left=0, right=0, inner=0):
    """Lifts are in rows. left/right raise each brow; inner raises the inner
    ends (surprise, worry) or, when negative, lowers them (focus)."""
    for side, lift in ((-1, left), (1, right)):
        for c in range(COLS):
            au = side * col_x(c) / W0
            if not 0.16 < au < 0.72:
                continue
            tb = -0.46 - 0.04 * math.exp(-((au - 0.46) / 0.22) ** 2)
            r = row_of(Y0 + tb * A) - lift - (inner if au < 0.34 else 0)
            _put(rows, r, c, "~", "brow")

EYE_KIND = {"_": "lash", ".": "lash", "=": "lash", "(": "lash", ")": "lash", "'": "lash",
            "-": "lash", "o": "iris", "*": "shine", "@": "pupil"}

def _eye_rows(open_=True, gx=0, gy=0):
    """Three rows per eye. gx looks left (-1) or right (1); gy up (-1) or down (1)."""
    if not open_:
        return ("           ", " '-.___.-' ", "           ")     # a happy closed arc
    def place(line, seq, at):
        chars = list(line)
        for i, ch in enumerate(seq):
            if 0 <= at + i < len(chars):
                chars[at + i] = ch
        return "".join(chars)
    if gy > 0:                                                  # looking down: lids lower
        return ("           ", " _.=====._ ", place(" '-------' ", "o*@o", 3 + gx))
    top = " _.=====._ "
    mid = place("(         )", "o*@@o", 3 + gx)
    low = place(" '-------' ", "ooo", 4 + gx)
    if gy < 0:                                                  # looking up: the iris rises
        top, low = place(top, "o@o", 4 + gx), " '-.___.-' "
    return (top, mid, low)

def draw_eyes(rows, open_=True, gx=0, gy=0):
    er = row_of(Y0 - 0.18 * A)
    lines = _eye_rows(open_, gx, gy)
    for su in (-0.40, 0.40):
        c0 = x_col(su * W0) - 5
        for i, line in enumerate(lines):
            for j, ch in enumerate(line):
                if ch == " ":
                    if i == 1 and line.startswith("("):
                        _put(rows, er - 1 + i, c0 + j, " ", "white")
                    continue
                _put(rows, er - 1 + i, c0 + j, ch, EYE_KIND.get(ch, "lash"))

def draw_mouth(rows, jaw):
    """A small, gentle smile with dimples - it opens only a little to talk."""
    mr = row_of(Y0 + 0.40 * A)
    cl, cr = COLS // 2 - 3, COLS // 2 + 2
    _put(rows, mr, cl - 2, "(", "dimple"); _put(rows, mr, cr + 2, ")", "dimple")
    _put(rows, mr, cl, "\\", "lip"); _put(rows, mr, cr, "/", "lip")
    inner = "=" if jaw >= 0.2 else "_"
    for c in range(cl + 1, cr):
        _put(rows, mr, c, inner, "teeth" if inner == "=" else "lip")
    if jaw >= 0.6:
        _put(rows, mr + 1, cl + 1, "\\", "lip"); _put(rows, mr + 1, cr - 1, "/", "lip")
        for c in range(cl + 2, cr - 1):
            _put(rows, mr + 1, c, "_", "lip")

# ---------------------------------------------------------------- head movement
def tilt(rows, amount):
    """Tilt the head: rows above the neck slide sideways in proportion to their
    height. amount is columns at the crown; positive leans left."""
    k_top = int(round(amount))
    if not k_top:
        return rows
    out, blank = [], (" ", "bg")
    for r, row in enumerate(rows):
        k = int(round(amount * (NECK_ROW - r) / NECK_ROW)) if r < NECK_ROW else 0
        if k > 0:
            row = row[k:] + [blank] * k
        elif k < 0:
            row = [blank] * (-k) + row[:k]
        out.append(row)
    return out

def breathe(rows, settled):
    """Breathing: on the out-breath the head settles one row; the shoulders stay."""
    if not settled:
        return rows
    return [[(" ", "bg")] * COLS] + rows[:NECK_ROW - 1] + rows[NECK_ROW:]

def compose(jaw=0.0, open_=True, gx=0, gy=0, brows=(0, 0, 0)):
    rows = [list(r) for r in base_rows()]
    draw_brows(rows, *brows)
    draw_eyes(rows, open_, gx, gy)
    draw_mouth(rows, jaw)
    return rows

def frame(jaw, eyes_open=True):
    return compose(jaw, eyes_open)

def frames():
    return {(j, e): frame(j / (JAW_STEPS - 1), e) for j in range(JAW_STEPS) for e in (True, False)}

if __name__ == "__main__":
    shots = [("neutral", dict()),
             ("looks left, brows up", dict(gx=-1, brows=(1, 1, 0))),
             ("looks up, one brow", dict(gy=-1, brows=(0, 1, 0))),
             ("looks down, focused", dict(gy=1, brows=(0, 0, -1)))]
    for label, kw in shots:
        rows = compose(**kw)
        print(f"--- {label} ---")
        for r in range(9, 17):
            print("".join(ch for ch, _ in rows[r][14:62]).rstrip())
    print("--- tilted 3 columns, breathing out ---")
    for row in breathe(tilt(compose(jaw=0.8), 3), True)[:30]:
        print("".join(ch for ch, _ in row).rstrip())
