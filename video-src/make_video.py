"""Narrated motion-graphics explainer for the electrostatics course.

usage:  python make_video.py render OUT.mp4
        python make_video.py preview OUTDIR    (PNG stills, no audio)
"""
import json, math, os, subprocess, sys, wave

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, SS, FPS = 1280, 720, 2, 30
LEAD, TAIL = 0.5, 1.1

BG = (18, 21, 28); INK = (232, 234, 240); MUTED = (140, 147, 162)
ACC = (122, 162, 255); PLUS = (255, 107, 91); MINUS = (91, 155, 255)
GOOD = (76, 199, 135); WARN = (242, 193, 78); PANEL = (30, 34, 45)

FD = "C:/Windows/Fonts/"
_fc = {}


def font(kind, size):
    key = (kind, size)
    if key not in _fc:
        if kind == "math":
            _fc[key] = ImageFont.truetype(FD + "cambria.ttc", size * SS, index=1)
        elif kind == "bold":
            _fc[key] = ImageFont.truetype(FD + "segoeuib.ttf", size * SS)
        else:
            _fc[key] = ImageFont.truetype(FD + "segoeui.ttf", size * SS)
    return _fc[key]


def mix(col, a, base=BG):
    a = max(0.0, min(1.0, a))
    return tuple(int(base[i] + (col[i] - base[i]) * a) for i in range(3))


def ease(u, a, b):
    x = (u - a) / (b - a)
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def partial(pts, frac):
    """First `frac` (by length) of a polyline."""
    if frac <= 0 or len(pts) < 2:
        return []
    segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(segs) * min(frac, 1.0)
    out = [pts[0]]
    for i, s in enumerate(segs):
        if total >= s:
            out.append(pts[i + 1]); total -= s
        else:
            t = total / s if s else 0
            out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t,
                        pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t))
            break
    return out


class Cv:
    def __init__(self):
        self.im = Image.new("RGB", (W * SS, H * SS), BG)
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def P(x, y):
        return (x * SS, y * SS)

    def line(self, pts, col, w=3, a=1.0):
        if len(pts) < 2 or a <= 0:
            return
        self.d.line([self.P(*p) for p in pts], fill=mix(col, a), width=max(1, int(w * SS)), joint="curve")

    def dashed(self, pts, col, w=2, a=1.0, dash=10, gap=8):
        if a <= 0:
            return
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            L = math.dist(pts[i], pts[i + 1])
            if L == 0:
                continue
            s = 0.0
            while s < L:
                e = min(s + dash, L)
                self.line([(x0 + (x1 - x0) * s / L, y0 + (y1 - y0) * s / L),
                           (x0 + (x1 - x0) * e / L, y0 + (y1 - y0) * e / L)], col, w, a)
                s += dash + gap

    def arrow(self, x0, y0, x1, y1, col, w=3, a=1.0, head=12):
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 2 or a <= 0:
            return
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        head = min(head, L * 0.6)
        bx, by = x1 - ux * head, y1 - uy * head
        self.line([(x0, y0), (bx, by)], col, w, a)
        px, py = -uy, ux
        hw = head * 0.55
        self.d.polygon([self.P(x1, y1), self.P(bx + px * hw, by + py * hw), self.P(bx - px * hw, by - py * hw)],
                       fill=mix(col, a))

    def circle(self, x, y, r, fill=None, outline=None, w=2, a=1.0):
        if a <= 0:
            return
        self.d.ellipse([self.P(x - r, y - r), self.P(x + r, y + r)],
                       fill=mix(fill, a) if fill else None,
                       outline=mix(outline, a) if outline else None, width=int(w * SS))

    def ellipse(self, x0, y0, x1, y1, outline, w=2, a=1.0):
        self.d.ellipse([self.P(x0, y0), self.P(x1, y1)], outline=mix(outline, a), width=int(w * SS))

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, w=2, a=1.0, r=0):
        if a <= 0:
            return
        self.d.rounded_rectangle([self.P(x0, y0), self.P(x1, y1)], radius=r * SS,
                                 fill=mix(fill, a) if fill else None,
                                 outline=mix(outline, a) if outline else None, width=int(w * SS))

    def poly(self, pts, fill=None, outline=None, a=1.0):
        self.d.polygon([self.P(*p) for p in pts], fill=mix(fill, a) if fill else None,
                       outline=mix(outline, a) if outline else None)

    def text(self, x, y, s, size=24, col=INK, kind="sans", a=1.0, align="c"):
        if a <= 0 or not s:
            return
        f = font(kind, size)
        bb = self.d.textbbox((0, 0), s, font=f, anchor="ls")
        if align == "c":
            px = x * SS - (bb[0] + bb[2]) / 2
        elif align == "r":
            px = x * SS - bb[2]
        else:
            px = x * SS - bb[0]
        py = y * SS - (bb[1] + bb[3]) / 2
        self.d.text((px, py), s, font=f, fill=mix(col, a), anchor="ls")

    def width(self, s, size, kind="sans"):
        return self.d.textlength(s, font=font(kind, size)) / SS


