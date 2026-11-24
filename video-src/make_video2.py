"""Part 2 (magnetostatics & currents) explainer. Reuses the drawing/render engine of make_video.py,
swapping in new scenes and a neural voice (edge-tts).

usage:  python make_video2.py render OUT.mp4
        python make_video2.py preview OUTDIR
"""
import asyncio, math, os, random, subprocess, sys, wave

import imageio_ffmpeg
import edge_tts

import make_video as mv
from make_video import (Cv, ease, partial, charge, bez, BG, INK, MUTED, ACC, PLUS, MINUS, GOOD, WARN, PANEL)

VOICE = "en-US-AvaNeural"

# ---------------------------------------------------------------- subscripts / superscripts in text
import re as _re
_orig_text = Cv.text


def _rich_text(self, x, y, s, size=24, col=INK, kind="sans", a=1.0, align="c"):
    if a <= 0 or not s:
        return
    if "_" not in s and "^" not in s:
        return _orig_text(self, x, y, s, size, col, kind, a, align)
    segs = []
    for m in _re.finditer(r"([_^])(\{[^}]*\}|.)|([^_^]+)", s):
        if m.group(3):
            segs.append((m.group(3), 0))
        else:
            t = m.group(2)
            segs.append((t[1:-1] if t.startswith("{") else t, 1 if m.group(1) == "_" else 2))
    fN, fS = mv.font(kind, size), mv.font(kind, max(8, int(size * 0.68)))
    ws = [self.d.textlength(t, font=fS if md else fN) for t, md in segs]
    total = sum(ws)
    px = x * SS - (total / 2 if align == "c" else total if align == "r" else 0)
    normal = "".join(t for t, md in segs if md == 0) or "x"
    bb = self.d.textbbox((0, 0), normal, font=fN, anchor="ls")
    base = y * SS - (bb[1] + bb[3]) / 2
    for (t, md), w in zip(segs, ws):
        off = 0 if md == 0 else (0.28 * size * SS if md == 1 else -0.42 * size * SS)
        self.d.text((px, base + off), t, font=fS if md else fN, fill=mv.mix(col, a), anchor="ls")
        px += w


Cv.text = _rich_text
SS = mv.SS


# ---------------------------------------------------------------- small helpers
def dot_out(c, x, y, r=9, col=ACC, a=1.0):
    c.circle(x, y, r, outline=col, w=1.8, a=a)
    c.circle(x, y, r * 0.28, fill=col, a=a)


def cross_in(c, x, y, r=9, col=ACC, a=1.0):
    c.circle(x, y, r, outline=col, w=1.8, a=a)
    k = r * 0.6
    c.line([(x - k, y - k), (x + k, y + k)], col, 1.8, a)
    c.line([(x + k, y - k), (x - k, y + k)], col, 1.8, a)


def panel_text(c, x, items, u):
    """items: (y, text, size, col, kind, start)"""
    for y, s, size, col, kind, st in items:
        c.text(x, y, s, size, col, kind, ease(u, st, st + 0.07))


# ---------------------------------------------------------------- scenes
def s_title(c, u, T):
    t = u * T
    # a wire with circular B field lines around it
    cx, cy = 640, 430
    for i, r in enumerate((50, 95, 140)):
        c.ellipse(cx - r * 1.6, cy - r * 0.45, cx + r * 1.6, cy + r * 0.45, ACC, 2, ease(u, 0.05 + 0.08 * i, 0.2 + 0.08 * i) * 0.6)
    c.line([(cx, 290), (cx, 590)], PLUS, 6)
    for k in range(5):
        y = 590 - ((t * 60 + k * 60) % 300)
        c.circle(cx, y, 4, fill=(255, 220, 210))
    c.text(640, 150, "Magnetostatics & Currents", 58, INK, "bold", ease(u, 0, 0.15))
    c.text(640, 215, "the logic behind each topic", 28, MUTED, "sans", ease(u, 0.08, 0.25))


def s_drift(c, u, T):
    t = u * T
    c.text(640, 140, "I = n q v_d S", 36, INK, "math", ease(u, 0, 0.08))
    c.rect(100, 220, 640, 420, fill=(40, 48, 66), outline=ACC, w=2, r=8)
    c.rect(636, 287, 1180, 353, fill=(40, 48, 66), outline=ACC, w=2, r=6)
    v1 = 22.0
    for row in range(6):
        y = 240 + row * 32
        for k in range(12):
            x = 100 + ((k * 50 + row * 17 + v1 * t) % 540)
            c.circle(x, y, 5, fill=MINUS)
    for row in range(2):
        y = 303 + row * 34
        for k in range(12):
            x = 640 + ((k * 50 + row * 23 + 3 * v1 * t) % 540)
            c.circle(x, y, 5, fill=MINUS)
    a = ease(u, 0.2, 0.3)
    c.arrow(300, 445, 380, 445, MINUS, 3, a, 12)
    c.text(370, 480, "big S → slow drift", 20, MUTED, a=a)
    c.arrow(860, 380, 1060, 380, MINUS, 3, a, 12)
    c.text(910, 415, "small S → fast drift", 20, MUTED, a=a)
    c.text(640, 520, "same I everywhere  ⇒  v_d ∝ 1 / S", 28, GOOD, "math", ease(u, 0.5, 0.6))


