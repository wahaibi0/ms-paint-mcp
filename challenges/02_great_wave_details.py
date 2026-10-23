"""Challenge 2, detail pass: zoomed in, piece by piece, on the same canvas.

Run one phase at a time and look at the canvas in between:
    uv run challenges/02_great_wave_details.py A
A: foam claws and droplets   A2: irregular lip claws   B: depth under the crest
C: boats and rowers   D: sky and the mountain
Each phase's recording is appended to 02_great_wave.gif.
"""
import math
import os
import random
import sys
from importlib import import_module

import brushlib
from brushlib import color, cover, line, p, save, smooth
from record import append_gif, recording

wave = import_module("02_great_wave")
W, H, HERE, CREST, offset = wave.W, wave.H, wave.HERE, wave.CREST, wave.offset
CREAM, SKY_MID, SKY_TOP = wave.CREAM, wave.SKY_MID, wave.SKY_TOP
NAVY, BLUE, MID_BLUE, LIGHT_BLUE, FOAM, BOAT = wave.NAVY, wave.BLUE, wave.MID_BLUE, wave.LIGHT_BLUE, wave.FOAM, wave.BOAT
SHADOW = "#0F1A31"
GIF = os.path.join(HERE, "02_great_wave.gif")


def pen_line(pts, size):
    color(NAVY)
    p.stroke([(round(x), round(y)) for x, y in pts], size=size, brush="Calligraphy pen")


def sky_at(x, y):
    """The sky band color at a point, following the bands' lower edges."""
    return SKY_TOP if y < 62 - 12 * x / W else SKY_MID if y < 106 + 8 * math.sin(math.pi * x / W) else CREAM


def sky_strip(chain, size):
    """Paint the sky back along a chain, switching color where it crosses a band edge."""
    run = []
    for q in chain + [None]:
        c = sky_at(*q) if q else None
        if run and (c != run[0]):
            if len(run) > 2:
                line(run[0], size, *run[1:])
            run = []
        if q:
            run = run or [c]
            run.append(q)


def claw_path(base, start_ang, end_ang, length, steps=8):
    """A finger of foam: leaves `base` heading `start_ang`, bending to `end_ang` at the tip."""
    pts = [base]
    for i in range(1, steps + 1):
        t = i / steps
        ang = start_ang + (end_ang - start_ang) * t * t
        x, y = pts[-1]
        pts.append((x + math.cos(ang) * length / steps, y + math.sin(ang) * length / steps))
    return pts


