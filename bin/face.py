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
    """Cable hair: strands from a centre part that flow around the face and
    drape past the jaw. Fixed for every frame, so computed once."""
    cells = {}
    n = 10
    for side in (-1, 1):
        for k in range(n):
            f = (k + 0.5) / n
            vary = ((k * 7 + (3 if side > 0 else 11)) % 10) / 10.0
            y_top = -0.95 + 0.14 * f ** 1.5
            y_end = 0.28 + 0.50 * vary
            thick = k % 3 == 0
            prev = None
            for r in range(max(0, int((y_top + 1) / DY)), min(ROWS - 1, int((y_end + 1) / DY)) + 1):
                y = row_y(r)
                s = _clamp((y - y_top) / 0.40)
                x = 0.62 * f * (0.45 + 0.55 * math.sin(s * math.pi / 2)) + 0.12 * _clamp((y + 0.10) / 0.85)
                x = min(x, 0.82)                                          # drape, don't fan out
                if x < face_half_width(y) + COLW:                         # around the face, never over it
                    x = face_half_width(y) + COLW * (1 + k % 2)
                c = x_col(side * x)
                if not 0 <= c < COLS:
                    continue
                d = 0 if prev is None else c - prev
                if abs(d) >= 1:
                    ch, kind = ("\\" if d > 0 else "/"), "cable"
                elif (r + k) % 6 == 0 and not thick:
                    ch, kind = "o", "node"
                else:
                    ch, kind = ("┃" if thick else "│"), "cable"
                cells[(r, c)] = (ch, kind)
                if thick and abs(d) < 1 and 0 <= c + side < COLS:
                    cells[(r, c + side)] = ("│", "cable2")
                prev = c
    return cells

CABLES = _cables()

def _draw_mouth(rows, jaw):
    """A drawn smile - a curve, not a shaded bar - that opens to show teeth."""
    mr = int(round((Y0 + 0.40 * A + 1) / DY - 0.5))
    cl, cr = COLS // 2 - 6, COLS // 2 + 5           # corners
    def put(r, c, ch, kind):
        if 0 <= r < ROWS and 0 <= c < COLS:
            rows[r][c] = (ch, kind)
    put(mr - 1, cl - 1, ".", "lip"); put(mr - 1, cr + 1, ".", "lip")     # lifted corners
    if jaw < 0.2:
        put(mr, cl, "\\", "lip"); put(mr, cr, "/", "lip")
        for c in range(cl + 1, cr):
            put(mr, c, "_", "lip")
        return
    put(mr, cl, "\\", "lip"); put(mr, cr, "/", "lip")
    for c in range(cl + 1, cr):
        put(mr, c, "=", "teeth")
    if jaw < 0.6:
        put(mr + 1, cl + 1, "\\", "lip"); put(mr + 1, cr - 1, "/", "lip")
        for c in range(cl + 2, cr - 1):
            put(mr + 1, c, "_", "lip")
        return
    put(mr + 1, cl + 1, "\\", "lip"); put(mr + 1, cr - 1, "/", "lip")
    for c in range(cl + 2, cr - 1):
        put(mr + 1, c, " ", "void")
    put(mr + 2, cl + 2, "\\", "lip"); put(mr + 2, cr - 2, "/", "lip")
    for c in range(cl + 3, cr - 2):
        put(mr + 2, c, "_", "lip")

def frame(jaw, eyes_open=True):
    """ROWS lists of (char, kind). Kinds: bg, s0-s4 skin, cable, cable2, node,
    iris, pupil, white, lid, brow, lip, void, teeth, cloth, lapel, shirt."""
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
            z = face_height(x, y)
            if z is None:
                bd = body(x, y)
                if bd:
                    kind, b = bd
                    ch = {"shirt": "#", "lapel": "/" if x < 0 else "\\"}.get(kind, RAMP[min(9, int(b * 10))])
                    row.append((ch, f"s{min(4, int(b * 5))}" if kind == "s" else kind)); continue
                row.append((" ", "bg")); continue
            eye = None
            for su in (-0.40, 0.40):
                du, dt = (u - su) / 0.21, (t + 0.18) / 0.065
                if du * du + dt * dt < 1.0:
                    if not eyes_open:
                        eye = ("^", "lid") if abs(dt) < 0.45 else None      # closed and content
                    elif dt < -0.50:
                        eye = ("_", "lid")
                    elif abs(du) < 0.11 and abs(dt) < 0.45:
                        eye = ("@", "pupil")
                    elif abs(du) < 0.30:
                        eye = ("o", "iris")
                    else:
                        eye = ("-", "white")
                    break
            if eye:
                row.append(eye); continue
            for su in (-1, 1):
                au = su * u
                if 0.16 < au < 0.72:
                    tb = -0.37 - 0.04 * math.exp(-((au - 0.46) / 0.22) ** 2)
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