def s_ohm(c, u, T):
    t = u * T
    c.text(640, 140, "J = σ E", 40, INK, "math", ease(u, 0, 0.08))
    s = 0.35 + 0.65 * ease(u, 0.2, 0.45)
    heat = ease(u, 0.62, 0.8) * s
    c.rect(180, 250, 1100, 390, fill=tuple(int(a + (b - a) * heat * 0.5) for a, b in zip((40, 48, 66), (120, 70, 30))), outline=ACC, w=2, r=10)
    for k in range(6):
        x = 230 + k * 150
        c.arrow(x, 285, x + 110 * s, 285, ACC, 3, 1, 12)
        c.arrow(x, 355, x + 110 * s, 355, GOOD, 3, 1, 12)
    c.text(160, 285, "E", 26, ACC, "math", align="r")
    c.text(160, 355, "J", 26, GOOD, "math", align="r")
    c.text(640, 430, "J follows E point by point — the value of V itself doesn't matter, only its slope", 19, MUTED, a=ease(u, 0.45, 0.55))
    c.text(420, 495, "whole wire:  V = R I", 28, INK, "math", ease(u, 0.55, 0.62))
    c.text(860, 495, "heat:  P = I² R", 28, WARN, "math", ease(u, 0.65, 0.72))


def _blob(theta):
    return 150 + 110 * max(0.0, math.cos(theta)) ** 8


_rng = random.Random(4)
_START = []
for _ in range(34):
    th = _rng.uniform(0, 2 * math.pi); rr = _rng.uniform(0, 0.75) * _blob(th)
    _START.append((rr * math.cos(th), rr * math.sin(th)))
# final positions: denser near the tip (theta ~ 0)
_END = []
_ths = [(-math.pi + 2 * math.pi * (k + 0.5) / 34) for k in range(34)]
_ths = [th * (abs(th) / math.pi) ** 0.6 for th in _ths]  # bunch toward 0
_ths.sort()
for th in _ths:
    r = _blob(th) - 9
    _END.append((r * math.cos(th), r * math.sin(th)))
_START.sort(key=lambda p: math.atan2(p[1], p[0]))


def s_conductor(c, u, T):
    cx, cy = 450, 340
    pts = [(cx + _blob(th) * math.cos(th), cy + _blob(th) * math.sin(th)) for th in (2 * math.pi * k / 180 for k in range(181))]
    fillA = ease(u, 0.48, 0.58)
    c.poly(pts, fill=tuple(int(a + (b - a) * fillA * 0.35) for a, b in zip((34, 40, 54), GOOD)))
    c.line(pts, INK, 2.5)
    g = ease(u, 0.08, 0.42)
    ai = 1 - ease(u, 0.3, 0.45)
    for k in range(5):
        y = 250 + k * 45
        c.arrow(cx - 60, y, cx + 40, y, WARN, 2.5, ai * 0.9, 10)
    for (x0, y0), (x1, y1) in zip(_START, _END):
        c.circle(cx + x0 + (x1 - x0) * g, cy + y0 + (y1 - y0) * g, 5.5, fill=PLUS)
    c.text(cx - 30, cy, "V = const", 30, INK, "math", fillA)
    c.text(cx - 30, cy + 34, "E = 0 inside", 20, MUTED, a=fillA)
    ao = ease(u, 0.6, 0.72)
    for th in [math.radians(a) for a in (-150, -110, -70, -35, -12, 0, 12, 35, 70, 110, 150, 180)]:
        r = _blob(th)
        L = 25 + 0.55 * (r - 140)
        x0, y0 = cx + (r + 8) * math.cos(th), cy + (r + 8) * math.sin(th)
        c.arrow(x0, y0, x0 + L * math.cos(th), y0 + L * math.sin(th), ACC, 2.5, ao, 10)
    panel_text(c, 1060, [
        (200, "charges move until", 20, INK, "sans", 0.1), (228, "the inside field is gone", 20, INK, "sans", 0.1),
        (300, "E_{in} = 0", 30, WARN, "math", 0.42),
        (360, "→ V same at every point", 22, GOOD, "sans", 0.52),
        (440, "at the tip: more σ, stronger E outside", 18, ACC, "sans", 0.66),
        (466, "(but the same V!)", 18, MUTED, "sans", 0.7)], u)


