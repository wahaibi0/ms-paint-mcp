"""Drives real Paint through every tool and checks pixels. Discards Paint's current image.
Run: uv run smoke_test.py  (hands off the mouse while it runs)"""

import io
import os
import tempfile

from PIL import Image as PILImage

import server


def pixel(x, y):
    """Canvas pixel at image coords (x, y), read from view()."""
    shot = PILImage.open(io.BytesIO(server.view().data)).convert("RGB")
    _, w, _ = server._canvas()
    scale = shot.width / w
    return shot.getpixel((int((x + 0.5) * scale), int((y + 0.5) * scale)))


server.new_canvas(400, 300, discard_unsaved=True)
assert server._canvas()[1:] == (400, 300)
assert pixel(200, 150) == (255, 255, 255)

server.set_color("#1E90FF")
server.stroke([(20, 20), (380, 20)], size=10)
assert pixel(200, 20) == (30, 144, 255), pixel(200, 20)

server.set_color("#FF0000")
server.shape("Rectangle", 100, 100, 300, 250)
server.fill(200, 175)
assert pixel(200, 175) == (255, 0, 0), pixel(200, 175)
assert pixel(50, 175) == (255, 255, 255)

server.undo()
assert pixel(200, 175) == (255, 255, 255)

path = os.path.join(tempfile.mkdtemp(), "smoke.png")
server.save(path)
assert PILImage.open(path).size == (400, 300)
print("ok", path)
