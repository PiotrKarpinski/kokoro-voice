"""The assistant's face, in text: a confident woman with cable hair.

Procedurally shaded, not drawn: the face is a height field lit softly from the
front and shaded into a character ramp. Structured features - cheekbones, a
defined jaw, a softly squared chin - so it does not read as an egg. Calm eyes,
arched brows, a drawn smile that opens to show teeth, and hair made of cables
that fall from a centre part, flow around the face and drape onto the
shoulders of a blazer.

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
            x0 = 0.64 * f                                     # along the crown, not from a point
            y_top = -0.92 + 0.30 * f ** 2                     # a rounded dome
            y_end = 0.30 + 0.45 * vary
            thick = k % 3 == 1
            prev = None
            for r in range(max(0, int((y_top + 1) / DY)), min(ROWS - 1, int((y_end + 1) / DY)) + 1):
                y = row_y(r)
                x = x0 + 0.08 * _clamp((y + 0.2) / 0.9)       # a gentle fall outward
                if x < face_half_width(y) + COLW:             # around the face, never over it
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

def in_cap(x, y):
    """The dark cap of hair under the crown, so the top of the head is not bare."""
    top = Y0 - A
    if y >= top:
        return False
    k = (top - y) / 0.32
    return k < 1 and abs(x) < 0.66 * math.sqrt(max(0.0, 1 - k * k))

CABLES = _cables()

def _put(rows, r, c, ch, kind):
    if 0 <= r < ROWS and 0 <= c < COLS:
        rows[r][c] = (ch, kind)

def _draw_mouth(rows, jaw):
    """A small, gentle smile with dimples - it opens only a little to talk."""
    mr = int(round((Y0 + 0.40 * A + 1) / DY - 0.5))
    cl, cr = COLS // 2 - 3, COLS // 2 + 2                      # six columns wide
    _put(rows, mr, cl - 2, "(", "dimple"); _put(rows, mr, cr + 2, ")", "dimple")
    _put(rows, mr, cl, "\\", "lip"); _put(rows, mr, cr, "/", "lip")
    inner = "=" if jaw >= 0.2 else "_"
    for c in range(cl + 1, cr):
        _put(rows, mr, c, inner, "teeth" if inner == "=" else "lip")
    if jaw >= 0.6:
        _put(rows, mr + 1, cl + 1, "\\", "lip"); _put(rows, mr + 1, cr - 1, "/", "lip")
        for c in range(cl + 2, cr - 1):
            _put(rows, mr + 1, c, "_", "lip")

EYE_OPEN = (" _.=====._ ",      # thick upper lashes
            "(  o*@@o  )",      # big iris, highlight, pupil; spaces are the whites
            " '-.ooo.-' ")      # lower lid and the bottom of the iris
EYE_SHUT = ("           ",
            " '-.___.-' ",      # a happy closed arc
            "           ")
EYE_KIND = {"_": "lash", ".": "lash", "=": "lash", "(": "lash", ")": "lash", "'": "lash",
            "-": "lash", "o": "iris", "*": "shine", "@": "pupil"}

def _draw_eyes(rows, eyes_open):
    er = int(round((Y0 - 0.18 * A + 1) / DY - 0.5))            # the middle row of each eye
    for su in (-0.40, 0.40):
        c0 = x_col(su * W0) - 5
        for i, line in enumerate(EYE_OPEN if eyes_open else EYE_SHUT):
            for j, ch in enumerate(line):
                if ch == " ":
                    if eyes_open and i == 1:
                        _put(rows, er - 1 + i, c0 + j, " ", "white")
                    continue
                _put(rows, er - 1 + i, c0 + j, ch, EYE_KIND.get(ch, "lash"))

def frame(jaw, eyes_open=True):
    """ROWS lists of (char, kind). Kinds: bg, s0-s4 skin, cap, cable, cable2,
    node, lash, iris, shine, pupil, white, brow, dimple, lip, teeth, cloth,
    lapel, shirt."""
    L = (-0.22, -0.34, 0.91)
    n = math.sqrt(sum(v * v for v in L)); L = tuple(v / n for v in L)
    rows = []
    for r in range(ROWS):
        y = row_y(r)
        row = []
        for c in range(COLS):
            x = col_x(c)
            t, u = (y - Y0) / A, x / W0
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
            eye = None
            for su in (-1, 1):
                au = su * u
                if 0.16 < au < 0.72:
                    tb = -0.46 - 0.04 * math.exp(-((au - 0.46) / 0.22) ** 2)
                    if abs(t - tb) < 0.05:
                        eye = ("~", "brow")
            if eye:
                row.append(eye); continue
            dx, dy = COLW, DY
            zx = (face_height(x + dx, y) or 0) - (face_height(x - dx, y) or 0)
            zy = (face_height(x, y + dy) or 0) - (face_height(x, y - dy) or 0)
            nx, ny = -zx / (2 * dx), -zy / (2 * dy)
            nn = math.sqrt(nx * nx + ny * ny + 1)
            lit = _clamp((nx * L[0] + ny * L[1] + L[2]) / nn)
            b = _clamp((0.38 + 0.62 * lit) * (0.62 + 0.38 * _clamp(z)))
            row.append((RAMP[min(8, int(b * 10))], f"s{min(4, int(b * 5))}"))   # '@' is kept for pupils
        rows.append(row)
    _draw_eyes(rows, eyes_open)
    _draw_mouth(rows, jaw)
    return rows

def frames():
    """Every mouth step, eyes open and shut - computed once at startup."""
    return {(j, e): frame(j / (JAW_STEPS - 1), e) for j in range(JAW_STEPS) for e in (True, False)}

if __name__ == "__main__":
    for label, jaw, eyes in (("smiling, mouth closed", 0.0, True), ("speaking, mouth open", 1.0, True)):
        print(f"--- {label} ---")
        for row in frame(jaw, eyes):
            print("".join(ch for ch, _ in row).rstrip())