def s_rc(c, u, T):
    # circuit
    x0, x1, y0, y1 = 110, 500, 190, 450
    c.line([(x0, y0), (250, y0)], INK, 3); c.line([(370, y0), (x1, y0), (x1, 305)], INK, 3)
    c.line([(x1, 335), (x1, y1), (x0, y1), (x0, 335)], INK, 3); c.line([(x0, 305), (x0, y0)], INK, 3)
    zz = [(250, y0)] + [(262 + 12 * k, y0 + (-14 if k % 2 == 0 else 14)) for k in range(9)] + [(370, y0)]
    c.line(zz, PLUS, 3)
    c.text(310, 150, "R", 24, PLUS, "math")
    c.line([(x0 - 26, 305), (x0 + 26, 305)], INK, 4); c.line([(x0 - 14, 335), (x0 + 14, 335)], INK, 4)
    c.text(x0 - 40, 320, "ℰ", 26, INK, "math", align="r")
    c.line([(x1 - 30, 305), (x1 + 30, 305)], GOOD, 5); c.line([(x1 - 30, 335), (x1 + 30, 335)], GOOD, 5)
    c.text(x1 + 46, 320, "C", 24, GOOD, "math", align="l")
    q = ease(u, 0.2, 0.75)
    nq = int(round(q * 5))
    for k in range(nq):
        c.text(x1 - 24 + k * 12, 290, "+", 14, PLUS, "bold"); c.text(x1 - 24 + k * 12, 352, "−", 14, MINUS, "bold")
    # graph
    gx0, gx1, gy0, gy1 = 640, 1180, 200, 440
    c.line([(gx0, gy1), (gx1, gy1)], MUTED, 1.5); c.line([(gx0, gy0 - 10), (gx0, gy1)], MUTED, 1.5)
    c.dashed([(gx0, gy0), (gx1, gy0)], MUTED, 1.2, 0.7)
    c.text(gx0 - 10, gy0, "ℰ", 22, MUTED, "math", align="r")
    c.text(gx1, gy1 + 22, "t", 20, MUTED, "math", align="r")
    tau = 120
    g = ease(u, 0.2, 0.75)
    vr = [(gx0 + x, gy1 - (gy1 - gy0) * math.exp(-x / tau)) for x in range(0, gx1 - gx0 + 1, 6)]
    vc = [(gx0 + x, gy1 - (gy1 - gy0) * (1 - math.exp(-x / tau))) for x in range(0, gx1 - gx0 + 1, 6)]
    c.line(partial(vr, g), PLUS, 4); c.line(partial(vc, g), GOOD, 4)
    a0 = ease(u, 0.15, 0.25)
    c.circle(gx0, gy0, 8, outline=WARN, w=3, a=a0)
    c.text(gx0 + 18, gy0 - 22, "t = 0: V_R = ℰ, V_C = 0", 20, WARN, "math", a0, "l")
    c.text(gx0 + 190, gy1 - 40, "V_R", 22, PLUS, "math", ease(u, 0.4, 0.5))
    c.text(gx0 + 190, gy0 + 42, "V_C", 22, GOOD, "math", ease(u, 0.4, 0.5))
    c.text(900, 500, "V_R = ℰ e^{−t/RC}      V_C = ℰ (1 − e^{−t/RC})", 22, INK, "math", ease(u, 0.7, 0.78))


def s_lorentz(c, u, T):
    for gx in range(130, 760, 60):
        for gy in range(140, 560, 60):
            cross_in(c, gx, gy, 7, MUTED, 0.45)
    c.text(130, 118, "B into the page", 18, MUTED, align="l")
    cx, cy, R = 440, 345, 150
    g = ease(u, 0.08, 0.95)
    ph_end = -math.pi / 2 + 2 * math.pi * 1.6 * (u - 0.08) / 0.87 if u > 0.08 else -math.pi / 2
    ph0 = -math.pi / 2
    if u > 0.08:
        n = 80
        trail = [(cx + R * math.cos(ph0 + (ph_end - ph0) * k / n), cy - R * math.sin(ph0 + (ph_end - ph0) * k / n)) for k in range(n + 1)]
        c.line(trail[-60:] if ph_end - ph0 > 2 * math.pi else trail, WARN, 2.5, 0.6)
    ph = ph_end
    px, py = cx + R * math.cos(ph), cy - R * math.sin(ph)
    vx, vy = -math.sin(ph), -math.cos(ph)
    c.arrow(px, py, px + 80 * vx, py + 80 * vy, INK, 3, 1, 12)
    c.arrow(px, py, px + 75 * (cx - px) / R, py + 75 * (cy - py) / R, WARN, 3.5, ease(u, 0.12, 0.2), 13)
    charge(c, px, py, 12, +1)
    c.text(px + 92 * vx, py + 92 * vy, "v", 22, INK, "math")
    panel_text(c, 1020, [
        (190, "F = q v × B", 36, INK, "math", 0.05),
        (260, "F is perpendicular to v and B", 20, WARN, "sans", 0.2),
        (310, "no work → speed stays constant", 20, INK, "sans", 0.38),
        (350, "it only bends the path", 20, INK, "sans", 0.45),
        (420, "uniform B → circle", 20, MUTED, "sans", 0.6),
        (460, "r = m v / (q B)", 28, GOOD, "math", 0.62)], u)