def charge(c, x, y, r, sign, a=1.0):
    c.circle(x, y, r, fill=PLUS if sign > 0 else MINUS, a=a)
    c.text(x, y, "+" if sign > 0 else "−", int(r * 1.3), (255, 255, 255), "bold", a)


# ---------------------------------------------------------------- physics helpers
DIP = [(-1.0, 0.0, 1.0), (1.0, 0.0, -1.0)]


def efield(x, y, charges=DIP):
    ex = ey = 0.0
    for cx, cy, q in charges:
        dx, dy = x - cx, y - cy
        r3 = (dx * dx + dy * dy) ** 1.5 + 1e-9
        ex += q * dx / r3; ey += q * dy / r3
    return ex, ey


def field_line(x, y, ds=0.01, nmax=1200, bx=2.4, by=1.6):
    pts = [(x, y)]
    for _ in range(nmax):
        ex, ey = efield(x, y); n = math.hypot(ex, ey)
        mx, my = x + ex / n * ds / 2, y + ey / n * ds / 2
        ex, ey = efield(mx, my); n = math.hypot(ex, ey)
        x, y = x + ex / n * ds, y + ey / n * ds
        pts.append((x, y))
        if math.hypot(x - 1, y) < 0.07 or abs(x) > bx or abs(y) > by:
            break
    return pts


def dipole_lines(angles):
    return [field_line(-1 + 0.07 * math.cos(t), 0.07 * math.sin(t)) for t in angles]


ANGLES = [math.radians(a) for a in (20, 40, 60, 85, 115, 150, -20, -40, -60, -85, -115, -150)]
LINES = dipole_lines(ANGLES)

