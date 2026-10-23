"""Drives real Paint through every tool and checks pixels. Discards Paint's current image.
Run: uv run smoke_test.py  (leave the mouse still: the test checks that it never gets moved)"""

import ctypes
import io
import os
import tempfile
from ctypes import wintypes

from PIL import Image as PILImage

import server


def pixel(x, y):
    """Canvas pixel at image coords (x, y), read from view()."""
    shot = PILImage.open(io.BytesIO(server.view().data)).convert("RGB")
    _, w, _ = server._canvas()
    scale = shot.width / w
    return shot.getpixel((int((x + 0.5) * scale), int((y + 0.5) * scale)))


def cursor():
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


mouse_at = cursor()
server.new_canvas(400, 300, discard_unsaved=True)
assert server._canvas()[1:] == (400, 300)
assert pixel(200, 150) == (255, 255, 255)

before = server.view().data
server.set_color("#1E90FF")
assert server.view().data == before, "set_color changed the canvas"
server.stroke([(20, 20), (380, 20)], size=10)
assert pixel(200, 20) == (30, 144, 255), pixel(200, 20)
assert pixel(378, 20) == (30, 144, 255), "orange overlay cursor leaked into view()"

server.set_color("#FF0000")
server.stroke([(100, 150), (300, 150)], size=30)
assert pixel(200, 150) == (255, 0, 0), pixel(200, 150)
assert pixel(200, 137) == (255, 0, 0), "size-30 brush painted narrower than about 26px"
assert pixel(200, 168) == (255, 255, 255), "size-30 brush painted wider than about 36px"

server.undo()
assert pixel(200, 150) == (255, 255, 255)

path = os.path.join(tempfile.mkdtemp(), "smoke.png")
server.save(path)
assert PILImage.open(path).size == (400, 300)
assert cursor() == mouse_at, f"mouse moved from {mouse_at} to {cursor()}"
print("ok", path)