def s_wire_dir(c, u, T):
    wx = 360
    c.line([(wx, 560), (wx, 130)], PLUS, 6)
    c.arrow(wx, 200, wx, 130, PLUS, 6, 1, 20)
    c.text(wx - 18, 140, "I (+y)", 22, PLUS, "math", align="r")
    aB = ease(u, 0.08, 0.18)
    for gy in range(170, 560, 70):
        for gx in (180, 260):
            dot_out(c, gx, gy, 8, ACC, aB * 0.8)
        for gx in (460, 560, 660, 760):
            cross_in(c, gx, gy, 8, ACC, aB * 0.8)
    c.text(220, 120, "B out", 18, ACC, a=aB)
    c.text(610, 120, "B into page (−z)", 18, ACC, a=aB)
    g = ease(u, 0.25, 0.7)
    px, py = 450 + 280 * g, 395
    if u > 0.2:
        c.line([(450, py), (px, py)], MUTED, 1.5, 0.6)
        c.arrow(px, py, px + 70, py, INK, 3, 1, 12)
        c.arrow(px, py, px, py - 90, WARN, 4, ease(u, 0.35, 0.42), 14)
        charge(c, px, py, 12, +1)
        c.text(px + 80, py + 22, "v (+x)", 20, INK, "math")
        c.text(px + 14, py - 100, "F (+y)", 22, WARN, "math", ease(u, 0.35, 0.42), "l")
    panel_text(c, 1060, [
        (200, "1. right-hand grip:", 20, INK, "sans", 0.1), (228, "B points into the page", 20, ACC, "sans", 0.1),
        (300, "2. F = q v × B", 26, INK, "math", 0.3), (338, "x × (−z) = +y", 26, WARN, "math", 0.36),
        (420, "moving away from the wire", 19, MUTED, "sans", 0.6), (446, "→ pushed along the current", 19, GOOD, "sans", 0.6)], u)


def s_ampere(c, u, T):
    c.text(640, 140, "∮ B · dl = μ₀ I_{enc}     (signed sum)", 32, INK, "math", ease(u, 0, 0.08))
    P = {1: (330, 340), 2: (600, 340), 3: (870, 340)}
    for k, (x, y) in P.items():
        if k == 3:
            cross_in(c, x, y, 16, PLUS)
        else:
            dot_out(c, x, y, 16, PLUS)
        c.text(x, y + 40, f"I{'₁₂₃'[k - 1]}", 24, INK, "math")
    c.text(330, 230, "out (+)", 17, MUTED); c.text(600, 230, "out (+)", 17, MUTED); c.text(870, 230, "in (−)", 17, MUTED)
    loops = [((230, 270, 700, 410), ACC, "I₁ + I₂ = 2I  →  2μ₀I", 0.15, 0.38),
             ((500, 270, 970, 410), GOOD, "I₂ − I₃ = 0  →  ∮ B·dl = 0", 0.38, 0.62),
             ((200, 255, 1000, 425), WARN, "I₁ + I₂ − I₃ = I  →  μ₀I", 0.62, 0.86)]
    for (x0, y0, x1, y1), col, lab, s, e in loops:
        a = ease(u, s, s + 0.05) * (1 - ease(u, e - 0.03, e + 0.02)) if e < 0.85 else ease(u, s, s + 0.05)
        if a > 0:
            c.ellipse(x0, y0, x1, y1, col, 3, a)
            c.text(640, 500, lab, 28, col, "math", a)


def s_thick(c, u, T):
    cx, cy, a = 280, 330, 110
    c.circle(cx, cy, a, fill=(52, 44, 50), outline=PLUS, w=2)
    rmax = 1.7 * a
    g = ease(u, 0.12, 0.72)
    r = g * rmax
    if r > 2:
        c.circle(cx, cy, min(r, a), fill=(80, 66, 40), a=0.9)
    for gx in range(-100, 101, 25):
        for gy in range(-100, 101, 25):
            if gx * gx + gy * gy < (a - 8) ** 2:
                dot_out(c, cx + gx, cy + gy, 4, PLUS, 0.7)
    if r > 2:
        mv.dashed_circle(c, cx, cy, r, WARN, 2.5, 1, 48)
    c.text(cx, 528, "dashed loop: I_{enc} = I · r²/a²  (inside)", 18, MUTED, a=ease(u, 0.15, 0.25))
    # graph
    gx0, gx1, gy0, gy1 = 620, 1180, 230, 450
    c.line([(gx0, gy1), (gx1, gy1)], MUTED, 1.5); c.line([(gx0, gy0 - 10), (gx0, gy1)], MUTED, 1.5)
    xa = gx0 + 180
    c.dashed([(xa, gy0 - 5), (xa, gy1)], MUTED, 1.2, 0.7)
    c.text(xa, gy1 + 20, "a", 20, MUTED, "math"); c.text(gx0 + 90, gy1 + 20, "a/2", 18, MUTED, "math")
    c.text(gx1, gy1 + 20, "r", 20, MUTED, "math", align="r")
    hmax = 190

    def B(rr):
        return rr / a if rr <= a else a / rr
    xs = [k * rmax / 100 for k in range(101)]
    pts = [(gx0 + 180 * x / a, gy1 - hmax * B(x)) for x in xs]
    c.line(partial(pts, g), ACC, 4)
    if r > 2:
        c.circle(gx0 + 180 * r / a, gy1 - hmax * B(r), 6, fill=WARN)
    am = ease(u, 0.75, 0.82)
    c.circle(gx0 + 90, gy1 - hmax / 2, 7, outline=WARN, w=3, a=am)
    c.text(gx0 + 105, gy1 - hmax / 2 + 26, "B(a/2) = μ₀ I / (4πa)", 22, WARN, "math", am, "l")
    c.text(900, 140, "inside:  B = μ₀ I r / (2π a²)   ∝ r", 24, INK, "math", ease(u, 0.3, 0.38))
    c.text(900, 180, "outside:  B = μ₀ I / (2π r)   ∝ 1/r", 24, INK, "math", ease(u, 0.55, 0.63))