# trajectory of a + test charge released from rest on a curved field line
_FL = field_line(-1 + 0.07 * math.cos(math.radians(55)), 0.07 * math.sin(math.radians(55)))
P0 = _FL[len(_FL) // 6]
FL_FROM_P0 = _FL[len(_FL) // 6:]


def _trajectory():
    x, y = P0; vx = vy = 0.0; dt = 0.0004; pts = [(x, y)]
    for i in range(60000):
        ex, ey = efield(x, y)
        vx += ex * dt; vy += ey * dt
        x += vx * dt; y += vy * dt
        if i % 20 == 0:
            pts.append((x, y))
        if abs(x) > 2.1 or abs(y) > 1.45 or math.hypot(x - 1, y) < 0.12 or math.hypot(x + 1, y) < 0.12:
            break
    return pts


TRAJ = _trajectory()


def to_screen(pts, cx, cy, sc):
    return [(cx + p[0] * sc, cy - p[1] * sc) for p in pts]


# ---------------------------------------------------------------- scenes
def s_title(c, u, T):
    g = ease(u, 0.05, 0.6)
    for ln in LINES:
        pts = to_screen(ln, 640, 430, 150)
        k = next((i for i, q in enumerate(pts) if q[1] < 265 or q[1] > 600), len(pts))
        c.line(partial(pts[:k], g), ACC, 2, 0.45)
    charge(c, 640 - 150, 430, 18, +1); charge(c, 640 + 150, 430, 18, -1)
    c.text(640, 150, "Electrostatics", 64, INK, "bold", ease(u, 0, 0.15))
    c.text(640, 215, "the logic behind each topic", 28, MUTED, "sans", ease(u, 0.08, 0.25))


def s_field(c, u, T):
    cx, cy = 420, 330
    g = ease(u, 0.05, 0.35)
    if g > 0.02:
        for k in range(16):
            t = 2 * math.pi * k / 16
            c.arrow(cx + 36 * math.cos(t), cy + 36 * math.sin(t),
                    cx + (36 + 240 * g) * math.cos(t), cy + (36 + 240 * g) * math.sin(t), ACC, 2.5, 0.85, 10)
    charge(c, cx, cy, 26, +1)
    a2 = ease(u, 0.42, 0.5)
    charge(c, 790, cy, 13, +1, a2)
    a3 = ease(u, 0.5, 0.65)
    c.arrow(806, cy, 806 + 110 * a3, cy, WARN, 5, a3, 16)
    c.text(860, cy - 32, "F = qE", 26, WARN, "math", a3)
    c.text(1085, 240, "E = kQ / r²", 34, INK, "math", ease(u, 0.25, 0.35))
    c.text(1085, 330, "F = q E", 34, INK, "math", ease(u, 0.6, 0.7))
    c.text(1085, 400, "points away from +,", 18, MUTED, a=ease(u, 0.3, 0.4))
    c.text(1085, 425, "toward −", 18, MUTED, a=ease(u, 0.3, 0.4))


def dashed_circle(c, x, y, r, col, w=2, a=1.0, n=36):
    for k in range(n):
        if k % 2:
            continue
        t0, t1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        c.line([(x + r * math.cos(t0 + (t1 - t0) * s / 4), y + r * math.sin(t0 + (t1 - t0) * s / 4)) for s in range(5)], col, w, a)


def s_gauss(c, u, T):
    c.text(640, 130, "∮ E · dA  =  Q / ε₀", 36, INK, "math", ease(u, 0, 0.08))
    c.text(640, 172, "Q = charge inside the closed surface", 18, MUTED, a=ease(u, 0, 0.08))
    starts = [0.15, 0.42, 0.68]
    a = [ease(u, s, s + 0.1) for s in starts]
    # point charge
    x, y = 240, 320
    if a[0] > 0:
        for k in range(8):
            t = 2 * math.pi * k / 8 + 0.2
            c.arrow(x + 22 * math.cos(t), y + 22 * math.sin(t), x + 130 * math.cos(t), y + 130 * math.sin(t), ACC, 2.5, a[0], 10)
        dashed_circle(c, x, y, 85, INK, 2, a[0] * 0.8)
        charge(c, x, y, 14, +1, a[0])
    c.text(x, 475, "point charge → sphere", 19, MUTED, a=a[0])
    c.text(x, 510, "E ∝ 1 / r²", 28, INK, "math", a[0])
    # wire
    x = 640
    if a[1] > 0:
        c.ellipse(565, 209, 715, 241, INK, 2, a[1] * 0.7)
        c.ellipse(565, 399, 715, 431, INK, 2, a[1] * 0.7)
        c.line([(565, 225), (565, 415)], INK, 2, a[1] * 0.7)
        c.line([(715, 225), (715, 415)], INK, 2, a[1] * 0.7)
        c.line([(x, 190), (x, 450)], PLUS, 6, a[1])
        for yy in (270, 320, 370):
            c.arrow(x + 6, yy, x + 110, yy, ACC, 2.5, a[1], 10)
            c.arrow(x - 6, yy, x - 110, yy, ACC, 2.5, a[1], 10)
    c.text(x, 475, "wire → cylinder", 19, MUTED, a=a[1])
    c.text(x, 510, "E = λ / 2πε₀r", 28, INK, "math", a[1])
    # plane
    x = 1040
    if a[2] > 0:
        c.poly([(1015, 190), (1065, 215), (1065, 450), (1015, 425)], fill=PLUS, a=a[2] * 0.45)
        c.rect(998, 290, 1082, 350, outline=INK, w=2, a=a[2] * 0.7)
        for yy in (260, 320, 380):
            c.arrow(1070, yy, 1170, yy, ACC, 2.5, a[2], 10)
            c.arrow(1010, yy, 910, yy, ACC, 2.5, a[2], 10)
    c.text(x, 475, "plane → pillbox", 19, MUTED, a=a[2])
    c.text(x, 510, "E = σ / 2ε₀  (constant)", 28, INK, "math", a[2])


def s_plates(c, u, T):
    xp, xm = 520, 760
    c.rect(xp - 5, 170, xp + 5, 470, fill=PLUS)
    c.rect(xm - 5, 170, xm + 5, 470, fill=MINUS)
    c.text(xp, 150, "+σ", 26, PLUS, "math"); c.text(xm, 150, "−σ", 26, MINUS, "math")
    rows = (230, 320, 410)
    a1 = ease(u, 0.1, 0.25) * (1 - ease(u, 0.62, 0.7))
    a2 = ease(u, 0.35, 0.5) * (1 - ease(u, 0.62, 0.7))
    for y in rows:
        # + plate: away on both sides
        c.arrow(xp - 15, y - 12, xp - 105, y - 12, PLUS, 2.5, a1, 10)
        c.arrow(xp + 15, y - 12, xp + 105, y - 12, PLUS, 2.5, a1, 10)
        c.arrow(xm + 110, y - 12, xm + 200, y - 12, PLUS, 2.5, a1, 10)
        # − plate: toward it on both sides
        c.arrow(xp - 105, y + 12, xp - 15, y + 12, MINUS, 2.5, a2, 10)
        c.arrow(xm - 105, y + 12, xm - 15, y + 12, MINUS, 2.5, a2, 10)
        c.arrow(xm + 200, y + 12, xm + 110, y + 12, MINUS, 2.5, a2, 10)
    c.text(xp - 60, 490, "from +σ: σ/2ε₀ away", 18, PLUS, a=a1)
    c.text(xm + 60, 490, "from −σ: σ/2ε₀ toward", 18, MINUS, a=a2)
    a3 = ease(u, 0.66, 0.8)
    for y in rows:
        c.arrow(xp + 15, y, xm - 15, y, ACC, 5, a3, 16)
    c.text(640, 505, "E = σ / ε₀  · uniform · independent of d", 26, INK, "math", a3)
    c.text(420, 320, "0", 40, MUTED, "math", a3)
    c.text(860, 320, "0", 40, MUTED, "math", a3)


def s_boundary(c, u, T):
    y0 = 380
    c.line([(280, y0), (1000, y0)], PLUS, 5)
    for k in range(12):
        c.text(300 + k * 60, y0 + 22, "+", 18, PLUS, "bold", 0.8)
    c.text(990, y0 - 22, "σ", 26, PLUS, "math", align="r")
    t, n1, n2 = 150, 100, 220
    a1 = ease(u, 0.05, 0.2)
    c.arrow(640 - t, y0 + 10 + n1, 640, y0 + 10, INK, 4, a1, 14)
    c.arrow(640, y0 - 10, 640 + t, y0 - 10 - n2, INK, 4, a1, 14)
    c.text(520, y0 + 115, "E below", 18, MUTED, a=a1)
    c.text(860, y0 - 232, "E above", 18, MUTED, a=a1)
    a2 = ease(u, 0.3, 0.45)
    # tangential components (same)
    c.arrow(640 - t, y0 + 10 + n1, 640, y0 + 10 + n1, GOOD, 3, a2, 11)
    c.arrow(640, y0 - 10 - n2, 640 + t, y0 - 10 - n2, GOOD, 3, a2, 11)
    # normal components (different)
    a3 = ease(u, 0.45, 0.6)
    c.arrow(640, y0 + 10 + n1, 640, y0 + 10, WARN, 3, a3, 11)
    c.arrow(640 + t, y0 - 10, 640 + t, y0 - 10 - n2, WARN, 3, a3, 11)
    c.text(1120, 200, "tangential part: same on both sides", 20, GOOD, a=a2)
    c.text(1120, 240, "ΔE∥ = 0", 30, GOOD, "math", a2)
    c.text(1120, 310, "normal part: jumps", 20, WARN, a=a3)
    c.text(1120, 350, "ΔE⊥ = σ / ε₀", 30, WARN, "math", a3)
    c.text(170, 210, "tiny loop", 20, GOOD, a=ease(u, 0.55, 0.65))
    c.text(170, 236, "→ tangent part", 18, MUTED, a=ease(u, 0.55, 0.65))
    c.text(170, 290, "tiny pillbox", 20, WARN, a=ease(u, 0.6, 0.7))
    c.text(170, 316, "→ normal part", 18, MUTED, a=ease(u, 0.6, 0.7))


def bez(p0, p1, p2, n=40):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / n for i in range(n + 1))]


