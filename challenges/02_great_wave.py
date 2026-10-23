"""Challenge 2: The Great Wave, in the ukiyo-e style of Katsushika Hokusai. Tests curves and shape
boundaries.

Painted in dependency order: a stroke waits until everything it depends on is right.
    P1 ground, sky, clouds, distant sea, the mountain
    P2 silhouettes: the great wave, the boats in their troughs, the waves in front of them
    P3 the great wave's structure: overlapping tongues of water, recesses, streaks
    P4 foam: crest masses, branching claws, spray
    P5 key-block outlines

    uv run challenges/02_great_wave.py preview      simulate every phase in an image first
    uv run challenges/02_great_wave.py P1           then paint phase by phase, looking in between
"""
import math
import os
import random
import sys

import brushlib
from brushlib import canvas, color, cover, line, p, save, smooth, stroke

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1000, 680
GROUND, SKY_TOP, CLOUD = "#E7D9BA", "#A49D89", "#D3C8AD"
PRUSSIAN, DEEP, MID, LIGHT, PALE, FOAM, INK = "#1D3D72", "#0D1F44", "#3566A0", "#7FA8D2", "#BCD3E8", "#F5F1E3", "#16223D"
SEA_FAR, SEA_NEAR = "#7A93AE", "#27497D"
FUJI, FUJI_LIT, SNOW = "#3C4C6C", "#66779A", "#F4F0E2"
HULL, HULL_SHADE, HULL_RIM, ROWER, FACE = "#D8C59C", "#A68B5C", "#EFE3C4", "#22345A", "#E9DAB6"


# ---------------------------------------------------------------- geometry helpers

def offset(chain, d):
    """A polyline moved sideways by d (positive = right of the direction of travel). d may be a
    function of the position t in 0..1 along the chain, for bands that taper."""
    out = []
    for i, (x, y) in enumerate(chain):
        (ax, ay), (bx, by) = chain[max(0, i - 1)], chain[min(len(chain) - 1, i + 1)]
        length = math.hypot(bx - ax, by - ay) or 1
        dd = d(i / max(1, len(chain) - 1)) if callable(d) else d
        out.append((x - (by - ay) / length * dd, y + (bx - ax) / length * dd))
    return out


