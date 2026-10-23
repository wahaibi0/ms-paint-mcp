"""Challenge 2: a great wave in the ukiyo-e style of Katsushika Hokusai. Tests curves and shape
boundaries: big curved areas with clean edges, stripes that follow a curve, hooked foam.

This is the first pass as painted. Its mistakes were then corrected on the same canvas with the
brush by 02_great_wave_fixes.py, which imports the shapes defined here."""
import math
import os
import random

from brushlib import canvas, color, cover, line, save, smooth, stroke
from record import recording

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 900, 620
CREAM, SKY_MID, SKY_TOP = "#E9DEC4", "#D3CBB4", "#B7B09D"
NAVY, BLUE, MID_BLUE, LIGHT_BLUE = "#18284A", "#24467E", "#3A68A3", "#7FA3C9"
FOAM, FUJI, BOAT = "#F5F1E4", "#5E6F86", "#D9C49B"


def offset(chain, d):
    """A polyline moved sideways by d (positive = right of the direction of travel)."""
    out = []
    for i, (x, y) in enumerate(chain):
        (ax, ay), (bx, by) = chain[max(0, i - 1)], chain[min(len(chain) - 1, i + 1)]
        length = math.hypot(bx - ax, by - ay) or 1
        out.append((x - (by - ay) / length * d, y + (bx - ax) / length * d))
    return out


# The big wave's outer contour, bottom-left, up over the crest, down into the curl, then along
# the inner face and out to the right. The crest part (CREST) carries the foam.
CREST = smooth((40, 330), (110, 240), (200, 160), (300, 110), (400, 104), (480, 132), (520, 178))
CURL = [(505, 214), (470, 206), (440, 192), (400, 196), (352, 232), (322, 290), (330, 360),
        (380, 430), (470, 500), (600, 560), (760, 598), (W + 40, 606)]
WAVE = [(-40, H + 40), (-40, 420)] + CREST + CURL + [(W + 40, H + 40)]
FRONT_WAVE = [(590, H + 40), (630, 566), (700, 522), (760, 508), (822, 522), (880, 560), (W + 40, 585), (W + 40, H + 40)]
FUJI_SHAPE = [(520, 476), (576, 432), (606, 400), (622, 400), (650, 432), (712, 476)]
SNOW = [(578, 431), (606, 400), (622, 400), (648, 430), (634, 424), (624, 434), (612, 422), (598, 434), (590, 426)]
BOAT_A = [(226, 500), (360, 478), (504, 452), (500, 463), (362, 492), (232, 510)]
BOAT_B = [(610, 572), (700, 566), (800, 576), (796, 586), (700, 580), (612, 582)]
FRONT_CREST = smooth((640, 556), (700, 522), (760, 508), (822, 522), (880, 558))


def claws(start, end, n, length):
    """Hooked foam fingers along the crest between two crest indices, curling forward and down."""
    for i in range(n):
        t = start + (end - start) * i / max(1, n - 1)
        k = int(t)
        (x, y), (nx, ny) = CREST[k], CREST[min(k + 1, len(CREST) - 1)]
        ang = math.atan2(ny - y, nx - x)
        tip = (x + math.cos(ang - 0.6) * length, y + math.sin(ang - 0.6) * length)
        hook = (tip[0] + math.cos(ang + 1.4) * length * 0.45, tip[1] + math.sin(ang + 1.4) * length * 0.45)
        line(FOAM, 6, (x, y), tip, hook)


if __name__ == "__main__":
    random.seed(31)
    canvas(W, H)
    with recording(os.path.join(HERE, "02_great_wave.gif")):
        # sky: cream, darkening toward the top in two soft bands
        cover([(-40, -40), (W + 40, -40), (W + 40, H + 40), (-40, H + 40)], CREAM, 70, smooth_poly=False, wobble=0.5)
        cover([(-40, -40), (W + 40, -40), (W + 40, 118), (600, 104), (300, 118), (-40, 106)], SKY_MID, 40)
        cover([(-40, -40), (W + 40, -40), (W + 40, 60), (500, 50), (-40, 62)], SKY_TOP, 34)

        # distant mountain with its snow cap
        cover(FUJI_SHAPE, FUJI, 18, smooth_poly=False)
        cover(SNOW, FOAM, 8, smooth_poly=False)

        # the big wave, then the front wave: deep blue bodies
        cover(WAVE, BLUE, 60, angle=-30)
        cover(FRONT_WAVE, BLUE, 30, angle=-20)

        # lighter stripes following the crest's curve, deeper blue inside the curl
        for d, c, size in ((34, MID_BLUE, 9), (58, MID_BLUE, 7), (86, LIGHT_BLUE, 5), (118, MID_BLUE, 6), (150, LIGHT_BLUE, 4)):
            line(c, size, *offset(CREST[4:-3], d))
        line(NAVY, 14, (450, 214), (400, 214), (360, 246), (340, 300), (348, 360), (392, 424))

        # foam: a white band along the crest, then claws reaching forward over the curl
        band = CREST[2:] + list(reversed(offset(CREST[2:], 22)))
        cover(band, FOAM, 14, smooth_poly=False)
        claws(10, len(CREST) - 2, 16, 26)
        cover(FRONT_CREST + list(reversed(offset(FRONT_CREST, 12))), FOAM, 8, smooth_poly=False)

        # boats with rowers
        cover(BOAT_A, BOAT, 8, smooth_poly=False)
        cover(BOAT_B, BOAT, 6, smooth_poly=False)
        color(NAVY)
        for x in range(250, 490, 34):
            y = 500 - (x - 226) * 0.18
            stroke([(x, y - 6), (x + 1, y - 6)], 9)
        for x in range(630, 790, 32):
            stroke([(x, 568), (x + 1, 568)], 8)

        # crisp dark outlines with the calligraphy pen
        def outline(pts, size=3, closed=True):
            color(NAVY)
            path = pts + pts[:1] if closed else pts
            from brushlib import p
            p.stroke([(min(W - 1, max(0, round(x))), min(H - 1, max(0, round(y)))) for x, y in path], size=size, brush="Calligraphy pen")

        outline(CREST + CURL[:-1], 4, closed=False)
        outline(FRONT_CREST, 3, closed=False)
        outline(FUJI_SHAPE, 2)
        outline(BOAT_A, 2)
        outline(BOAT_B, 2)

        # spray thrown off the crest
        color(FOAM)
        for _ in range(40):
            x, y = random.uniform(430, 640), random.uniform(110, 280)
            if (x - 470) ** 2 / 170 ** 2 + (y - 160) ** 2 / 110 ** 2 < 1:
                stroke([(x, y), (x + 1, y)], random.choice((4, 5, 6)))
    save(os.path.join(HERE, "02_great_wave.png"))