def s_loop(c, u, T):
    cx, cy, R = 400, 345, 170
    c.circle(cx, cy, R, outline=PLUS, w=5)
    t = u * T
    for k in range(8):
        ph = 2 * math.pi * k / 8 + t * 0.6
        x, y = cx + R * math.cos(ph), cy + R * math.sin(ph)
        tx, ty = -math.sin(ph), math.cos(ph)
        c.arrow(x - 12 * tx, y - 12 * ty, x + 12 * tx, y + 12 * ty, (255, 200, 190), 3, 1, 10)
    c.text(cx + R + 20, cy - R + 10, "I", 26, PLUS, "math", align="l")
    g = ease(u, 0.15, 0.6)
    ph = 2 * math.pi * g - math.pi / 2
    ex, ey = cx + R * math.cos(ph), cy + R * math.sin(ph)
    if 0.1 < u < 0.65:
        c.line([(cx, cy), (ex, ey)], MUTED, 1.5, 0.8)
        c.circle(ex, ey, 9, outline=WARN, w=3)
        c.text((cx + ex) / 2 + 14, (cy + ey) / 2, "R", 20, MUTED, "math", align="l")
        # swept arc
    if g > 0:
        arc = [(cx + R * math.cos(-math.pi / 2 + 2 * math.pi * g * k / 60), cy + R * math.sin(-math.pi / 2 + 2 * math.pi * g * k / 60)) for k in range(61)]
        c.line(arc, WARN, 6, 0.8)
    rB = 8 + 22 * g
    dot_out(c, cx, cy, rB, ACC)
    c.text(cx, cy + rB + 22, "B (out of page)", 18, ACC)
    panel_text(c, 1000, [
        (180, "every dl: same distance R,", 20, INK, "sans", 0.12), (208, "perpendicular to the radius", 20, INK, "sans", 0.12),
        (265, "dB = μ₀ I dl / (4π R²)", 28, WARN, "math", 0.25),
        (330, "add up the full length 2πR:", 20, MUTED, "sans", 0.45),
        (390, "B = μ₀ I / (2R)", 40, GOOD, "math", 0.6),
        (455, "no π — μ₀I/(2πR) is the straight wire", 18, MUTED, "sans", 0.75)], u)


def s_parallel(c, u, T):
    attract = ease(u, 0.12, 0.42)
    repel_phase = ease(u, 0.5, 0.55)
    repel = ease(u, 0.58, 0.85)
    d = 260 - 60 * attract * (1 - repel_phase) + (-60 + 120 * repel) * repel_phase if repel_phase > 0 else 260 - 60 * attract
    if repel_phase > 0:
        d = 200 + 140 * repel
    x1, x2 = 500 - d / 2, 500 + d / 2
    up2 = repel_phase < 0.5
    c.line([(x1, 150), (x1, 540)], PLUS, 6); c.arrow(x1, 220, x1, 150, PLUS, 6, 1, 20)
    c.line([(x2, 150), (x2, 540)], PLUS, 6)
    if up2:
        c.arrow(x2, 220, x2, 150, PLUS, 6, 1, 20)
    else:
        c.arrow(x2, 470, x2, 540, PLUS, 6, 1, 20)
    c.text(x1 - 16, 160, "I₁", 24, PLUS, "math", align="r"); c.text(x2 + 16, 160, "I₂", 24, PLUS, "math", align="l")
    af = ease(u, 0.1, 0.18)
    for y in (300, 380, 460):
        if up2:
            c.arrow(x1 + 8, y, x1 + 60, y, WARN, 3.5, af, 12); c.arrow(x2 - 8, y, x2 - 60, y, WARN, 3.5, af, 12)
        else:
            c.arrow(x1 - 8, y, x1 - 60, y, WARN, 3.5, 1, 12); c.arrow(x2 + 8, y, x2 + 60, y, WARN, 3.5, 1, 12)
    c.text(500, 112, "same direction → attract" if up2 else "opposite directions → repel", 22, WARN, a=af)
    c.rect(850, 170, 1220, 500, fill=PANEL, r=14)
    panel_text(c, 1035, [
        (220, "wire 1 makes at wire 2:", 18, MUTED, "sans", 0.05),
        (255, "B₁ = μ₀ I₁ / (2π d)", 24, ACC, "math", 0.05),
        (310, "wire 2 feels F = I₂ L B₁", 22, INK, "math", 0.15),
        (370, "F/L = μ₀ I₁ I₂ / (2π d)", 28, GOOD, "math", 0.25),
        (430, "μ₀ / 2π = 2 × 10⁻⁷", 22, MUTED, "math", 0.65),
        (468, "0.2 A, 5 A, 20 cm → 1 μN/m", 18, MUTED, "math", 0.72)], u)