def s_conservative(c, u, T):
    A, B = (190, 470), (500, 215)
    for i, (ctrl, col) in enumerate((((150, 200), ACC), ((350, 360), GOOD), ((560, 470), WARN))):
        c.line(partial(bez(A, ctrl, B), ease(u, 0.06 + 0.12 * i, 0.18 + 0.12 * i)), col, 3)
    c.circle(*A, 8, fill=INK); c.circle(*B, 8, fill=INK)
    c.text(A[0] - 22, A[1] + 4, "A", 22, INK, "bold"); c.text(B[0] + 24, B[1], "B", 22, INK, "bold")
    c.text(345, 525, "same work W along every path", 20, MUTED, a=ease(u, 0.4, 0.48))
    c.text(345, 140, "∮ E·dl = 0  ⇒  ∇×E = 0", 30, INK, "math", ease(u, 0.35, 0.45))
    cx, cy = 930, 340
    a = ease(u, 0.48, 0.62)
    for r in (50, 95, 140, 185):
        c.circle(cx, cy, r, outline=MUTED, w=1.5, a=a * 0.8)
    charge(c, cx, cy, 16, +1, a)
    a2 = ease(u, 0.6, 0.72)
    for k in range(8):
        t = 2 * math.pi * k / 8 + 0.39
        c.arrow(cx + 60 * math.cos(t), cy + 60 * math.sin(t), cx + 178 * math.cos(t), cy + 178 * math.sin(t), ACC, 3, a2, 12)
    c.text(930, 120, "E = −∇V", 32, INK, "math", a2)
    c.text(1180, 230, "equipotentials", 18, MUTED, a=a, align="r")
    c.text(1180, 255, "E is perpendicular, downhill", 18, ACC, a=a2, align="r")


def s_continuity(c, u, T):
    c.line([(160, 360), (600, 360)], MUTED, 1.5); c.line([(690, 470), (1130, 470)], MUTED, 1.5)
    c.dashed([(380, 200), (380, 510)], PLUS, 2, 0.8); c.dashed([(910, 200), (910, 510)], PLUS, 2, 0.8)
    c.text(380, 530, "charged sheet", 17, PLUS); c.text(910, 530, "charged sheet", 17, PLUS)
    c.text(175, 200, "E(x)", 28, INK, "math", align="l"); c.text(705, 200, "V(x)", 28, INK, "math", align="l")
    g = ease(u, 0.08, 0.38)
    c.line(partial([(160, 430), (380, 430)], min(1, g * 2)), ACC, 4)
    c.line(partial([(380, 290), (600, 290)], max(0, g * 2 - 1)), ACC, 4)
    aj = ease(u, 0.3, 0.4)
    c.arrow(400, 425, 400, 297, WARN, 2.5, aj, 10)
    c.text(412, 360, "jumps", 20, WARN, a=aj, align="l")
    g2 = ease(u, 0.45, 0.72)
    c.line(partial([(690, 450), (910, 250), (1130, 450)], g2), GOOD, 4)
    ak = ease(u, 0.7, 0.78)
    c.circle(910, 250, 8, outline=WARN, w=3, a=ak)
    c.text(910, 222, "kink: continuous, not differentiable", 19, WARN, a=ak)


