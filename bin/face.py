"""The assistant's face, in text: a composed woman in her fifties, an executive.

Procedurally shaded, not drawn: the face is a height field lit softly from the
front and shaded into a character ramp. A sleek bob with a side-swept fringe,
groomed low-set brows, almond eyes, defined cheekbones, a straight nose, firm
lips, faint laugh lines, and a blazer with a shirt collar. The mouth opens with
the voice's loudness; the eyes blink.

No Tk here, so it previews in a terminal:  python3 bin/face.py
"""
import math

ROWS, COLS = 36, 76
CELL = 0.5                       # a character cell is about half as wide as tall
RAMP = " .:-=+*#%@"
JAW_STEPS = 6

# layout, in grid units: y runs -1 (top) to 1 (bottom); x is squeezed by CELL
Y0, A = -0.08, 0.60              # face centre and half-height (hairline to chin)
W0 = 0.42                        # face half-width at the cheekbones

def _g(x, y, cx, cy, rx, ry):
    return math.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))

def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))

def face_half_width(y):
    t = (y - Y0) / A
    if t <= -1 or t >= 1:
        return 0.0
    if t < 0:
        return W0 * math.sqrt(1 - t * t) ** 0.8
    return W0 * (1 - t ** 1.8) ** 0.62        # full cheeks, a defined jaw, a rounded chin

def mouth(jaw):
    t = 0.40                                   # mouth line, in face units
    return t, 0.012 + 0.075 * jaw              # centre line, opening half-height

def face_height(x, y, jaw):
    w = face_half_width(y)
    if w <= 0 or abs(x) >= w:
        return None
    t, u = (y - Y0) / A, x / W0
    z = math.sqrt(max(0.0, 1 - (x / w) ** 2)) * 0.8
    for su in (-0.42, 0.42):
        z -= 0.10 * _g(u, t, su, -0.18, 0.24, 0.08)     # shallow eye hollows
        z += 0.08 * _g(u, t, su * 1.35, 0.02, 0.18, 0.10)  # cheekbones
    z += 0.16 * math.exp(-(u / 0.07) ** 2) * _clamp((t + 0.16) / 0.06) * _clamp((0.20 - t) / 0.03)
    z += 0.06 * _g(u, t, 0.0, 0.18, 0.10, 0.05)          # nose tip
    mt, mh = mouth(jaw)
    z += 0.05 * _g(u, t, 0.0, mt - mh - 0.03, 0.26, 0.03)  # upper lip
    z += 0.06 * _g(u, t, 0.0, mt + mh + 0.035, 0.22, 0.035)  # lower lip
    z += 0.05 * _g(u, t, 0.0, 0.86, 0.14, 0.07)          # chin
    return z

def hair_half_width(y):
    top = -0.93
    if y < top:
        return 0.0
    if y < -0.66:                                           # a rounded crown
        k = (y - top) / (-0.66 - top)
        return 0.53 * math.sin(k * math.pi / 2) ** 0.7
    w = 0.53 + 0.05 * math.exp(-((y + 0.40) / 0.30) ** 2)   # a little volume at the temples
    if y > 0.12:
        w -= 0.07 * ((y - 0.12) / 0.20) ** 2                # the ends curve under
    return max(0.0, w)

def in_hair(x, y):
    """A sleek bob, longer toward the front, with a fringe swept from one side."""
    if abs(x) >= hair_half_width(y):
        return False
    if y > 0.30 + 0.08 * _clamp(1 - abs(x) / 0.55):        # A-line hem near the jaw
        return False
    fringe = -0.50 - 0.20 * _clamp((x + 0.40) / 0.80)
    return face_half_width(y) <= abs(x) or y < fringe

def hair_shade(x, y):
    sheen = (_g(x, y, -0.15, -0.78, 0.20, 0.06)             # light across the crown
             + 0.5 * _g(x, y, 0.40, -0.35, 0.05, 0.25)       # and down each side
             + 0.4 * _g(x, y, -0.42, -0.30, 0.05, 0.25))
    strands = 0.10 * math.sin(x * 55 + y * 6)                # combed lines
    return _clamp(0.20 + 0.55 * sheen + strands - 0.12 * _clamp(abs(x) / 0.55))

def body(x, y):
    """Neck, blazer and shirt collar. Returns (kind, brightness) or None."""
    if 0.46 < y < 0.70 and abs(x) < 0.13:
        shade = 0.30 + 0.28 * math.cos(x / 0.13 * math.pi / 2)
        return "s", shade * (0.6 if y < 0.53 else 1.0)       # shadow under the chin
    if y >= 0.64:
        if abs(x) > min(1.05, 0.24 + (y - 0.64) * 2.6):
            return None
        v = 0.03 + 0.30 * (y - 0.64) / 0.36                 # the V of the lapels widens downward
        if abs(x) < v:
            return "shirt", 0.85
        if abs(x) < v + 0.05:
            return "lapel", 0.9
        return "cloth", 0.25 + 0.15 * (1 - abs(x) / 1.05)
    return None

