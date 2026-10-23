"""Challenge 2, correction pass: fixes the first pass's mistakes on the same canvas, with the
brush, the way a painter would. No new canvas, no fills: each mistake is painted over locally.

Mistakes fixed (from looking at the first pass):
- the gray sky bands' ends were rounded inside the canvas
- the wave outline ran on past the curl, cutting a dark diagonal through the front wave
- stripes looped at the tight curl and dangled into the hollow
- a heavy near-black arc sat inside the curl
- the foam "claws" pointed up into the sky like teeth instead of reaching over the lip
- the left boat poked out of the wave into the hollow, and rowers floated above the boats
- the wave body was one flat expanse of blue
"""
import math
import os
import random

from PIL import Image

import brushlib
from brushlib import color, cover, line, p, save, smooth
from record import recording
from importlib import import_module

wave = import_module("02_great_wave")
HERE, W, H = wave.HERE, wave.W, wave.H
CREST, CURL, offset = wave.CREST, wave.CURL, wave.offset
CREAM, SKY_MID, SKY_TOP = wave.CREAM, wave.SKY_MID, wave.SKY_TOP
NAVY, BLUE, MID_BLUE, LIGHT_BLUE, FOAM, BOAT = wave.NAVY, wave.BLUE, wave.MID_BLUE, wave.LIGHT_BLUE, wave.FOAM, wave.BOAT
DEEP = "#1C3866"
FACE = CURL[3:]  # from the top of the hollow down the inner face and out to the right
GIF, FIX_GIF = os.path.join(HERE, "02_great_wave.gif"), os.path.join(HERE, "02_great_wave_fixes.gif")


def pen_line(pts, size, closed=False):
    color(NAVY)
    path = pts + pts[:1] if closed else pts
    p.stroke([(min(W - 1, max(0, round(x))), min(H - 1, max(0, round(y)))) for x, y in path],
             size=size, brush="Calligraphy pen")


def boat(x0, y0, x1, y1, depth):
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    return smooth((x0, y0), (mx, my - 3), (x1, y1)) + smooth((x1 - 4, y1 + depth * 0.6), (mx, my + depth), (x0 + 6, y0 + depth * 0.6))


def rowers(x0, y0, x1, y1, n):
    """Crouched rowers sitting on the gunwale: a short leaning body and a round head."""
    for i in range(n):
        t = (i + 0.5) / n
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        line(NAVY, 7, (x, y - 1), (x - 5, y - 11))
        line(NAVY, 8, (x - 6, y - 14), (x - 5, y - 14))


def claws(chain, n, length, direction):
    """Hooked foam fingers reaching in `direction` and curling back, with a light blue rim."""
    tips = []
    for i in range(n):
        x, y = chain[int(i * (len(chain) - 1) / max(1, n - 1))]
        reach = length * random.uniform(0.75, 1.1)
        tip = (x + math.cos(direction) * reach, y + math.sin(direction) * reach)
        hook = (tip[0] + math.cos(direction + 2.2) * reach * 0.4, tip[1] + math.sin(direction + 2.2) * reach * 0.4)
        tips.append(((x, y), tip, hook))
    for pts in tips:
        line(LIGHT_BLUE, 9, *pts)
    for pts in tips:
        line(FOAM, 5, *pts)


def sky_color_at(y, x):
    """Which sky band a point sits in, following the bands' lower edges."""
    top_edge = 62 - 12 * (x / W)
    mid_edge = 106 + 8 * math.sin(math.pi * x / W)
    return SKY_TOP if y < top_edge else SKY_MID if y < mid_edge else CREAM


