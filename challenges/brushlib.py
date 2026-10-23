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
PREVIEW = None  # a PIL image: strokes are simulated there instead of painted in Paint


def canvas(width, height, background=None, preview=False):
    """Start a fresh canvas (optionally toned with a ground color) and remember its size.
    With preview=True nothing touches Paint: strokes are simulated in an image, to check a
    composition cheaply before painting it for real (see `preview_image`)."""
    global W, H, _color, PREVIEW
    W, H, _color = width, height, None
    if preview:
        from PIL import Image
        PREVIEW = Image.new("RGB", (width, height), background or "#FFFFFF")
        return
    PREVIEW = None
    print(p.new_canvas(width, height, discard_unsaved=True, background=background))


def preview_image():
    return PREVIEW


picking = False  # true while Paint's color dialog covers the canvas; the GIF recorder skips those frames


def color(c):
    global _color, picking
    if PREVIEW is not None:
        _color = c
        return
    if c != _color:
        picking = True
        try:
            p.set_color(c)
        finally:
            picking = False
        _color = c


def _clamp(x, y):
    return (min(W - 1, max(0, round(x))), min(H - 1, max(0, round(y))))


def stroke(pts, size, opacity=100, brush="Brush"):
    """One brush stroke. Opacity is always set explicitly: Paint keeps the last value, so one
    glaze would otherwise leave every later stroke see-through."""
    out = []
    for q in pts:
        q = _clamp(*q)
        if not out or q != out[-1]:
            out.append(q)
    if PREVIEW is not None:
        _simulate(out, size, opacity, brush)
        return
    p.stroke(out, size=size, opacity=opacity, brush=brush)


def _simulate(pts, size, opacity, brush):
    """Approximate a round brush stroke in the preview image."""
    from PIL import Image, ImageDraw
    width = size * 0.75 if brush.startswith("Calligraphy") else size
    r = width / 2
    x0, y0 = int(min(q[0] for q in pts) - r - 2), int(min(q[1] for q in pts) - r - 2)
    x1, y1 = int(max(q[0] for q in pts) + r + 3), int(max(q[1] for q in pts) + r + 3)
    layer = Image.new("L", (x1 - x0, y1 - y0), 0)  # just the stroke's bounding box
    d = ImageDraw.Draw(layer)
    local = [(x - x0, y - y0) for x, y in pts]
    for (ax, ay), (bx, by) in zip(local, local[1:] or local):
        d.line([(ax, ay), (bx, by)], fill=255, width=max(1, round(width)))
        d.ellipse([bx - r, by - r, bx + r, by + r], fill=255)
    d.ellipse([local[0][0] - r, local[0][1] - r, local[0][0] + r, local[0][1] + r], fill=255)
    rgb = tuple(int(_color[i:i + 2], 16) for i in (1, 3, 5))
    PREVIEW.paste(Image.new("RGB", layer.size, rgb), (x0, y0), mask=layer.point(lambda v: v * opacity // 100))


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
        # Full miter, so at a sharp tip the point moves as far in as the geometry needs. A tight cap
        # (it was 2x) left tip points too near the corner and the round brush bulged out of the
        # shape there (the Great Wave's lip). Capped at 6x only to tame near-zero angles.
        k = d / max(0.17, nx * normals[0][0] + ny * normals[0][1])
        out.append((cur[0] + nx * k, cur[1] + ny * k))
    return out


def _clip(poly, x0, y0, x1, y1):
    """Clip a polygon to a rectangle (Sutherland-Hodgman)."""
    for inside_, cut in ((lambda q: q[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
                         (lambda q: q[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
                         (lambda q: q[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
                         (lambda q: q[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1))):
        out = []
        for a, b in zip(poly, poly[1:] + poly[:1]):
            if inside_(b):
                if not inside_(a):
                    out.append(cut(a, b))
                out.append(b)
            elif inside_(a):
                out.append(cut(a, b))
        poly = out
        if not poly:
            break
    return poly


def repaint(region, select, new, size=3, step=2):
    """Pixel-level correction on the visible canvas: find pixels inside region(x, y) whose color
    satisfies select(rgb), and paint them `new` in continuous zigzags through neighboring rows.
    Color-selective, so anything else in the region (a boat, a crest) is left alone."""
    import io
    from PIL import Image
    shot = Image.open(io.BytesIO(p.view().data)).convert("RGB")
    scale, ox, oy = p._mapping
    rect, _, _ = p._canvas()
    rows = {}
    for sy in range(0, shot.height, step):
        for sx in range(0, shot.width, step):
            x, y = (rect.left + sx - ox) / scale, (rect.top + sy - oy) / scale
            if region(x, y) and select(shot.getpixel((sx, sy))):
                rows.setdefault(round(y), []).append(round(x))
    runs = []
    for y in sorted(rows):
        xs = sorted(set(rows[y]))
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is None or x - prev > 3:
                runs.append((y, start, prev))
                if x is not None:
                    start = x
            if x is not None:
                prev = x
    print(f"repaint: {sum(b - a + 1 for _, a, b in runs)} px in {len(runs)} runs")
    chains, active = [], []
    for y, a, b in runs:  # join each run to an overlapping run on the row just above: one zigzag stroke
        ch = next((c for c in active if c["y"] >= y - 3 and c["s"][0] <= b + 2 and a - 2 <= c["s"][1]), None)
        if not ch:
            ch = {"p": []}
            chains.append(ch)
            active.append(ch)
        row = [(a, y), (b, y)] if len(ch["p"]) // 2 % 2 == 0 else [(b, y), (a, y)]
        ch["p"] += row
        ch["s"], ch["y"] = (a, b), y
        active = [c for c in active if c["y"] >= y - 3]
    color(new)
    for ch in chains:
        stroke(ch["p"] if len(ch["p"]) > 1 else ch["p"] * 2, size)


def _area(q):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(q, q[1:] + q[:1]))


def cover(poly, c, size, angle=0, spacing=0.55, wobble=1.0, smooth_poly=True, edge=5, opacity=100):
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
    # Clip to the canvas (a few px beyond it) before laying rings. Clamping off-canvas points onto
    # the edge afterwards would pull rings sideways, past the shape's true outline.
    poly = _clip(poly, -6, -6, W + 5, H + 5)
    if len(poly) < 3:
        return
    widths = [min(edge, size)]
    while widths[-1] < size:
        widths.append(min(size, widths[-1] * 2.4))
    center = 0.0
    for k, b in enumerate(widths):
        center = b / 2 if k == 0 else center + b / 2
        ring = _inset(poly, center)
        if _area(ring) * _area(poly) <= 0:
            return  # the shape is used up; the rings so far cover it
        stroke(ring + ring[:1], max(1, round(b)), opacity)  # straight between points: corners stay sharp
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
        stroke(dense, size, opacity)


def save(path):
    """Save the painting as PNG, replacing an earlier save only once the new one is written:
    save to a temporary name first, so a failed save never leaves no file at all."""
    import uuid
    path = os.path.abspath(path)
    tmp = f"{os.path.splitext(path)[0]}-{uuid.uuid4().hex[:8]}.png"
    print(p.save(tmp))
    os.replace(tmp, path)
    print(f"Saved {path}")