def plot(c, cx, cy, f, col, a, w=260, h=180):
    c.line([(cx - w / 2, cy), (cx + w / 2, cy)], MUTED, 1.2, a * 0.7)
    c.line([(cx, cy - h / 2 - 10), (cx, cy + h / 2 + 10)], MUTED, 1.2, a * 0.7)
    pts = [(cx + x * w / 2, cy - f(x) * h / 2) for x in (i / 40 - 1 for i in range(81))]
    return pts


def s_poisson(c, u, T):
    c.text(640, 135, "d²V/dx²  =  −ρ / ε₀", 36, INK, "math", ease(u, 0, 0.1))
    specs = [(240, lambda x: x, PLUS, "ρ ∝ x", "linear"),
             (640, lambda x: 2 * x * x - 1, ACC, "E ∝ x²", "quadratic"),
             (1040, lambda x: -x ** 3, GOOD, "V ∝ x³", "cubic")]
    for i, (cx, f, col, lab, word) in enumerate(specs):
        s = 0.12 + 0.22 * i
        a = ease(u, s, s + 0.06)
        if a > 0:
            pts = plot(c, cx, 340, f, col, a)
            c.line(partial(pts, ease(u, s, s + 0.16)), col, 4)
        c.text(cx, 470, lab, 30, col, "math", a)
        c.text(cx, 505, word, 19, MUTED, a=a)
        if i < 2:
            aa = ease(u, s + 0.14, s + 0.2)
            c.arrow(cx + 148, 340, cx + 252, 340, INK, 3, aa, 14)
            c.text(cx + 200, 315, "integrate", 18, MUTED, a=aa)


def s_dipole(c, u, T):
    for y in range(150, 540, 60):
        c.arrow(90, y, 850, y, MUTED, 1.5, 0.5, 10)
    c.text(845, 132, "uniform E", 18, MUTED, align="r")
    th0 = math.radians(55)
    if u < 0.45:
        th = th0
    else:
        s = (u - 0.45) / 0.45
        th = th0 * math.exp(-3.2 * s) * math.cos(2 * math.pi * 1.1 * s)
    cx, cy, L = 470, 340, 170
    px, py = cx + L / 2 * math.cos(th), cy - L / 2 * math.sin(th)
    mx, my = cx - L / 2 * math.cos(th), cy + L / 2 * math.sin(th)
    c.line([(mx, my), (px, py)], INK, 3)
    af = ease(u, 0.12, 0.22)
    c.arrow(px + 20, py, px + 115, py, PLUS, 4, af, 14)
    c.arrow(mx - 20, my, mx - 115, my, MINUS, 4, af, 14)
    c.text(px + 70, py - 22, "+qE", 22, PLUS, "math", af)
    c.text(mx - 70, my + 26, "−qE", 22, MINUS, "math", af)
    charge(c, px, py, 17, +1); charge(c, mx, my, 17, -1)
    at = ease(u, 0.3, 0.38) * (1 - ease(u, 0.55, 0.62))
    if at > 0:
        arc = [(cx + 120 * math.cos(-(th + 0.6 - 0.45 * k / 12)), cy + 120 * math.sin(-(th + 0.6 - 0.45 * k / 12))) for k in range(13)]
        c.line(arc[:-1], WARN, 3, at)
        c.arrow(*arc[-3], *arc[-1], WARN, 3, at, 14)
        c.text(arc[0][0] - 10, arc[0][1] - 18, "τ", 26, WARN, "math", at)
    c.rect(890, 160, 1220, 510, fill=PANEL, r=14)
    c.text(1055, 215, "ΣF = qE − qE = 0", 26, INK, "math", ease(u, 0.2, 0.28))
    c.text(1055, 290, "τ = p × E", 28, WARN, "math", ease(u, 0.35, 0.43))
    c.text(1055, 325, "turns p toward E", 17, MUTED, a=ease(u, 0.35, 0.43))
    c.text(1055, 390, "U = −p · E", 28, INK, "math", ease(u, 0.58, 0.66))
    c.text(1055, 425, "lowest when aligned", 17, MUTED, a=ease(u, 0.58, 0.66))
    c.text(1055, 475, "net force only if E is non-uniform", 16, ACC, a=ease(u, 0.8, 0.86))