def s_faraday(c, u, T):
    cx, cy = 400, 380
    s = ease(u, 0.1, 0.7)
    n = 3 + int(round(6 * s))
    for k in range(n):
        x = cx - 120 + 240 * (k + 0.5) / n
        c.arrow(x, 560, x, 150, ACC, 2.5, 0.85, 12)
    c.text(cx + 150, 165, f"B growing", 20, ACC, align="l")
    c.ellipse(cx - 170, cy - 45, cx + 170, cy + 45, PLUS, 6)
    ai = ease(u, 0.3, 0.4)
    for ph in (0.4, 2.0, 3.6, 5.2):
        x, y = cx + 170 * math.cos(ph), cy + 45 * math.sin(ph)
        tx, ty = -170 * math.sin(ph), 45 * math.cos(ph)
        L = math.hypot(tx, ty)
        # clockwise seen from above = decreasing phase on screen ellipse
        c.arrow(x + 14 * tx / L, y + 14 * ty / L, x - 14 * tx / L, y - 14 * ty / L, WARN, 4, ai, 12)
    c.arrow(cx + 200, 300, cx + 200, 460, WARN, 4, ai, 14)
    c.text(cx + 215, 380, "induced B opposes the increase", 18, WARN, a=ai, align="l")
    panel_text(c, 1010, [
        (170, "Φ = N B A cos θ", 30, INK, "math", 0.05),
        (235, "ℰ = − N dΦ/dt", 34, GOOD, "math", 0.2),
        (300, "change B, A or the angle → emf", 18, MUTED, "sans", 0.4),
        (330, "minus sign (Lenz): oppose the change", 18, WARN, "sans", 0.5),
        (410, "10 turns · 0.02 m² · 0.1 T/s", 20, INK, "math", 0.7),
        (445, "ℰ = −20 mV", 28, GOOD, "math", 0.75)], u)


def s_rotate(c, u, T):
    cx, cy = 280, 345
    for y in range(190, 520, 55):
        c.arrow(80, y, 490, y, MUTED, 1.5, 0.5, 10)
    c.text(480, 168, "B", 22, MUTED, "math", align="r")
    cyc = 2.25
    wt = 2 * math.pi * cyc * u
    nx, ny = math.cos(wt), math.sin(wt)
    L = 130
    c.line([(cx - L * ny, cy - L * nx), (cx + L * ny, cy + L * nx)], PLUS, 7)
    c.arrow(cx, cy, cx + 70 * nx, cy - 70 * ny, WARN, 3, 1, 12)
    c.text(cx + 88 * nx, cy - 88 * ny, "n", 20, WARN, "math")
    c.text(cx, 560, "side view: coil turning at ω", 18, MUTED)
    gx0, gx1 = 640, 1180
    rows = [(190, lambda x: math.cos(x), ACC, "Φ = B A cos ωt"),
            (330, lambda x: math.sin(x), GOOD, "ℰ = B A ω sin ωt"),
            (470, lambda x: math.sin(x) ** 2, WARN, "P = ℰ²/R = A² B² ω² sin² ωt / R")]
    for i, (yc, f, col, lab) in enumerate(rows):
        a = ease(u, 0.04 + 0.12 * i, 0.1 + 0.12 * i)
        base = yc + 45 if i == 2 else yc
        c.line([(gx0, base), (gx1, base)], MUTED, 1.2, a * 0.7)
        pts = [(gx0 + (gx1 - gx0) * k / 200, (yc + 45 - 90 * f(2 * math.pi * cyc * k / 200)) if i == 2 else (yc - 45 * f(2 * math.pi * cyc * k / 200))) for k in range(201)]
        c.line(pts[:max(2, int(201 * u))], col, 3.5, a)
        c.text(gx0, yc - 62, lab, 21, col, "math", a, "l")
    xc = gx0 + (gx1 - gx0) * u
    c.line([(xc, 120), (xc, 525)], INK, 1.2, 0.5)


def s_reversal(c, u, T):
    cx, cy = 330, 345
    c.rect(cx - 70, 160, cx + 70, 530, fill=(60, 62, 70), r=10)
    for k in range(9):
        y = 190 + k * 38
        c.ellipse(cx - 92, y - 10, cx + 92, y + 10, PLUS, 3)
    c.text(cx, 140, "N = 100 turns, A = 0.001 m²", 18, MUTED)
    flip = ease(u, 0.22, 0.5)
    b = 1 - 2 * flip
    if abs(b) > 0.05:
        c.arrow(cx, 345 + 120 * b, cx, 345 - 120 * b, ACC, 7, 1, 22)
    c.text(cx + 110, 345, f"B = {b:+.1f} T", 22, ACC, "math", align="l")
    # flux axis
    ax = 820
    c.line([(ax, 170), (ax, 520)], MUTED, 1.5)
    c.line([(ax - 8, 345), (ax + 8, 345)], MUTED, 1.5)
    c.text(ax - 14, 200, "+BA", 20, MUTED, "math", align="r"); c.text(ax - 14, 490, "−BA", 20, MUTED, "math", align="r")
    yphi = 345 - 145 * b
    c.circle(ax, yphi, 9, fill=ACC)
    ab = ease(u, 0.52, 0.6)
    c.line([(ax + 30, 200), (ax + 45, 200), (ax + 45, 490), (ax + 30, 490)], WARN, 3, ab)
    c.text(ax + 60, 345, "ΔΦ = 2BA", 28, WARN, "math", ab, "l")
    c.text(ax + 60, 380, "not BA!", 18, MUTED, a=ab, align="l")
    c.text(860, 140, "Q = ∫ I dt = N ΔΦ / R", 30, GOOD, "math", ease(u, 0.62, 0.7))
    c.text(1000, 530, "Q = 100 · 2 · 1 · 0.001 / 10 = 0.02 C", 22, INK, "math", ease(u, 0.74, 0.8))