def inside(poly, x, y):
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def tapered(pts, c, sizes, opacity=100):
    """A mark drawn as overlapping pieces that change size along its length (thin ends, full body)."""
    n = len(sizes)
    for j, s in enumerate(sizes):
        piece = pts[j * (len(pts) - 1) // n: (j + 1) * (len(pts) - 1) // n + 1]
        if len(piece) > 1:
            line(c, max(1, round(s)), *piece, opacity=opacity)


def finger(base, ang, bend, length, steps=7):
    """A curving foam finger: leaves `base` heading `ang`, turning by `bend` radians by the tip."""
    pts = [base]
    for i in range(1, steps + 1):
        a = ang + bend * (i / steps) ** 1.6
        x, y = pts[-1]
        pts.append((x + math.cos(a) * length / steps, y + math.sin(a) * length / steps))
    return pts


def claw_tree(base, ang, bend, length, width, depth, out):
    """A claw: a finger curling with the wave, splitting into a few short claws near its tip."""
    path = finger(base, ang, bend, length)
    out.append((path, width))
    if depth == 0:
        return
    for _ in range(random.choice((1, 2, 2, 3))):
        k = random.randint(len(path) * 2 // 3, len(path) - 2)
        a = math.atan2(path[k + 1][1] - path[k][1], path[k + 1][0] - path[k][0])
        side = random.choice((-1, 1))
        claw_tree(path[k], a + side * random.uniform(0.3, 0.6), bend * random.uniform(0.7, 1.2),
                  length * random.uniform(0.25, 0.42), width * 0.55, depth - 1, out)


def paint_claws(claws, rim=PALE, body=FOAM):
    """All rims first, then all foam on top: two color changes for any number of claws."""
    for path, w in claws:
        tapered(path, rim, [w + 3, w * 0.75 + 3, w * 0.45 + 2, w * 0.25 + 2])
    for path, w in claws:
        tapered(path, body, [w, w * 0.75, w * 0.45, w * 0.22])


def boat(x0, y0, x1, y1, depth):
    """A long boat: gunwale from (x0, y0) to (x1, y1) with an upswept bow, hull curving below."""
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    top = smooth((x0 - 6, y0 - 10), (x0 + 20, y0), (mx, my + 2), (x1, y1))
    hull = smooth((x1 - 8, y1 + depth * 0.5), (mx, my + depth), (x0 + 22, y0 + depth * 0.6), (x0 - 4, y0 - 6))
    return top, top + hull


# ---------------------------------------------------------------- the composition

CREST = smooth((-30, 400), (30, 300), (100, 222), (190, 165), (290, 130), (385, 120), (465, 136),
               (530, 168), (572, 210), (586, 240))
UNDER = smooth((586, 240), (566, 260), (528, 260), (488, 248), (452, 250))       # the lip's underside
INNER = smooth((452, 250), (418, 274), (392, 318), (384, 380), (400, 446), (440, 508), (500, 562),
               (580, 610), (690, 650), (820, 672), (1040, 690))                    # the curl's inner face
MAIN = [(-40, H + 40)] + CREST + UNDER[1:] + INNER[1:] + [(W + 40, H + 40)]
ARC = [q for q in CREST if q[0] < 540]                                             # the crest before it curls
# Water masses in front of the great wave, each with its own crest (top edges only).
SWELL_TOP = smooth((-40, 512), (40, 482), (120, 470), (180, 490), (226, 528))     # a swell on the lower slope
FRONT_TOP = smooth((150, H + 40), (205, 630), (250, 592), (286, 566), (316, 552), (346, 560), (384, 590), (430, 640), (470, H + 40))
RIGHT_TOP = smooth((610, H + 40), (646, 624), (705, 578), (780, 538), (860, 516), (930, 514), (1040, 530))
FUJI_SHAPE = [(548, 526), (596, 494), (636, 466), (656, 450), (670, 450), (694, 468), (738, 500), (776, 526)]
SNOW_CAP = [(632, 469), (656, 450), (670, 450), (697, 470), (688, 476), (681, 466), (673, 480),
            (664, 466), (655, 482), (647, 467), (639, 476)]
BOAT_1 = boat(24, 560, 330, 506, 20)
BOAT_2 = boat(468, 550, 646, 604, 16)
BOAT_3 = boat(696, 606, 912, 572, 16)
FRONT_BLUE, SWELL_BLUE = "#26508C", "#22487F"
# The great wave's tongues: (start, end along the crest arc, depth from the crest, width, color).
# Staggered starts and ends make overlapping masses, each breaking at its own tip.
TONGUES = [(0.18, 0.92, 42, 40, MID), (0.05, 0.74, 100, 48, "#2D5C98"), (0.22, 0.62, 160, 38, MID),
           (0.0, 0.48, 222, 50, "#2A5791"), (0.12, 0.34, 286, 34, MID)]


def inward(chain, d):
    """Offset a chain of the great wave's outline toward the inside of the wave."""
    probe = offset(chain, d(0.5) if callable(d) else d)[len(chain) // 2]
    sign = 1 if inside(MAIN, *probe) else -1
    return offset(chain, (lambda t: sign * d(t)) if callable(d) else sign * d)


def tongue(t0, t1, depth, width):
    """A crescent following the crest: thickest in the middle, tapering to points at both ends."""
    sub = ARC[int(t0 * (len(ARC) - 1)): int(t1 * (len(ARC) - 1)) + 1]
    hw = lambda t: width / 2 * math.sin(math.pi * t) ** 0.6
    top = inward(sub, lambda t: depth - hw(t))
    bottom = inward(sub, lambda t: depth + hw(t))
    keep = lambda pts: [q for q in pts if inside(MAIN, *q)]
    return keep(top), keep(bottom)


def mass(top, color_, size, angle):
    """A water mass in front of the great wave: its top edge, closed off below the canvas."""
    cover(top + [(top[-1][0], H + 40), (top[0][0], H + 40)], color_, size, angle=angle, smooth_poly=False)


def hull(b):
    top, poly = b
    cover(poly, HULL, 10)
    line(HULL_SHADE, 5, *offset(poly[len(top):], -3))
    line(HULL_RIM, 3, *top)


# ---------------------------------------------------------------- phases

def p1():
    """Ground, sky, clouds, distant sea, the mountain."""
    for y in range(-40, 120, 8):  # many faint wide glazes, overlapping most at the top: a smooth darkening
        line(SKY_TOP, 70, (-40, y), (W + 40, y), opacity=5)
    for y, x0, x1, w in ((468, 470, 1040, 20), (492, 540, 1040, 12), (300, 650, 1040, 12), (330, 720, 1000, 8)):
        line(CLOUD, w, *[(x, y + 4 * math.sin(x / 60)) for x in range(x0, x1, 40)], opacity=55)
    cover([(-40, 524), (W + 40, 524), (W + 40, H + 40), (-40, H + 40)], SEA_NEAR, 50, smooth_poly=False)
    cover([(-40, 522), (W + 40, 522), (W + 40, 556), (-40, 556)], SEA_FAR, 16, smooth_poly=False)
    for _ in range(26):  # small far-off wavelets
        x, y = random.uniform(420, 1000), random.uniform(530, 552)
        line(PALE, 2, (x, y), (x + random.uniform(6, 14), y - 1))
    cover(FUJI_SHAPE, FUJI, 14, smooth_poly=False)
    cover([(548, 526), (596, 494), (636, 466), (656, 452), (650, 490), (620, 526)], FUJI_LIT, 10, smooth_poly=False)
    cover(SNOW_CAP, SNOW, 6, smooth_poly=False)


def p2():
    """Silhouettes, back to front: the great wave, a swell on its slope, boats riding the water, and
    the waves in front of them, each a lighter blue so the masses separate."""
    cover(MAIN, PRUSSIAN, 60, angle=-35, smooth_poly=False)
    mass(SWELL_TOP, SWELL_BLUE, 36, -10)
    for b in (BOAT_1, BOAT_2):
        hull(b)
    mass(RIGHT_TOP, FRONT_BLUE, 40, -15)
    hull(BOAT_3)
    mass(FRONT_TOP, FRONT_BLUE, 34, -10)
    for top, _ in (BOAT_1, BOAT_2, BOAT_3):  # rowers bowed over their oars, no two alike
        n = max(5, int(math.hypot(top[-1][0] - top[0][0], top[-1][1] - top[0][1]) / 30))
        for i in range(n):
            x, y = top[int((i + 0.7) / (n + 0.4) * (len(top) - 1))]
            lean = random.uniform(-0.6, 0.6)
            line(ROWER, random.choice((8, 9, 10)), (x + 3, y + 2), (x - 1 + lean, y - 6), (x - 6 + lean, y - 8))
            line(FACE, 5, (x - 9 + lean, y - 6), (x - 8 + lean, y - 6))


def p3():
    """Structure: the great wave's overlapping tongues (each with a dark seam below and a streak),
    shadows cast by each water mass on the one behind it, a deep recess inside the curl."""
    for t0, t1, depth, width, c in TONGUES:
        top, bottom = tongue(t0, t1, depth, width)
        if len(top) > 4 and len(bottom) > 4:
            cover(top + list(reversed(bottom)), c, 18, angle=-35, smooth_poly=False)
            tapered(bottom, DEEP, [1, 4, 5, 3])                     # the seam where it overlaps the next
            mid = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(top, bottom)]
            k = random.randint(len(mid) // 5, len(mid) // 3)
            tapered(mid[k:], LIGHT, [1, 2, 3, 2, 1])                # a streak running with the water
    for top in (SWELL_TOP, FRONT_TOP[1:-1], RIGHT_TOP[1:-1]):      # each mass shades the water behind it
        shade = [q for q in offset(top, -9) if inside(MAIN, *q) or q[1] > 528]  # on water only, never sky
        if len(shade) > 2:
            line(DEEP, 14, *shade, opacity=45)
        tapered(offset(top, 14), LIGHT, [1, 2, 3, 2, 1])
        tapered(offset(top, 30), LIGHT, [1, 2, 2, 1])
    line(DEEP, 26, *inward(INNER[:26], 14), opacity=45)            # the curl's inner wall, in shadow
    line(DEEP, 18, *UNDER, opacity=55)
    line(DEEP, 16, *inward([q for q in CREST if q[0] > 470], 40), opacity=40)  # under the breaking lip


def p4():
    """Foam: an uneven crest mass widening toward the lip, branching claws that reach forward and
    down over the trough, foam breaking at each tongue's tip, crests on the front waves, spray."""
    jag = [random.uniform(0, 9) for _ in CREST]
    jag = [(jag[max(0, i - 1)] + jag[i] + jag[min(len(jag) - 1, i + 1)]) / 3 for i in range(len(jag))]
    # stops short of the tip: carried to the tip, the band's two edges crossed into a foam 'beak'
    outer = [(x, y - j) for (x, y), j in zip(CREST[3:-4], jag[3:-4])]
    inner = inward(CREST[3:-4], lambda t: 10 + 30 * t ** 1.6)
    cover(outer + list(reversed(inner)), FOAM, 14, smooth_poly=False)
    tapered(inner, PALE, [1, 3, 4, 3])
    claws = []
    tangent = lambda chain, i: math.atan2(chain[min(i + 1, len(chain) - 1)][1] - chain[max(i - 1, 0)][1],
                                          chain[min(i + 1, len(chain) - 1)][0] - chain[max(i - 1, 0)][0])
    for i in range(5, len(CREST) - 22, random.choice((3, 4))):  # small claws riding the crest, leaning forward
        claw_tree((CREST[i][0], CREST[i][1] - jag[i]), tangent(CREST, i) - random.uniform(0.3, 0.8),
                  random.uniform(1.0, 1.8), random.uniform(12, 28), random.uniform(3.5, 6), 1, claws)
    # the great claws: a dozen fingers from the lip, each turning on with the curl's rotation
    # (clockwise here) and splitting into a few short claws near its tip
    lip = CREST[-22:] + UNDER[1:]
    for i in range(0, len(lip), 3):
        claw_tree(lip[i], tangent(lip, i) + random.uniform(0.15, 0.6), random.uniform(1.0, 1.9),
                  random.uniform(48, 96), random.uniform(8, 13), 1, claws)
    for t0, t1, depth, width, c in TONGUES:  # each tongue breaks into foam at its tip, irregularly
        top, _ = tongue(t0, t1, depth, width)
        tip = top[-max(4, len(top) // 4):]
        for q in random.sample(tip, k=min(len(tip), random.randint(2, 3))):
            a = math.atan2(top[-1][1] - top[0][1], top[-1][0] - top[0][0])
            claw_tree(q, a - random.uniform(0.2, 1.0), random.uniform(0.8, 1.8), random.uniform(8, 26),
                      random.uniform(2.5, 5), random.choice((0, 1)), claws)
    paint_claws(claws)
    small = []
    for top, peak in ((SWELL_TOP[1:], 120), (FRONT_TOP[1:-1], 320), (RIGHT_TOP[1:-1], -1)):
        cap = [(x, y - random.uniform(0, 3)) for x, y in top]
        cover(cap + list(reversed(offset(top, 8))), FOAM, 8, smooth_poly=False)
        for i in range(1, len(top) - 1, 3):
            x, y = top[i]
            spill = math.pi * (0.8 if x < peak else 0.2) if peak > 0 else math.pi * 0.9
            claw_tree((x, y), spill + random.uniform(-0.4, 0.4), random.choice((-1, 1)) * random.uniform(0.8, 1.6),
                      random.uniform(10, 24), random.uniform(3, 5), 1, small)
    paint_claws(small)
    color(FOAM)
    for path, w in claws:  # droplets thrown beyond the bigger claw tips
        if w > 6:
            (x0, y0), (x1, y1) = path[-2], path[-1]
            a = math.atan2(y1 - y0, x1 - x0)
            for _ in range(random.randint(1, 3)):
                r = random.uniform(6, 34)
                x, y = x1 + math.cos(a) * r + random.gauss(0, 5), y1 + math.sin(a) * r + random.gauss(0, 5)
                stroke([(x, y), (x + 1, y)], random.choice((2, 3, 3, 4, 5)))
    for _ in range(45):  # finer spray drifting over the trough
        x, y = random.gauss(650, 80), random.gauss(330, 70)
        if 0 < x < W and 170 < y < 470 and not inside(MAIN, x, y):
            stroke([(x, y), (x + 1, y)], random.choice((2, 2, 3)))


def p5():
    """Key-block outlines, thin: blue on the water, dark on the mountain and the boats."""
    def ink(pts, c, size):
        color(c)
        stroke(pts, size, brush="Calligraphy pen")
    ink(INNER[2:30], DEEP, 3)
    ink(FUJI_SHAPE, INK, 2)
    for top, poly in (BOAT_1, BOAT_2, BOAT_3):
        ink(poly + poly[:1], INK, 2)


def near(c, tol=12):
    rgb = tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    return lambda px: sum(abs(a - b) for a, b in zip(px, rgb)) <= tol


def p2b():
    """Correction after looking at P2: off-canvas brush points clamped onto the bottom edge pulled
    the front waves' rings sideways into three blocky 'feet', and the swell ended in a vertical
    cut. Repaint only the wrong-colored pixels, each with the color that belongs behind it."""
    front = FRONT_TOP
    right = RIGHT_TOP + [(W + 40, H + 40)]
    swell = SWELL_TOP + [(226, H + 40), (-40, H + 40)]
    behind = lambda x, y: SWELL_BLUE if inside(swell, x, y) else PRUSSIAN if inside(MAIN, x, y) else SEA_NEAR
    for cx, cy, box, shape in ((160, 650, (110, 630, 205, 680), front), (450, 640, (395, 596, 505, 680), front),
                               (615, 650, (565, 616, 665, 680), right)):
        print(p.zoom(300, cx, cy))
        for c in (SWELL_BLUE, PRUSSIAN, SEA_NEAR):
            brushlib.repaint(lambda x, y, b=box, s=shape, c=c: b[0] <= x <= b[2] and b[1] <= y <= b[3]
                             and not inside(s, x, y) and behind(x, y) == c, near(FRONT_BLUE), c)
    # the swell slopes away under the front wave instead of dropping straight down
    print(p.zoom(300, 262, 600))
    slope = [(226, 528), (310, H + 40), (226, H + 40)]
    brushlib.repaint(lambda x, y: inside(slope, x, y), near(PRUSSIAN), SWELL_BLUE)


def p3b():
    """Correction after looking at P3: the shadow under the lip was laid on its outline, so half of it
    spilled into the hollow's sky; the right wave's cast shadow smeared the pale distant sea.
    Repaint just those pixels with what belongs there."""
    rgb = lambda c: tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    print(p.zoom(300, 515, 250))
    brushlib.repaint(lambda x, y: 425 <= x <= 610 and 222 <= y <= 290 and not inside(MAIN, x, y),
                     lambda px: not near(GROUND, 10)(px), GROUND)
    print(p.zoom(300, 740, 530))
    far = rgb(SEA_FAR)
    brushlib.repaint(lambda x, y: 640 <= x <= 820 and 524 <= y <= 556 and not inside(MAIN, x, y)
                     and not inside(RIGHT_TOP + [(W + 40, H + 40)], x, y) and not inside(FUJI_SHAPE, x, y),
                     lambda px: sum(px) < sum(far) - 18 and not near(PALE, 40)(px), SEA_FAR)


def p4b():
    """Correction (the user spotted it): a round bump at the lip's tip. The silhouette's brush rings
    overshot the sharp corner where the crest folds into the lip's underside, and the foam band ran
    past the tip in a beak. Paint the sky back over just the dark and foam pixels outside the wave's
    true outline; the claw rims there are another color and stay."""
    print(p.zoom(400, 568, 215))
    tip = lambda x, y: 515 <= x <= 625 and 150 <= y <= 275 and not inside(MAIN, x, y)
    brushlib.repaint(tip, lambda px: near(PRUSSIAN, 24)(px) or near(DEEP, 24)(px) or near(MID, 20)(px), GROUND)
    brushlib.repaint(tip, near(FOAM, 14), GROUND)


def runs(pts, keep):
    """Split a polyline into its stretches whose points pass keep(x, y)."""
    out, cur = [], []
    for q in pts:
        if keep(*q):
            cur.append(q)
        elif cur:
            out.append(cur)
            cur = []
    out.append(cur)
    return [r for r in out if len(r) > 2]


def paint_grouped(items):
    """Paint (color, size, points, opacity) items grouped by color, in each color's first-seen order:
    one color change per color instead of one per stroke."""
    order = list(dict.fromkeys(c for c, *_ in items))
    for c in order:
        for c2, size, pts, op in items:
            if c2 == c:
                line(c, max(1, round(size)), *pts, opacity=op)


def p3x():
    """Water, not silhouettes: depth glazes, hundreds of flow lines following each mass's curve,
    broken edges with bulges and foam lace, lace netting on the faces, wavelets on the troughs."""
    swell = SWELL_TOP + [(310, H + 40), (-40, H + 40)]
    front = FRONT_TOP
    right = RIGHT_TOP + [(W + 40, H + 40)]
    boats = [offset(top, -22) + poly[len(top):] for top, poly in (BOAT_1, BOAT_2, BOAT_3)]
    clear = lambda x, y: not any(inside(b, x, y) for b in boats)
    in_main = lambda x, y: inside(MAIN, x, y) and not inside(swell, x, y) and not inside(front, x, y) \
        and not inside(right, x, y) and clear(x, y)
    masses = [  # (top edge chain, mass color, region test)
        (SWELL_TOP, SWELL_BLUE, lambda x, y: inside(swell, x, y) and not inside(front, x, y) and clear(x, y)),
        (FRONT_TOP[1:-1], FRONT_BLUE, lambda x, y: inside(front, x, y) and clear(x, y)),
        (RIGHT_TOP[1:-1], FRONT_BLUE, lambda x, y: inside(right, x, y) and clear(x, y)),
    ]
    sub = lambda chain, t0, t1: chain[int(t0 * (len(chain) - 1)): max(int(t0 * (len(chain) - 1)) + 3, int(t1 * (len(chain) - 1)) + 1)]

    def streak(chain, keep, palette, width, op):
        items = []
        for r in runs(chain, keep):
            w, c = random.choice(width), random.choice(palette)
            for k, s in enumerate((max(1, w - 1), w, max(1, w - 1))):  # thin ends
                piece = r[k * (len(r) - 1) // 3: (k + 1) * (len(r) - 1) // 3 + 1]
                if len(piece) > 1:
                    items.append((c, s, piece, op))
        return items

    glazes, streaks, edges, lace = [], [], [], []
    # depth: the great wave darkens away from its crest; translucent light just under the foam
    for d in range(50, 430, 28):
        start = 0 if d < 130 else 10  # deep offsets of the crest's off-canvas start flatten into bars
        for r in runs(inward(ARC[start:], d), in_main):
            glazes.append((DEEP, 32, r, min(14, 3 + d // 45)))
    for d, op in ((22, 22), (40, 12)):
        for r in runs(inward(ARC, d), in_main):
            glazes.append(("#6F9FD2", 22, r, op))
    for top, _, keep in masses:
        for d in range(26, 180, 24):
            for r in runs(offset(top, d), keep):
                glazes.append((DEEP, 26, r, min(14, 3 + d // 30)))
        for r in runs(offset(top, 9), keep):
            glazes.append(("#6F9FD2", 16, r, 24))
    # flow lines: many partial streaks following each mass's curve, lighter near the crest
    near_pal, mid_pal, deep_pal = [PALE, LIGHT, "#5B8BC4"], [LIGHT, MID, "#4677B3", "#163566"], ["#2B5A96", "#163566", DEEP, MID]
    for _ in range(150):
        d = random.uniform(14, 400)
        t0 = random.uniform(0, 0.88)
        chain = inward(sub(ARC, t0, t0 + random.uniform(0.1, 0.42)), d + random.uniform(-4, 4))
        pal = near_pal if d < 70 else mid_pal if d < 190 else deep_pal
        streaks += streak(chain, in_main, pal, (1, 2, 2, 3, 4), random.choice((70, 85, 100)))
    for _ in range(45):  # down the curl's inner wall
        t0 = random.uniform(0, 0.7)
        chain = inward(sub(INNER[:34], t0, t0 + random.uniform(0.15, 0.45)), random.uniform(5, 70))
        streaks += streak(chain, in_main, [MID, "#163566", LIGHT, "#4677B3"], (1, 2, 3), random.choice((70, 100)))
    for top, _, keep in masses:
        for _ in range(45 if top is not SWELL_TOP else 30):
            t0 = random.uniform(0, 0.85)
            chain = offset(sub(top, t0, t0 + random.uniform(0.12, 0.5)), random.uniform(6, 150))
            streaks += streak(chain, keep, [LIGHT, PALE, MID, "#3F70AC", "#173A6F"], (1, 2, 2, 3), random.choice((70, 100)))
    # broken edges: the water bulges past each outline here and there, and foam laces along it
    for chain, c, sign in ((SWELL_TOP, SWELL_BLUE, 1), (FRONT_TOP[1:-1], FRONT_BLUE, 1), (RIGHT_TOP[1:-1], FRONT_BLUE, 1),
                           (INNER[2:30], PRUSSIAN, -1), (CREST[:8], PRUSSIAN, 1)):
        inner_side, outer_side = offset(chain, 3 * sign), offset(chain, -random.uniform(3, 6) * sign)
        bulge = (0.3, 4) if c is PRUSSIAN else (0.65, 7)  # the curl's face: fewer, shorter, so no beads
        for i in range(0, len(chain), 2):
            if random.random() < bulge[0] and clear(*chain[i]):
                o = offset(chain, -random.uniform(2, bulge[1]) * sign)[i]
                edges.append((c, random.choice((4, 5, 6)), [inner_side[i], o], 100))
        for i in range(1, len(chain), 3):
            if random.random() < 0.55 and clear(*chain[i]):
                x, y = outer_side[i]
                a = random.uniform(0, 2 * math.pi)
                lace.append((random.choice((FOAM, FOAM, PALE)), random.choice((2, 3, 3, 4)),
                             [(x, y), (x + math.cos(a) * random.uniform(2, 6), y + math.sin(a) * random.uniform(2, 6))], 100))
    # foam lace netting across the faces, near each crest: chains of small droplets and hooks
    for top, _, keep in masses + [(ARC, PRUSSIAN, in_main)]:
        for d in ((14, 24, 36, 50) if top is not ARC else (300, 330, 360)):
            t0 = random.uniform(0, 0.5)
            chain = (inward if top is ARC else offset)(sub(top, t0, t0 + random.uniform(0.25, 0.5)), d)
            for i in range(0, len(chain), random.choice((2, 3))):
                x, y = chain[i]
                if keep(x, y) and random.random() < 0.7:
                    a = random.uniform(0, 2 * math.pi)
                    lace.append((FOAM, random.choice((2, 2, 3)), [(x, y), (x + math.cos(a) * 3, y + math.sin(a) * 3)], 100))
    # wavelets curling on the open water between the masses
    for _ in range(40):
        x, y = random.uniform(440, 690), random.uniform(560, 660)
        if not inside(MAIN, x, y) and not inside(right, x, y) and clear(x, y):
            lace.append((random.choice((PALE, LIGHT)), 2, [(x, y), (x + 5, y - 3), (x + 10, y - 1), (x + 12, y + 2)], 100))
    paint_grouped(glazes)
    paint_grouped(streaks)
    paint_grouped(edges)
    paint_grouped(lace)


PHASES = {"P1": p1, "P2": p2, "P2B": p2b, "P3": p3, "P3B": p3b, "P3X": p3x, "P4": p4, "P4B": p4b, "P5": p5}
PREVIEW_ORDER = ["P1", "P2", "P3", "P3X", "P4", "P5"]  # the correction phases need the real canvas

if __name__ == "__main__":
    args = sys.argv[1:]
    random.seed(2)
    if args == ["preview"]:
        import tempfile
        out = os.environ.get("PREVIEW_DIR", tempfile.gettempdir())
        canvas(W, H, background=GROUND, preview=True)
        for name in PREVIEW_ORDER:
            phase = PHASES[name]
            random.seed(sum(map(ord, name)))
            phase()
            brushlib.preview_image().save(os.path.join(out, f"great_wave_preview_{name}.png"))
        print("previews saved in", out)
    else:
        from record import append_gif, recording
        gif = os.path.join(HERE, "02_great_wave.gif")
        part = os.path.join(HERE, f"02_great_wave_{''.join(args)}.gif")
        brushlib.W, brushlib.H = W, H
        with recording(part if "P1" not in args else gif, every=0.6):
            for name in args:
                random.seed(sum(map(ord, name)))
                if name == "P1":
                    canvas(W, H, background=GROUND)
                PHASES[name]()
            print(p.zoom())
        save(os.path.join(HERE, "02_great_wave.png"))
        if "P1" not in args:
            append_gif(gif, part)
