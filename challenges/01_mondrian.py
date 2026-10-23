"""Challenge 1: a composition in Mondrian's style. Tests straight lines and even brush coverage."""
import os

from brushlib import canvas, cover, line, save
from record import recording

HERE = os.path.dirname(os.path.abspath(__file__))
S = 600
WHITE, RED, BLUE, YELLOW, BLACK = "#F1EEE4", "#C8261E", "#1D4E9E", "#F2C431", "#141414"


def block(x0, y0, x1, y1, c, size=34):
    cover([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], c, size, smooth_poly=False, wobble=0.4)


canvas(S, S)
with recording(os.path.join(HERE, "01_mondrian.gif")):
    # off-white ground, laid in broad horizontal strokes
    block(-30, -30, S + 30, S + 30, WHITE, size=60)  # past the edges: brush runs off the canvas

    # primary blocks, each bounded by line centers so the black lines cover the seams
    block(160, -30, 430, 210, RED)
    block(-30, 470, 160, S + 30, BLUE)
    block(530, 470, S + 30, S + 30, YELLOW, size=24)
    block(430, 340, S + 30, 470, WHITE, size=30)  # second coat: whites in Mondrian are layered too

    # black lines, thickest first
    line(BLACK, 16, (160, 0), (160, S - 1))
    line(BLACK, 16, (430, 0), (430, S - 1))
    line(BLACK, 16, (0, 210), (S - 1, 210))
    line(BLACK, 16, (0, 470), (S - 1, 470))
    line(BLACK, 10, (430, 340), (S - 1, 340))
    line(BLACK, 10, (530, 470), (530, S - 1))
    line(BLACK, 10, (0, 100), (160, 100))
save(os.path.join(HERE, "01_mondrian.png"))
