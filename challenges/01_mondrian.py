"""Challenge 1: a composition in the style of Piet Mondrian. Tests straight lines and clean,
even brush coverage."""
import os

from brushlib import canvas, cover, line, save
from record import recording

HERE = os.path.dirname(os.path.abspath(__file__))
S = 700
WHITE, GREY_WHITE = "#F1EEE4", "#E3E1D8"
RED, BLUE, YELLOW, BLACK = "#C8261E", "#1D4E9E", "#F2C431", "#151515"

# The canvas is split recursively, like Mondrian's grids: (axis, at, line width, first, second).
# Leaves are colors. Every line spans exactly its parent rectangle, so lines always meet cleanly.
LAYOUT = ("x", 300, 18,
          ("y", 180, 16,
           ("x", 110, 12, ("y", 90, 8, WHITE, GREY_WHITE), RED),
           ("y", 520, 16,
            ("x", 110, 12, WHITE, ("y", 330, 8, WHITE, YELLOW)),
            ("x", 110, 12, ("y", 610, 8, GREY_WHITE, BLUE), WHITE))),
          ("y", 420, 16,
           ("x", 600, 12,
            ("y", 90, 8, WHITE, ("x", 470, 8, WHITE, GREY_WHITE)),
            ("y", 260, 10, BLUE, WHITE)),
           ("x", 470, 12,
            ("y", 560, 8, WHITE, BLACK),
            ("x", 600, 10, WHITE, ("y", 520, 8, RED, YELLOW)))))


def walk(node, x0, y0, x1, y1, blocks, lines):
    """Collect leaf rectangles and split lines (with their depth-ordered widths)."""
    if isinstance(node, str):
        blocks.append((x0, y0, x1, y1, node))
        return
    axis, at, width, first, second = node
    if axis == "x":
        lines.append((width, (at, y0), (at, y1)))
        walk(first, x0, y0, at, y1, blocks, lines)
        walk(second, at, y0, x1, y1, blocks, lines)
    else:
        lines.append((width, (x0, at), (x1, at)))
        walk(first, x0, y0, x1, at, blocks, lines)
        walk(second, x0, at, x1, y1, blocks, lines)


def past_edge(v):
    """Rectangles touching the canvas edge run past it, so the brush leaves no rim there."""
    return -40 if v <= 0 else S + 40 if v >= S else v


blocks, lines = [], []
walk(LAYOUT, 0, 0, S, S, blocks, lines)

canvas(S, S)
with recording(os.path.join(HERE, "01_mondrian.gif")):
    # warm white ground in broad strokes
    cover([(-40, -40), (S + 40, -40), (S + 40, S + 40), (-40, S + 40)], WHITE, 70, smooth_poly=False, wobble=0.5)

    # color blocks, grouped by color (each color change opens Paint's dialog)
    for c in (GREY_WHITE, RED, BLUE, YELLOW, BLACK):
        for x0, y0, x1, y1, fill in blocks:
            if fill == c:
                x0, y0, x1, y1 = map(past_edge, (x0, y0, x1, y1))
                size = max(10, min(40, round(min(x1 - x0, y1 - y0) / 3)))
                cover([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], c, size, smooth_poly=False, wobble=0.4)

    # black lines, thickest first, so thinner lines end inside the thicker ones they meet
    for width, a, b in sorted(lines, key=lambda l: -l[0]):
        line(BLACK, width, tuple(map(past_edge, a)), tuple(map(past_edge, b)))
save(os.path.join(HERE, "01_mondrian.png"))