def s_summary(c, u, T):
    a = [ease(u, s, s + 0.08) for s in (0.02, 0.14, 0.3, 0.46, 0.62)]
    mv.node(c, 200, 290, 200, 76, "currents I", a[0], 26)
    mv.node(c, 640, 290, 200, 76, "B field", a[1], 26)
    mv.node(c, 1080, 290, 200, 76, "forces", a[2], 26)
    c.arrow(302, 290, 536, 290, INK, 3, a[1], 14)
    c.text(420, 262, "Biot–Savart · Ampère", 18, MUTED, a=a[1])
    c.arrow(742, 290, 976, 290, INK, 3, a[2], 14)
    c.text(860, 262, "F = q v × B", 22, INK, "math", a[2])
    c.text(860, 322, "F/L = μ₀I₁I₂/(2πd)", 18, MUTED, "math", a[2])
    mv.node(c, 640, 470, 240, 70, "changing Φ", a[3], 24)
    c.arrow(640, 330, 640, 432, INK, 3, a[3], 14)
    c.text(655, 385, "Φ = B A", 20, MUTED, "math", a[3], "l")
    arc = bez((518, 470), (200, 520), (200, 330), 40)
    c.line(partial(arc, a[4]), GOOD, 3)
    if a[4] > 0.95:
        c.arrow(*arc[-3], *arc[-1], GOOD, 3, 1, 14)
    c.text(300, 520, "Faraday: emf = −N dΦ/dt drives new currents", 18, GOOD, a=a[4], align="l")


