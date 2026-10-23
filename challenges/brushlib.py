"""Brush-only painting helpers on top of the ms-paint MCP server's tools. No fills: every area is
built from overlapping brush strokes."""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server as p  # noqa: E402

W, H = 0, 0
random.seed(7)
_color = None


def canvas(width, height):
    """Start a fresh canvas and remember its size for clamping."""
    global W, H, _color
    W, H, _color = width, height, None
    print(p.new_canvas(width, height, discard_unsaved=True))


picking = False  # true while Paint's color dialog covers the canvas; the GIF recorder skips those frames


def color(c):
    global _color, picking
    if c != _color:
        picking = True
        try:
            p.set_color(c)
        finally:
            picking = False
        _color = c


def _clamp(x, y):
    return (min(W - 1, max(0, round(x))), min(H - 1, max(0, round(y))))


def stroke(pts, size, opacity=100):
    """One brush stroke. Opacity is always set explicitly: Paint keeps the last value, so one
    glaze would otherwise leave every later stroke see-through."""
    out = []
    for q in pts:
        q = _clamp(*q)
        if not out or q != out[-1]:
            out.append(q)
    p.stroke(out, size=size, opacity=opacity)


def chaikin(pts, closed=False, n=3):
    for _ in range(n):
        seq = pts + [pts[0]] if closed else pts
        out = [] if closed else [pts[0]]
        for (x1, y1), (x2, y2) in zip(seq, seq[1:]):
            out += [(0.75 * x1 + 0.25 * x2, 0.75 * y1 + 0.25 * y2), (0.25 * x1 + 0.75 * x2, 0.25 * y1 + 0.75 * y2)]
        pts = out if closed else out + [pts[-1]]
    return pts


def smooth(*pts, closed=False):
    return chaikin(list(pts), closed)


def line(c, size, *pts, wobble=0.0, opacity=100):
    """One smooth continuous brush stroke through the given points (opacity < 100 glazes)."""
    color(c)
    sm = smooth(*pts) if len(pts) > 2 else list(pts)
    dense = []
    for (x1, y1), (x2, y2) in zip(sm, sm[1:]):
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) / 4))
        dense += [(x1 + (x2 - x1) * i / n + random.uniform(-wobble, wobble),
                   y1 + (y2 - y1) * i / n + random.uniform(-wobble, wobble)) for i in range(n)]
    dense.append(sm[-1])
    stroke(dense, size, opacity)


def egg(cx, cy, rx, ry, chin=0.18, n=72):
    """Closed egg outline: narrower toward the bottom."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        y = cy - ry * math.cos(t)
        k = 1 - chin * max(0.0, (y - cy) / ry)
        pts.append((cx + rx * k * math.sin(t), y))
    return pts


def _spans(poly, y):
    xs = []
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 <= y < y2) or (y2 <= y < y1):
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    xs.sort()
    return list(zip(xs[::2], xs[1::2]))


def _rot(q, a):
    c, s = math.cos(a), math.sin(a)
    return (q[0] * c - q[1] * s, q[0] * s + q[1] * c)


def _inset(poly, d):
    """The polygon moved inward by d (miter offset of each vertex)."""
    area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]))
    side = 1 if area > 0 else -1
    out = []
    for prev, cur, nxt in zip(poly[-1:] + poly[:-1], poly, poly[1:] + poly[:1]):
        normals = []
        for (x1, y1), (x2, y2) in ((prev, cur), (cur, nxt)):
            length = math.hypot(x2 - x1, y2 - y1) or 1
            normals.append((-side * (y2 - y1) / length, side * (x2 - x1) / length))
        nx, ny = normals[0][0] + normals[1][0], normals[0][1] + normals[1][1]
        length = math.hypot(nx, ny) or 1
        nx, ny = nx / length, ny / length
        k = d / max(0.5, nx * normals[0][0] + ny * normals[0][1])  # miter, capped at sharp corners
        out.append((cur[0] + nx * k, cur[1] + ny * k))
    return out


def _area(q):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(q, q[1:] + q[:1]))


def cover(poly, c, size, angle=0, spacing=0.55, wobble=1.0, smooth_poly=True, edge=5):
    """Paint the area inside poly the way a painter does, from the outside in.

    1. Cut in the edge: one continuous stroke of a small brush (`edge` px) whose outer side runs
       exactly along the outline. Smooth contour, near-sharp corners.
    2. Rings following the outline with brushes growing about 2.4x each time up to `size`, each
       ring's outer side on the previous ring's center line, so no slivers open along curves and
       corner pockets stay covered.
    3. The core: parallel rows of the `size` brush at `angle` degrees, as continuous zigzags, their
       centers inside the last ring's center line, so their round tips never reach the edge."""
    color(c)
    if smooth_poly:
        poly = smooth(*poly, closed=True)
    widths = [min(edge, size)]
    while widths[-1] < size:
        widths.append(min(size, widths[-1] * 2.4))
    center = 0.0
    for k, b in enumerate(widths):
        center = b / 2 if k == 0 else center + b / 2
        ring = _inset(poly, center)
        if _area(ring) * _area(poly) <= 0:
            return  # the shape is used up; the rings so far cover it
        stroke(ring + ring[:1], max(1, round(b)))  # straight between points: corners stay sharp
    inner = ring
    gap = max(2.0, size * spacing)
    a = math.radians(angle)
    rp = [_rot(q, -a) for q in inner]
    ys = [q[1] for q in rp]
    top, bottom = min(ys), max(ys)
    n = max(1, math.ceil((bottom - top) / gap))
    rows = [top + (bottom - top) * i / n for i in range(n + 1)]
    chains, active = [], []
    for y in rows:
        nxt = []
        for x0, x1 in _spans(rp, min(max(y, top + 0.01), bottom - 0.01)):
            ch = next((ch for ch in active if ch["s"][0] <= x1 + gap and x0 - gap <= ch["s"][1]), None)
            if ch:
                active.remove(ch)
            else:
                ch = {"p": []}
                chains.append(ch)
            row = [(x0, y), (x1, y)]
            if len(ch["p"]) // 2 % 2:
                row.reverse()
            ch["p"] += row
            ch["s"] = (x0, x1)
            nxt.append(ch)
        active = nxt
    for ch in chains:
        pts = [_rot(q, a) for q in ch["p"]]
        dense = []
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(x2 - x1, y2 - y1) / 25))
            # hand wobble only mid-row; row ends stay exact so tips never reach the edge
            dense += [(x1 + (x2 - x1) * i / n + (random.uniform(-wobble, wobble) if i else 0),
                       y1 + (y2 - y1) * i / n + (random.uniform(-wobble, wobble) if i else 0)) for i in range(n)]
        dense.append(pts[-1])
        stroke(dense, size)


def save(path):
    """Save the finished painting as PNG, replacing an earlier attempt."""
    path = os.path.abspath(path)
    if os.path.exists(path):
        os.remove(path)
    print(p.save(path))