def s_motion(c, u, T):
    cx, cy, sc = 400, 345, 135
    for ln in LINES:
        c.line(to_screen(ln, cx, cy, sc), MUTED, 1.5, 0.45)
    charge(c, cx - sc, cy, 15, +1); charge(c, cx + sc, cy, 15, -1)
    af = ease(u, 0.05, 0.14)
    c.dashed(to_screen(FL_FROM_P0, cx, cy, sc), ACC, 3, af, 9, 6)
    c.dashed([(70, 132), (110, 132)], ACC, 3, af, 9, 6)
    c.text(120, 132, "field line (direction of the force)", 18, ACC, a=af, align="l")
    g = ease(u, 0.15, 0.55)
    tr = to_screen(TRAJ, cx, cy, sc)
    n = max(1, int(len(tr) * g))
    c.line(tr[:n], WARN, 3.5)
    p = tr[n - 1]
    charge(c, p[0], p[1], 9, +1)
    al = ease(u, 0.15, 0.22)
    c.line([(70, 160), (110, 160)], WARN, 3.5, al)
    c.text(120, 160, "actual path of a charge released at rest", 18, WARN, a=al, align="l")
    a = ease(u, 0.6, 0.7)
    c.rect(850, 150, 1225, 520, fill=PANEL, r=14, a=a)
    bx, by = 1037, 330
    c.rect(bx - 32, by - 32, bx + 32, by + 32, fill=PLUS, r=8, a=a)
    c.text(bx, by, "+q, m", 17, (255, 255, 255), "bold", a)
    c.arrow(bx, by + 36, bx, by + 130, WARN, 4, ease(u, 0.66, 0.74), 14)
    c.arrow(bx, by - 36, bx, by - 130, ACC, 4, ease(u, 0.7, 0.78), 14)
    c.text(bx + 30, by + 110, "mg", 26, WARN, "math", ease(u, 0.66, 0.74), "l")
    c.text(bx + 30, by - 110, "qE", 26, ACC, "math", ease(u, 0.7, 0.78), "l")
    c.text(bx, 185, "equilibrium", 20, MUTED, a=a)
    c.text(bx, 490, "qE = mg  ⇒  q = mg / E", 24, INK, "math", ease(u, 0.76, 0.84))


def cap(c, x0, x1, ytop, ybot, a=1.0, arrows=True):
    c.rect(x0, ytop - 4, x1, ytop + 4, fill=PLUS, a=a)
    c.rect(x0, ybot - 4, x1, ybot + 4, fill=MINUS, a=a)
    if arrows:
        for k in range(1, 4):
            x = x0 + (x1 - x0) * k / 4
            c.arrow(x, ytop + 8, x, ybot - 8, ACC, 2, a * 0.8, 8)


def s_caps(c, u, T):
    c.text(640, 130, "C = ε₀ A / d", 32, INK, "math", ease(u, 0, 0.1))
    c.text(330, 200, "Parallel", 26, INK, "bold", ease(u, 0.05, 0.12))
    s = ease(u, 0.15, 0.35)
    cap(c, 170, 290, 300, 360, ease(u, 0.05, 0.12))
    off = 80 * (1 - s)
    cap(c, 290 + off, 410 + off, 300, 360, ease(u, 0.05, 0.12))
    c.text(330, 420, "area adds", 20, MUTED, a=ease(u, 0.32, 0.4))
    c.text(330, 460, "C = C₁ + C₂  (bigger)", 26, GOOD, "math", ease(u, 0.35, 0.43))
    c.text(950, 200, "Series", 26, INK, "bold", ease(u, 0.45, 0.52))
    a = ease(u, 0.45, 0.52)
    fade = 1 - ease(u, 0.58, 0.72)
    c.rect(890, 236, 1010, 244, fill=PLUS, a=a)
    c.rect(890, 376, 1010, 384, fill=MINUS, a=a)
    c.rect(890, 276, 1010, 284, fill=MINUS, a=a * fade)
    c.rect(890, 336, 1010, 344, fill=PLUS, a=a * fade)
    c.line([(950, 288), (950, 332)], INK, 2, a * fade)
    for k in range(1, 4):
        x = 890 + 120 * k / 4
        c.arrow(x, 248, x, 372, ACC, 2, a * 0.8, 8)
    c.text(950, 420, "gap adds", 20, MUTED, a=ease(u, 0.7, 0.76))
    c.text(950, 460, "1/C = 1/C₁ + 1/C₂", 26, WARN, "math", ease(u, 0.72, 0.8))
    c.text(950, 495, "smaller than the smallest", 17, MUTED, a=ease(u, 0.72, 0.8))


def node(c, x, y, w, h, s, a, size=34, kind="math", col=INK):
    c.rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, fill=PANEL, outline=ACC, w=2, r=12, a=a)
    c.text(x, y, s, size, col, kind, a)


