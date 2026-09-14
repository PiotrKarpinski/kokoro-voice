"""A SHODAN-style face in text: an original, procedurally shaded mask.

The face is a height field - skull, angular jaw, a brow ridge that dips toward
the centre, deep sockets, cheekbones over hollow cheeks, a nose ridge, lips -
lit from the upper left and shaded into a character ramp. One side breaks into
circuitry and cables. The mouth cavity opens with the voice's loudness.

No Tk here, so it can be previewed in a terminal:  python3 bin/face.py
"""
import math

ROWS, COLS = 24, 60
CELL = 0.5                      # a character cell is about half as wide as it is tall
RAMP = " .:-=+*#%@"
CIRCUIT = "═║╬┼╪─│╫"
JAW_STEPS = 6

def _g(x, y, cx, cy, rx, ry):
    return math.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))

def _sig(v):
    return 1.0 / (1.0 + math.exp(-v))

def half_width(y):
    if y < -0.62:                                   # no skull dome: cables grow from the brow
        return 0.0
    if y < 0.06:                                    # temples to cheekbones
        return 0.62 + 0.04 * math.exp(-((y + 0.02) / 0.10) ** 2)
    t = (y - 0.06) / 0.94                           # hard taper to a narrow chin
    return max(0.0, 0.62 - 0.46 * t ** 1.15)

def mouth(jaw):
    h = 0.035 + 0.19 * jaw                          # opening height
    return 0.54, h                                  # top of the opening, height

def height(x, y, jaw):
    w = half_width(y)
    if w <= 0 or abs(x) >= w:
        return None
    u = x / w
    z = math.sqrt(max(0.0, 1 - u * u)) * 0.85
    yb = -0.40 + 0.14 * abs(x)                      # the glare: brow dips to the centre
    z += 0.22 * math.exp(-((y - yb) / 0.045) ** 2) * (1 if abs(x) < 0.55 else 0)
    for sx in (-0.28, 0.28):
        z -= 0.34 * _g(x, y, sx, -0.21, 0.12, 0.065)          # deep sockets
        z += 0.15 * _g(x, y, sx * 1.45, 0.02, 0.10, 0.07)     # cheekbones
        z -= 0.18 * _g(x, y, sx * 1.45, 0.40, 0.11, 0.17)     # hollow cheeks
    z += 0.26 * math.exp(-(x / 0.05) ** 2) * _sig((y + 0.12) / 0.025) * _sig((0.30 - y) / 0.02)
    z += 0.10 * _g(x, y, 0.0, 0.29, 0.07, 0.04)               # nose tip
    for sx in (-0.065, 0.065):
        z -= 0.12 * _g(x, y, sx, 0.345, 0.03, 0.022)          # nostrils
    top, h = mouth(jaw)
    z += 0.14 * _g(x, y, 0.0, top - 0.025, 0.21, 0.03)        # upper lip
    z += 0.15 * _g(x, y, 0.0, top + h + 0.035, 0.19, 0.035)   # lower lip, drops with the jaw
    z += 0.11 * _g(x, y, 0.0, 0.90, 0.11, 0.06)               # chin
    return z

def frame(jaw, eyes_open=True):
    """One frame: ROWS lists of (char, kind). kind is bg, s0-s4, eye, void,
    circuit or cable."""
    L = (-0.28, -0.42, 0.86)                        # mostly frontal, a little from the upper left
    n = math.sqrt(sum(v * v for v in L)); L = tuple(v / n for v in L)
    dx = 2.0 / COLS * (COLS / ROWS) * CELL
    dy = 2.0 / ROWS
    top, h = mouth(jaw)
    out = []
    for r in range(ROWS):
        y = -1 + (r + 0.5) * dy
        seam = 0.24 + 0.05 * math.sin(r * 1.7)      # jagged edge where the face turns to machine
        row = []
        for c in range(COLS):
            x = (-1 + (c + 0.5) * 2.0 / COLS) * (COLS / ROWS) * CELL
            z = height(x, y, jaw)
            if z is None and y < -0.60 and abs(x) < 0.58 and c % 3 == 0 and (r + c) % 5:
                row.append(("┃" if c % 6 == 0 else "│", "cable")); continue
            if z is None:
                cable = (y > 0.30 and any(abs(x - cx) < dx * 0.6 for cx in (0.50, 0.58, -0.54))
                         and abs(x) < half_width(0.06) + 0.10)
                row.append(("│", "cable") if cable else (" ", "bg"))
                continue
            my = top + h / 2
            if abs(y - my) < h / 2 and abs(x) < 0.20 * math.sqrt(max(0.0, 1 - ((y - my) / (h / 2 + 1e-6)) ** 2)):
                row.append((" ", "void")); continue
            if any(_g(x, y, sx, -0.21, 0.065, 0.04) > 0.45 for sx in (-0.28, 0.28)):
                row.append(("@", "eye") if eyes_open else ("-", "s1")); continue
            zx = (height(x + dx, y, jaw) or 0) - (height(x - dx, y, jaw) or 0)
            zy = (height(x, y + dy, jaw) or 0) - (height(x, y - dy, jaw) or 0)
            nx, ny, nz = -zx / (2 * dx), -zy / (2 * dy), 1.0
            nn = math.sqrt(nx * nx + ny * ny + nz * nz)
            lit = max(0.0, (nx * L[0] + ny * L[1] + nz * L[2]) / nn)
            b = (0.16 + 0.84 * lit) * (0.45 + 0.55 * max(0.0, min(1.0, z)))
            b = max(0.08, min(1.0, b ** 0.9))       # never fully black inside the silhouette
            if x > seam and -0.70 < y < 0.84:       # the machine half: panel lines over dim skin
                on_h = r % 4 == 1
                on_v = c % 7 == 3
                if on_h or on_v:
                    ch = "╬" if (on_h and on_v) else ("═" if on_h else "║")
                    row.append((ch, "circuit")); continue
                b *= 0.55
            row.append((RAMP[min(len(RAMP) - 1, int(b * len(RAMP)))], f"s{min(4, int(b * 5))}"))
        out.append(row)
    return out

def frames():
    """Every mouth step, eyes open and closed - computed once at startup."""
    return {(j, e): frame(j / (JAW_STEPS - 1), e) for j in range(JAW_STEPS) for e in (True, False)}

if __name__ == "__main__":
    for label, jaw, eyes in (("mouth closed", 0.0, True), ("mouth open", 1.0, True)):
        print(f"--- {label} ---")
        for row in frame(jaw, eyes):
            print("".join(ch for ch, _ in row).rstrip())