SCENES = [
    ("", s_title, None,
     "Welcome to part two: magnetostatics and currents. Once again, we'll focus on the logic: how charges flow, how currents create magnetic fields, how those fields push on moving charges, and how a changing field creates new currents."),
    ("Current and drift velocity", s_drift, "Same current through a narrower wire  →  faster drift",
     "A current is just charge carriers drifting through a wire. In one second, every carrier within a length v d of the cross-section passes through it. So the current is n, times q, times the drift speed, times the section S. In a steady circuit, charge can't pile up, so the same current flows everywhere. If the wire gets narrower, the electrons have to drift faster, exactly like water speeding up in a narrow pipe."),
    ("Ohm's law and power", s_ohm, "J follows E point by point  ·  heat P = I²R",
     "What pushes the carriers is the electric field. In an ohmic material, the current density at each point is proportional to the field at that same point: J equals sigma E. It's the slope of the potential that matters, never the value of V itself. Integrated over the whole wire, this becomes V equals R I. And the energy the carriers lose in collisions turns into heat, at a rate of I squared R."),
    ("Conductor in equilibrium", s_conductor, "No field inside  →  the whole conductor is at one potential",
     "Now stop the current. In a conductor in equilibrium, nothing is moving. If there were any field inside, the free electrons would move, so the charges rearrange until the inside field is exactly zero. With zero field, the potential can't change from point to point, so the whole conductor sits at one single potential. Near sharp tips, the surface charge and the outside field are stronger, but the potential is still the same."),
    ("RC circuit at the switch-on", s_rc, "At t = 0 the capacitor acts like a wire  →  the full emf is across R",
     "Connect a resistor and an uncharged capacitor to a battery. The capacitor's voltage is Q over C, and at the very first instant there's no charge yet, so its voltage is zero. It behaves like a plain wire, and the whole battery voltage appears across the resistor. As charge builds up, the capacitor voltage rises, the resistor voltage decays exponentially, and eventually the current stops."),
    ("The magnetic force", s_lorentz, "F = qv×B is perpendicular to v and B: it bends, never speeds up",
     "A magnetic field pushes on moving charges with the Lorentz force: q times v cross B. Because it's a cross product, the force is always perpendicular to both the velocity and the field. That means it does no work. It can't speed the particle up or slow it down; it can only bend its path. In a uniform field, the charge goes around in a circle."),
    ("Finding the force direction", s_wire_dir, "Moving away from a wire  →  pushed along the current",
     "Here's the recipe for direction questions. First, find B with the right hand grip: thumb along the current, fingers curl along the field. To the right of a wire carrying current upward, B points into the page. Second, take the cross product. The charge moves in plus x, B is minus z, and x cross minus z gives plus y. So a positive charge moving away from the wire is pushed along the current."),
    ("Ampère's law", s_ampere, "Only the signed enclosed current counts",
     "Ampère's law says the circulation of B around any closed loop equals mu zero times the current passing through it, counted with sign. Currents in one direction count as positive, opposite ones as negative, and currents outside the loop don't count at all. So if a loop encloses two equal currents flowing in opposite directions, the line integral is exactly zero."),
    ("Inside a thick wire", s_thick, "Inside: B grows with r  ·  outside: B falls as 1/r",
     "Apply Ampère's law to a thick wire with uniform current. Outside, the loop encloses all the current, and B falls as one over r. Inside, the loop only encloses a fraction of the current, r squared over a squared, so B grows linearly with r. At half the radius, B is mu zero I over four pi a: exactly half its value at the surface."),
    ("Centre of a current loop", s_loop, "Every element adds the same way  →  B = μ₀I / 2R",
     "For a circular loop, use Biot–Savart. Every little piece of wire is the same distance R from the centre, and perpendicular to the radius, so every piece adds a contribution pointing the same way. Summing over the whole circumference, two pi R, gives B equals mu zero I over two R. Notice: no pi. Mu zero I over two pi R is the straight wire."),
    ("Force between parallel wires", s_parallel, "Same direction attracts  ·  opposite directions repel",
     "Two parallel wires push on each other. Wire one creates a field at wire two, and wire two, carrying a current in that field, feels a force. Per unit length, it's mu zero I one I two over two pi d. Currents in the same direction attract. Opposite currents repel. It's the same rule as the moving charge: currents that run alongside each other pull together."),
    ("Faraday's law of induction", s_faraday, "Changing flux  →  emf that opposes the change",
     "Now the reverse: a changing magnetic field creates a current. The emf equals minus N times the rate of change of the flux through the coil. It doesn't matter how the flux changes: the field, the area, or the angle. The minus sign is Lenz's law: the induced current makes its own field that opposes the change. For example, ten turns of two hundred square centimetres, in a field rising at point one tesla per second, give minus twenty millivolts."),
    ("Rotating coil", s_rotate, "emf = BAω sin ωt  →  P = A²B²ω² sin²ωt / R",
     "When a coil rotates in a uniform field, the flux goes like B A cosine omega t. Taking the derivative, the emf is B A omega sine omega t: a sine wave, largest when the flux is passing through zero. The power dissipated is the emf squared over R, so both A and B appear squared: A squared, B squared, omega squared, sine squared omega t, over R."),
    ("Charge from a flux reversal", s_reversal, "Charge depends only on the total flux change  ·  reversal = 2BA",
     "How much charge flows when the flux changes? Integrate the current over time. The time cancels out, and the charge is simply N times the change in flux, divided by R. If the field reverses, from plus B to minus B, the flux change is two B A, not B A. With a hundred turns, a thousandth of a square metre, one tesla and ten ohms, that's point zero two coulombs."),
    ("The whole chain", s_summary, None,
     "Here's the whole picture. Currents create magnetic fields, through Biot–Savart and Ampère's law. Those fields push on moving charges and on other currents. And when the magnetic flux changes, Faraday's law creates an emf that drives new currents. Keep this loop in mind, and every question in this part of the course falls into place."),
]


async def _tts(text, path):
    await edge_tts.Communicate(text, VOICE, rate="-4%").save(path)


def make_audio(workdir):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    durs, frames_list = [], []
    for i, s in enumerate(SCENES):
        mp3 = os.path.join(workdir, f"p2_{i:02d}.mp3"); wav = os.path.join(workdir, f"p2_{i:02d}.wav")
        asyncio.run(_tts(s[3], mp3))
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", mp3, "-ar", "24000", "-ac", "1", "-sample_fmt", "s16", wav], check=True)
        with wave.open(wav) as w:
            frames_list.append(w.readframes(w.getnframes())); durs.append(w.getnframes() / w.getframerate())
            rate, width = w.getframerate(), w.getsampwidth()
    scene_T, pcm = [], bytearray()
    for d, fr in zip(durs, frames_list):
        n = math.ceil((mv.LEAD + d + mv.TAIL) * mv.FPS)
        T = n / mv.FPS; scene_T.append(T)
        total = int(round(T * rate)) * width
        chunk = bytearray(int(mv.LEAD * rate) * width) + fr
        pcm += chunk[:total] + bytearray(max(0, total - len(chunk)))
    out = os.path.join(workdir, "narration_p2.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(width); w.setframerate(rate); w.writeframes(bytes(pcm))
    return out, scene_T, durs


mv.SCENES = SCENES
mv.make_audio = make_audio

if __name__ == "__main__":
    if sys.argv[1] == "render":
        mv.render(sys.argv[2])
    else:
        os.makedirs(sys.argv[2], exist_ok=True)
        for i in range(len(SCENES)):
            for frac in (0.5, 0.95):
                mv.frame(i, frac * 20, 20.0, 17).save(os.path.join(sys.argv[2], f"s{i:02d}_{int(frac*100)}.png"))
        print("ok")