# Work on the open canvas: no new_canvas.
brushlib.W, brushlib.H = W, H
random.seed(57)
with recording(FIX_GIF, every=0.6):
    # 1. square off the sky bands' rounded ends at both sides
    for x0, x1 in ((-60, 70), (830, W + 60)):
        cover([(x0, 40), (x1, 40), (x1, 104), (x0, 104)], SKY_MID, 24, smooth_poly=False)
        cover([(x0, -40), (x1, -40), (x1, 56), (x0, 58)], SKY_TOP, 24, smooth_poly=False)

    # 2. the foam teeth above the crest: paint the sky back over them, band by band
    outside = offset(CREST[6:-2], -18)
    runs, run = [], []
    for q in outside:
        c = sky_color_at(q[1], q[0])
        if run and run[0] != c:
            runs.append(run)
            run = []
        run = run or [c]
        run.append(q)
    runs.append(run)
    for c, *pts in runs:
        if len(pts) > 1:
            line(c, 26, *pts)

    # 3. the old boats and floating rowers go under blue (the hollow is repainted right after,
    #    which takes back the left boat's bow where it poked out of the wave)
    cover(wave.BOAT_A, BLUE, 10, smooth_poly=False)
    cover(wave.BOAT_B, BLUE, 8, smooth_poly=False)
    for x in range(250, 490, 34):
        line(BLUE, 14, (x, 500 - (x - 226) * 0.18 - 6), (x + 1, 500 - (x - 226) * 0.18 - 6))
    for x in range(630, 790, 32):
        line(BLUE, 13, (x, 568), (x + 1, 568))
    # the stray outline that ran on past the face across the front wave
    line(BLUE, 10, (620, 567), (760, 600), (W + 20, 608))

    # 4. the hollow under the curl: paint the sky back, which removes the dark arc and the
    #    dangling stripe ends
    hollow = smooth((404, 202), (356, 236), (328, 292), (336, 360), (384, 428), (470, 494), (512, 470), (516, 300), (500, 224))
    cover(hollow, CREAM, 26)

    # 5. life in the body: a deeper band inside the face, stripes down the left side, foam lace
    line(DEEP, 10, *offset(smooth(*FACE[:7]), 14))
    for d in (60, 120, 190):
        line(MID_BLUE, 5, *offset(smooth((-10, 600), (20, 470), (60, 380)), d))
    lace = offset(smooth(*FACE[:7]), 5)
    for i in range(0, len(lace) - 3, 4):
        line(FOAM, 4, lace[i], lace[i + 2])

    # 6. claws that reach forward and down over the hollow, small fingers along the crest
    claws(CREST[-14:], 12, 30, math.radians(70))
    claws(CREST[len(CREST) // 3:-14], 14, 16, math.radians(-30))

    # 7. the front wave's foam where the stray line crossed it
    front = wave.FRONT_CREST
    cover(front + list(reversed(offset(front, 12))), FOAM, 8, smooth_poly=False)

    # 8. new boats riding inside the troughs, with seated rowers
    boat_a, boat_b = boat(150, 556, 430, 508, 13), boat(470, 590, 640, 600, 10)
    cover(boat_a, BOAT, 8)
    cover(boat_b, BOAT, 6)
    rowers(170, 552, 420, 507, 7)
    rowers(490, 591, 630, 600, 4)

    # 9. redraw the key-block outlines that the corrections touched
    pen_line(CREST + CURL[:3] + [(400, 196)] + smooth(*FACE[:9]), 4)
    pen_line(front, 3)
    pen_line(boat_a, 2, closed=True)
    pen_line(boat_b, 2, closed=True)

    # 10. second look: the old boats' pen outlines and the end of the stray line still showed
    # Clip segments at the face rather than dropping points, or the pieces that cross it stay.
    second_look = [
        [(226, 500), (360, 478), (425, 466)],              # old left boat, top edge up to the face
        [(226, 500), (232, 510), (362, 492), (425, 479)],  # and its hull
        wave.BOAT_B + wave.BOAT_B[:1],                     # old right boat, all of it
        [(600, 560), (760, 598), (W + 20, 606)],
    ]
    for pts in second_look:
        line(BLUE, 7, *pts)
    pen_line(boat_b, 2, closed=True)

save(os.path.join(HERE, "02_great_wave.png"))

# One GIF of the whole story: the first pass, then the corrections.
frames = []
for path in (GIF, FIX_GIF):
    with Image.open(path) as g:  # closed afterwards, so the temporary GIF can be deleted
        for i in range(g.n_frames):
            g.seek(i)
            if path == FIX_GIF or i % 2 == 0 or i == g.n_frames - 1:  # first pass at double speed
                frames.append(g.convert("RGB").resize((800, round(g.height * 800 / g.width))).quantize(colors=160, method=Image.Quantize.MEDIANCUT))
durations = [70] * len(frames)
durations[-1] = 2500
frames[0].save(GIF, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
os.remove(FIX_GIF)
print(f"Saved {GIF} ({len(frames)} frames, first pass then corrections)")