def s_summary(c, u, T):
    a = [ease(u, s, s + 0.08) for s in (0.02, 0.12, 0.28, 0.45, 0.62, 0.75)]
    node(c, 200, 300, 140, 76, "ρ", a[0])
    node(c, 640, 300, 140, 76, "E", a[1])
    node(c, 1080, 300, 140, 76, "V", a[2])
    c.arrow(275, 300, 565, 300, INK, 3, a[1], 14)
    c.text(420, 278, "Gauss", 20, MUTED, a=a[1])
    c.arrow(715, 285, 1005, 285, INK, 3, a[2], 14)
    c.text(860, 258, "V = −∫ E·dl", 22, INK, "math", a[2])
    c.arrow(1005, 318, 715, 318, INK, 3, a[2], 14)
    c.text(860, 345, "E = −∇V", 22, INK, "math", a[2])
    arc = bez((200, 258), (640, 30), (1080, 258), 40)
    c.line(partial(arc, a[3]), GOOD, 3)
    if a[3] > 0.95:
        c.arrow(*arc[-3], *arc[-1], GOOD, 3, 1, 14)
    c.text(640, 170, "Poisson: integrate ρ twice", 20, GOOD, a=a[3])
    c.arrow(640, 340, 640, 440, WARN, 3, a[4], 14)
    c.text(660, 390, "acts back on charges", 18, WARN, a=a[4], align="l")
    node(c, 640, 480, 420, 66, "F = qE    ·    τ = p × E", a[4], 26)


SCENES = [
    ("", s_title, None,
     "Electrostatics in a few minutes. We'll skip the units and focus on the logic: how charges create fields, how fields become potentials, and how fields act back on charges."),
    ("Charges create fields", s_field, "Charges make fields  →  fields push charges",
     "Everything starts with charge. A charge fills the space around it with an electric field, pointing away from positive charges and toward negative ones. Any other charge placed in that field feels a force, q times E. So the field is the middleman: charges make fields, and fields push charges."),
    ("Gauss's law", s_gauss, "Symmetry + Gauss's law  →  E in one line",
     "Gauss's law says the total field flowing out of any closed surface counts the charge inside. When the charge is symmetric, we pick a surface where the field is constant, and the law hands us E directly. For a point charge the flux spreads over a sphere, so E falls as one over r squared. For an infinite wire it spreads over a cylinder, so E falls as one over r. For an infinite plane the area doesn't grow at all, so the field is constant: sigma over two epsilon zero."),
    ("Superposition: two charged plates", s_plates, "Fields add as vectors  →  uniform field inside, zero outside",
     "Fields add as vectors. Put a positive plane next to a negative one. Each makes a uniform field of sigma over two epsilon zero. Between the plates the two fields point the same way and add up to sigma over epsilon zero. Outside, they point opposite ways and cancel. The result is a uniform field inside that does not depend on the gap. This is the capacitor."),
    ("Crossing a charged surface", s_boundary, "Normal part jumps by σ/ε₀  ·  tangential part is continuous",
     "What happens when you cross a charged surface? Split the field into a part along the surface and a part normal to it. A tiny loop shows that the tangential part cannot change at all. A tiny pillbox shows that the normal part jumps by sigma over epsilon zero. Normal jumps, tangent stays continuous."),
    ("Conservative field and potential", s_conservative, "Same work on every path  →  E is the downhill slope of V",
     "The electrostatic field is conservative: the work to move a charge from A to B is the same along every path. So its curl is zero, the field is irrotational, and it can be written as minus the gradient of a scalar, the potential V. Think of V as a landscape: the field always points straight downhill, perpendicular to the lines of equal potential. Being conservative does not make the field zero. It makes the field a slope."),
    ("Why V is continuous", s_continuity, "V is the integral of E  →  one step smoother than E",
     "Because V is the integral of E, it is always smoother than E. Where E jumps, at a charged surface, V stays continuous, but it bends sharply, making a kink where it cannot be differentiated."),
    ("Poisson's equation", s_poisson, "Integrate ρ twice  →  each step raises the power by one",
     "Poisson's equation links the potential directly to the charge: the second derivative of V equals minus rho over epsilon zero. So to get V, you integrate the charge density twice, and each integration raises the power by one. A charge density that grows linearly gives a quadratic field and a cubic potential."),
    ("Dipole in a uniform field", s_dipole, "Uniform field: no net force, only a torque that aligns p",
     "A dipole is a plus and minus charge pair, with moment p pointing from minus to plus. In a uniform field the two forces are equal and opposite, so the net force is zero. But they act at different points, so they form a couple: a torque, p cross E, that turns the dipole to line up with the field. The energy is minus p dot E, lowest when aligned. Only a non-uniform field can pull the dipole as a whole."),
    ("Charges moving in a field", s_motion, "Field lines give the force direction, not the path",
     "Field lines show the direction of the force, not the path. On a curved field line, a moving charge would need a sideways push to follow the curve, and the field does not supply one, so inertia carries it off the line. A charge follows a field line only if the line is straight and the charge starts at rest or moving along it. And when a charge floats at rest, the electric force exactly balances its weight: q E equals m g."),
    ("Capacitors: parallel and series", s_caps, "C depends only on geometry  ·  parallel adds, series shrinks",
     "Capacitance depends only on geometry. Connecting capacitors in parallel is like enlarging the plate area, so the capacitances add. Connecting them in series is like widening the gap, so the result is smaller than the smallest one. Changing the voltage does not change C."),
    ("The whole chain", s_summary, None,
     "Here's the whole chain. Charge density gives the field through Gauss's law, and the potential through Poisson's equation. Field and potential are linked by an integral one way and a gradient the other. And the field acts back on charges: a force on single charges, and a torque on dipoles. Master these links, and every question in this part of the course follows."),
]