def tapered(pts, c, sizes):
    """One finger drawn as overlapping pieces that thin toward the tip."""
    n = len(sizes)
    for j, s in enumerate(sizes):
        piece = pts[j * (len(pts) - 1) // n: (j + 1) * (len(pts) - 1) // n + 1]
        if len(piece) > 1:
            line(c, s, *piece, wobble=0.3)


def claws(fingers, rim_sizes, foam_sizes):
    """Rims first for all fingers, then the foam on top: two color changes, not two per finger."""
    for f in fingers:
        tapered(f, LIGHT_BLUE, rim_sizes)
    for f in fingers:
        tapered(f, FOAM, foam_sizes)


def boat(x0, y0, x1, y1, depth):
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    top = smooth((x0, y0), (mx, my - 3), (x1, y1))
    hull = smooth((x1 - 6, y1 + depth * 0.6), (mx, my + depth), (x0 + 8, y0 + depth * 0.6))
    return top, hull


def phase_a():
    """Foam: clear the scalloped fringe, smooth the lip, then claws one by one, then droplets."""
    print(p.zoom(200, 330, 190))
    tangent = lambda i: math.atan2(CREST[i + 1][1] - CREST[i][1], CREST[i + 1][0] - CREST[i][0])
    # the pale scalloped fringe above the crest goes back to sky
    sky_strip(offset(CREST[5:-1], -9), 15)
    # the jagged outline under the lip goes back to the wave's blue
    line(BLUE, 9, (520, 180), (506, 212), (470, 206), (440, 194), (404, 198))
    # a smooth lip: the crest outline, round over the tip and back under it
    lip = smooth(CREST[-1], (526, 196), (512, 214), (480, 212), (446, 200), (406, 200))
    pen_line(CREST[4:] + lip[1:], 4)
    # small fingers riding the crest, leaning forward and curling down
    small = []
    for i in range(len(CREST) // 4, len(CREST) - 10, 2):
        a = tangent(i)
        small.append(claw_path(CREST[i], a - 0.5, a + 1.3, random.uniform(13, 19)))
    claws(small, [6, 4, 3], [4, 3, 2])
    # big claws hanging from the lip, reaching down into the hollow and hooking back
    big = []
    for q in CREST[-11:-1:2] + lip[2:-2:3]:
        big.append(claw_path(q, math.radians(random.uniform(65, 95)), math.radians(random.uniform(170, 200)), random.uniform(30, 46)))
    claws(big, [11, 8, 5], [7, 5, 3])
    # droplets thrown off the tips
    color(FOAM)
    for _ in range(45):
        x, y = random.gauss(520, 40), random.gauss(220, 45)
        if 0 <= x < W and 120 < y < 330 and not (x < 380 and y > 200):
            p.stroke([(round(x), round(y)), (round(x) + 1, round(y))], size=random.choice((2, 3, 3, 4)))


def phase_a2():
    """Second look at the foam: the lip's claws hung like an even comb. Add a few larger, irregular
    claws reaching forward and down from the front of the lip, each with its own length and curl."""
    print(p.zoom(200, 400, 200))
    big = []
    for x, y in ((516, 160), (524, 176), (528, 192), (520, 206), (506, 214), (490, 214)):
        start = math.radians(random.uniform(20, 75))
        big.append(claw_path((x, y), start, start + math.radians(random.uniform(100, 160)), random.uniform(38, 66)))
    claws(big, [12, 9, 6, 3], [8, 6, 4, 2])
    color(FOAM)
    for _ in range(20):
        x, y = random.gauss(560, 30), random.gauss(205, 30)
        p.stroke([(round(x), round(y)), (round(x) + 1, round(y))], size=random.choice((2, 3, 4)))


def phase_b():
    """Depth: a near-black shadow under the curling crest, more medium-blue bands inside."""
    print(p.zoom(200, 330, 230))
    tail = CREST[-26:]
    line(SHADOW, 12, *offset(tail[:-4], 30), wobble=0.4)        # just under the foam band
    line(SHADOW, 9, (404, 206), (440, 210), (480, 220), (505, 222))  # the curl's ceiling
    line(SHADOW, 6, *offset(tail[:-6], 44), wobble=0.4)
    for d, size in ((100, 6), (128, 5), (165, 4)):
        line(MID_BLUE, size, *offset(CREST[6:-12], d), wobble=0.5)


def inside(poly, x, y):
    """Even-odd point-in-polygon test."""
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def phase_b2():
    """Second look at the depth: the shadow came out as hard black bars, one across the claws, and
    the new stripes looped off the wave into the hollow. Fix each locally."""
    print(p.zoom(200, 380, 210))
    body = smooth(*wave.WAVE, closed=True)
    # 1. stripe pieces that left the wave body go back to the hollow's cream
    for d, size in ((100, 6), (128, 5), (165, 4)):
        run = []
        for q in offset(CREST[6:-12], d) + [None]:
            if q and not inside(body, *q):
                run.append(q)
            elif run:
                if len(run) > 1:
                    line(CREAM, size + 5, *run)
                run = []
    # 2. the bar under the lip becomes the lip's blue underside, with a fresh row of claws below it
    line(BLUE, 12, (404, 206), (440, 210), (480, 220), (505, 222))
    under = [(410, 214), (428, 216), (446, 219), (464, 222), (482, 225), (498, 226)]
    claws([claw_path(q, math.radians(random.uniform(75, 100)), math.radians(random.uniform(170, 210)), random.uniform(22, 34)) for q in under],
          [9, 6, 4], [6, 4, 2])
    # 3. the two upper bars go back to wave blue, then the shadow is built as two see-through glazes
    tail = CREST[-26:]
    line(BLUE, 16, *offset(tail[:-4], 30))
    line(MID_BLUE, 9, *offset(tail[:-4], 36))
    line(BLUE, 12, *offset(tail[:-6], 44))
    line(SHADOW, 18, *offset(tail[:-4], 34), opacity=35)
    line(SHADOW, 9, *offset(tail[:-4], 28), opacity=45)
    # 4. a stray rim dot in the hollow
    line(CREAM, 7, (538, 329), (539, 329))


def phase_c():
    """Boats: clean the old traces, thicker curved hulls, crouching rowers inside."""
    print(p.zoom(250, 390, 550))
    # the dotted trace of the first boat's outline, and the old boats with their stick rowers
    line(BLUE, 11, (226, 500), (360, 478), (425, 466))
    for (x0, y0, x1, y1, depth) in ((150, 556, 430, 508, 13), (470, 590, 640, 600, 10)):
        top, hull = boat(x0, y0, x1, y1, depth)
        cover(top + hull, BLUE, 8)
        line(BLUE, 22, *offset(top, -8))  # where the stick rowers stood
    # new hulls: deeper, with a shaded underside and a light rim
    for (x0, y0, x1, y1, depth, n) in ((140, 566, 440, 506, 22, 8), (466, 598, 640, 606, 16, 5)):
        top, hull = boat(x0, y0, x1, y1, depth)
        cover(top + hull, BOAT, 10)
        line("#A88F62", 5, *offset(hull, 4))
        line("#F0E4C6", 3, *top)
        pen_line(top + hull + top[:1], 2)
        # rowers crouched over their oars: a rounded back, a pale head bowed forward
        for i in range(n):
            t = (i + 0.6) / (n + 0.2)
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            line(NAVY, 9, (x + 4, y + 3), (x, y - 4), (x - 5, y - 6))
            line("#E8D9B5", 6, (x - 8, y - 4), (x - 7, y - 4))
            line(FOAM, 3, (x - 9, y - 7), (x - 5, y - 7))


def _hex(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _near_blend(px, palette, tol=34):
    """Whether a pixel is one of the palette colors or an anti-aliased blend of two of them."""
    best = 1e9
    for i, a in enumerate(palette):
        for b in palette[i:]:
            ab = [bb - aa for aa, bb in zip(a, b)]
            n = sum(v * v for v in ab) or 1
            t = max(0.0, min(1.0, sum((pp - aa) * v for pp, aa, v in zip(px, a, ab)) / n))
            best = min(best, sum(abs(pp - (aa + t * v)) for pp, aa, v in zip(px, a, ab)))
    return best <= tol


def repaint_strays(region, keep, c, size=4, tol=34):
    """Pixel-level cleanup: look at the visible canvas, find pixels inside `region(x, y)` whose color
    is not one of `keep` (or a blend of them), chain them into short paths and paint them `c`."""
    import io
    from PIL import Image
    shot = Image.open(io.BytesIO(p.view().data)).convert("RGB")
    scale, ox, oy = p._mapping
    rect, _, _ = p._canvas()
    palette = [_hex(k) for k in keep]
    strays = set()
    for sy in range(0, shot.height, 2):
        for sx in range(0, shot.width, 2):
            x, y = (rect.left + sx - ox) / scale, (rect.top + sy - oy) / scale
            if region(x, y) and not _near_blend(shot.getpixel((sx, sy)), palette, tol):
                strays.add((round(x), round(y)))
    print(f"{len(strays)} stray pixels")
    # chain neighbors (within 4 px) into paths, left to right
    pts = sorted(strays)
    while pts:
        path = [pts.pop(0)]
        while True:
            nxt = min(pts, key=lambda q: (q[0] - path[-1][0]) ** 2 + (q[1] - path[-1][1]) ** 2, default=None)
            if not nxt or (nxt[0] - path[-1][0]) ** 2 + (nxt[1] - path[-1][1]) ** 2 > 16:
                break
            path.append(nxt)
            pts.remove(nxt)
        line(c, size, *(path if len(path) > 1 else path * 2))


def phase_c2():
    """Pixel-level cleanup of what the earlier passes left behind: the first boat's dotted trace and
    old rower specks above the left boat, the first right boat's tan sliver under the front wave."""
    top_a = lambda x: 566 - 60 * (x - 140) / 300  # the new left boat's gunwale
    print(p.zoom(300, 330, 485))
    repaint_strays(lambda x, y: 220 <= x <= 436 and 452 <= y <= top_a(x) - 20, [BLUE, MID_BLUE, LIGHT_BLUE], BLUE)
    print(p.zoom(300, 730, 575))
    repaint_strays(lambda x, y: 648 <= x <= 820 and 566 <= y <= 594, [BLUE, MID_BLUE, LIGHT_BLUE, FOAM, NAVY], BLUE)


def phase_c3():
    """Second look at the cleanup: its search box reached into the hollow, so cream pixels counted as
    strays and a blue block now cuts into the hollow across the face. Restore it locally, then catch
    what the first search missed with a mask that stays inside the wave."""
    body = smooth(*wave.WAVE, closed=True)
    face = smooth(*wave.CURL[3:10])  # the inner face, as the earlier passes drew it
    print(p.zoom(400, 410, 462))
    # 1. the hollow's cream back over the block, outside the wave only
    repaint_strays(lambda x, y: 360 <= x <= 452 and 432 <= y <= 492 and not inside(body, x, y), [CREAM], CREAM, size=5)
    # then the face details the block covered, redrawn from the same geometry, on that stretch only
    span = lambda pts: [q for q in pts if 426 <= q[1] <= 496]
    line("#1C3866", 10, *span(offset(face, 14)))
    lace = span(offset(face, 5))
    for i in range(0, len(lace) - 3, 4):
        line(FOAM, 4, lace[i], lace[i + 2])
    pen_line(span(face), 4)
    # 2. the faint trace above the left boat: a tight color check, inside the wave, near the trace
    print(p.zoom(400, 330, 488))
    trace = lambda x: 500 - 22 * (x - 226) / 134 if x < 360 else 478 - 12 * (x - 360) / 65
    repaint_strays(lambda x, y: 222 <= x <= 428 and abs(y - trace(x)) <= 7 and inside(body, x, y),
                   [BLUE, MID_BLUE, LIGHT_BLUE], BLUE, size=3, tol=10)
    # 3. the lone dot in the sky beside the wave
    print(p.zoom(400, 540, 330))
    repaint_strays(lambda x, y: 520 <= x <= 560 and 312 <= y <= 346, [CREAM], CREAM, size=6)


def phase_d():
    """Sky: a few soft cloud streaks. The mountain: a shaded flank and an irregular snowcap."""
    print(p.zoom(300, 700, 320))
    for y0, x0, x1, c in ((270, 600, 860, "#DDD3BA"), (292, 650, 900, "#F1E9D6"), (330, 560, 780, "#DDD3BA")):
        line(c, 7, *[(x, y0 + 3 * math.sin(x / 40)) for x in range(x0, x1, 20)], wobble=0.6)
    print(p.zoom(400, 616, 440))
    line("#4B5A70", 9, (626, 408), (660, 438), (700, 470))
    line("#4B5A70", 6, (616, 416), (640, 446), (668, 470))
    for x0, y0, x1, y1 in ((598, 430, 594, 440), (611, 424, 609, 437), (624, 432, 625, 443), (640, 428, 645, 438)):
        line(FOAM, 3, (x0, y0), (x1, y1))
    pen_line([(520, 476), (576, 432), (606, 400), (622, 400), (650, 432), (712, 476)], 2)


if __name__ == "__main__":
    phases = sys.argv[1:]  # one or more, run in order
    random.seed(sum(map(ord, "".join(phases))))
    brushlib.W, brushlib.H = W, H
    part = os.path.join(HERE, f"02_great_wave_{''.join(phases)}.gif")
    with recording(part, every=0.6):
        for phase in phases:
            {"A": phase_a, "A2": phase_a2, "B": phase_b, "B2": phase_b2, "C": phase_c, "C2": phase_c2, "C3": phase_c3, "D": phase_d}[phase]()
        print(p.zoom())
    save(os.path.join(HERE, "02_great_wave.png"))
    append_gif(GIF, part)