def frame(jaw, eyes_open=True):
    """ROWS lists of (char, kind). Kinds: bg, s0-s4 skin, h0-h3 hair, iris,
    white, lid, brow, lip, void, teeth, cloth, lapel, shirt."""
    L = (-0.22, -0.34, 0.91)
    n = math.sqrt(sum(v * v for v in L)); L = tuple(v / n for v in L)
    dx = 2.0 / COLS * (COLS / ROWS) * CELL
    dy = 2.0 / ROWS
    mt, mh = mouth(jaw)
    out = []
    for r in range(ROWS):
        y = -1 + (r + 0.5) * dy
        row = []
        for c in range(COLS):
            x = (-1 + (c + 0.5) * 2.0 / COLS) * (COLS / ROWS) * CELL
            t, u = (y - Y0) / A, x / W0
            z = face_height(x, y, jaw)
            if in_hair(x, y):
                b = hair_shade(x, y)
                row.append((RAMP[1 + int(b * 6)], f"h{min(3, int(b * 4))}")); continue
            if z is None:
                bd = body(x, y)
                if bd:
                    kind, b = bd
                    ch = {"shirt": "#", "lapel": "/" if x < 0 else "\\"}.get(kind, RAMP[min(9, int(b * 10))])
                    row.append((ch, f"s{min(4, int(b * 5))}" if kind == "s" else kind)); continue
                row.append((" ", "bg")); continue
            # eyes: almond shapes with iris, whites and a lid line
            eye = None
            for su in (-0.42, 0.42):
                du, dt = (u - su) / 0.20, (t + 0.18) / 0.050
                if du * du + dt * dt < 1.0:
                    if not eyes_open:
                        eye = ("-", "lid") if abs(dt) < 0.45 else None
                    elif dt < -0.55:
                        eye = ("_", "lid")
                    elif abs(du) < 0.33:
                        eye = ("@", "iris") if abs(du) < 0.14 and dt < 0.2 else ("O", "iris")
                    else:
                        eye = ("=", "white")
                    break
            if eye:
                row.append(eye); continue
            # brows: groomed, arched, set low at the inner end
            for su in (-1, 1):
                au = su * u
                if 0.18 < au < 0.74:
                    tb = -0.31 - 0.06 * math.exp(-((au - 0.50) / 0.16) ** 2)
                    if abs(t - tb) < 0.022:
                        eye = ("~", "brow")
            if eye:
                row.append(eye); continue
            # mouth: firm lips; the opening grows with the jaw
            if abs(u) < 0.26 * math.sqrt(max(0.0, 1 - (u / 0.26) ** 4)):
                if abs(t - mt) < mh and abs(u) < 0.20:
                    row_h = dy / A                      # one text row, in face units
                    teeth = mh > 0.03 and abs((t - row_h) - mt) >= mh   # top row of the opening
                    row.append(("=", "teeth") if teeth else (" ", "void")); continue
                if -0.035 < t - mt + mh < 0 or 0 < t - mt - mh < 0.045:
                    row.append(("=", "lip")); continue
            zx = (face_height(x + dx, y, jaw) or 0) - (face_height(x - dx, y, jaw) or 0)
            zy = (face_height(x, y + dy, jaw) or 0) - (face_height(x, y - dy, jaw) or 0)
            nx, ny = -zx / (2 * dx), -zy / (2 * dy)
            nn = math.sqrt(nx * nx + ny * ny + 1)
            lit = _clamp((nx * L[0] + ny * L[1] + L[2]) / nn)
            b = _clamp((0.28 + 0.72 * lit) * (0.55 + 0.45 * _clamp(z)))
            # faint laugh lines, nose to mouth corners
            for su in (-1, 1):
                lu, lt = 0.10 + 0.16 * _clamp((t - 0.20) / 0.22), 0.20 + 0.22 * _clamp((su * u - 0.10) / 0.16)
                if 0.20 < t < 0.44 and abs(su * u - lu) < 0.025:
                    b *= 0.80
            row.append((RAMP[min(9, int(b * 10))], f"s{min(4, int(b * 5))}"))
        out.append(row)
    return out

def frames():
    """Every mouth step, eyes open and shut - computed once at startup."""
    return {(j, e): frame(j / (JAW_STEPS - 1), e) for j in range(JAW_STEPS) for e in (True, False)}

if __name__ == "__main__":
    for label, jaw, eyes in (("speaking, mouth open", 1.0, True), ("closed, blink", 0.0, False)):
        print(f"--- {label} ---")
        for row in frame(jaw, eyes):
            print("".join(ch for ch, _ in row).rstrip())