# ---------------------------------------------------------------- frame composition
def wrap(c, s, size, maxw):
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if c.width(t, size) > maxw and cur:
            lines.append(cur); cur = w_
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def sentences(text):
    out, cur = [], ""
    for ch in text:
        cur += ch
        if ch in ".!?" and len(cur.strip()) > 3:
            out.append(cur.strip()); cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def subtitle_at(text, t, speech):
    sents = sentences(text)
    total = sum(len(s) for s in sents)
    tt = (t - LEAD) / max(speech, 0.1) * total
    acc = 0
    for s in sents:
        acc += len(s)
        if tt < acc:
            return s
    return sents[-1] if t < LEAD + speech + 0.6 else ""


def frame(idx, t, T, speech):
    title, fn, take, text = SCENES[idx]
    u = t / T
    c = Cv()
    if title:
        c.text(60, 52, title, 30, INK, "bold", align="l")
        c.text(1220, 52, f"{idx} / {len(SCENES) - 1}", 18, MUTED, align="r")
        c.line([(60, 82), (60 + 60 * ease(u, 0, 0.15), 82)], ACC, 3)
    fn(c, u, T)
    if take:
        a = ease(u, 0.8, 0.88)
        if a > 0:
            w = c.width(take, 21, "bold") + 48
            c.rect(640 - w / 2, 553, 640 + w / 2, 597, fill=PANEL, outline=ACC, w=2, r=22, a=a)
            c.text(640, 575, take, 21, INK, "bold", a)
    sub = subtitle_at(text, t, speech)
    c.rect(0, 616, W, H, fill=(12, 14, 19))
    lines = wrap(c, sub, 22, 1120)[:3]
    y = 666 - (len(lines) - 1) * 15
    for ln in lines:
        c.text(640, y, ln, 22, (215, 218, 226)); y += 30
    im = c.im.reduce(SS)
    fade = min(1.0, t / 0.3, (T - t) / 0.3)
    if fade < 1:
        im = Image.blend(Image.new("RGB", im.size, BG), im, max(0.0, fade))
    return im


# ---------------------------------------------------------------- audio
def make_audio(workdir):
    items = [{"text": s[3], "out": os.path.join(workdir, f"n{i:02d}.wav")} for i, s in enumerate(SCENES)]
    jp = os.path.join(workdir, "tts.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(items, f)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    os.path.join(HERE, "tts.ps1"), jp], check=True)
    durs, frames_list, params = [], [], None
    for it in items:
        with wave.open(it["out"]) as w:
            params = w.getparams()
            frames_list.append(w.readframes(w.getnframes()))
            durs.append(w.getnframes() / w.getframerate())
    rate, width = params.framerate, params.sampwidth
    scene_T, pcm = [], bytearray()
    for d, fr in zip(durs, frames_list):
        n = math.ceil((LEAD + d + TAIL) * FPS)
        T = n / FPS
        scene_T.append(T)
        total = int(round(T * rate)) * width
        chunk = bytearray(int(LEAD * rate) * width) + fr
        chunk = chunk[:total] + bytearray(max(0, total - len(chunk)))
        pcm += chunk
    out = os.path.join(workdir, "narration.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(width); w.setframerate(rate)
        w.writeframes(bytes(pcm))
    return out, scene_T, durs


def render(out_mp4):
    workdir = os.path.join(HERE, "work"); os.makedirs(workdir, exist_ok=True)
    wav, scene_T, durs = make_audio(workdir)
    print("scene lengths:", [round(t, 1) for t in scene_T], "total", round(sum(scene_T), 1), flush=True)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "128k", "-shortest",
                          "-movflags", "+faststart", out_mp4], stdin=subprocess.PIPE)
    for i, (T, d) in enumerate(zip(scene_T, durs)):
        n = round(T * FPS)
        for k in range(n):
            p.stdin.write(frame(i, k / FPS, T, d).tobytes())
        print(f"scene {i} done", flush=True)
    p.stdin.close(); p.wait()
    print("wrote", out_mp4, "rc", p.returncode)


def preview(outdir):
    os.makedirs(outdir, exist_ok=True)
    for i in range(len(SCENES)):
        T = 20.0
        frame(i, 0.95 * T, T, 17).save(os.path.join(outdir, f"s{i:02d}.png"))
    print("ok")


if __name__ == "__main__":
    (render if sys.argv[1] == "render" else preview)(sys.argv[2])
