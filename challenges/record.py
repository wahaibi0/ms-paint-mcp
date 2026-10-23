"""Records the whole Paint window while a challenge paints, then writes a sped-up GIF.

The live overlay is hidden from screen capture, so its orange border, "Claude is drawing" label
and pen cursor are drawn into each frame here, matching what you see on screen.
"""

import ctypes
import threading
import time
from contextlib import contextmanager
from ctypes import wintypes

from PIL import Image, ImageDraw, ImageFont, ImageGrab

import brushlib
import overlay
from brushlib import p

ORANGE = (217, 119, 87)


def _window_box():
    rect = wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(p._paint().handle, 9, ctypes.byref(rect), ctypes.sizeof(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def _decorate(frame, box):
    """Draw the overlay as it looks live: border, label pill, pen cursor."""
    d = ImageDraw.Draw(frame)
    w, h = frame.size
    d.rectangle([0, 0, w - 1, h - 1], outline=ORANGE, width=6)
    d.rectangle([w // 2 - 75, 0, w // 2 + 75, 26], fill=ORANGE)
    try:
        font = ImageFont.truetype("segoeuib.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    d.text((w // 2, 13), "Claude is drawing", fill="white", font=font, anchor="mm")
    if overlay.at:
        x, y = overlay.at[0] - box[0], overlay.at[1] - box[1]
        d.polygon([(x + dx, y + dy) for dx, dy in overlay.ARROW], fill=ORANGE, outline="white")
    return frame


@contextmanager
def recording(path, every=0.4, width=960, frame_ms=70):
    """Grab the Paint window every `every` seconds; play frames at `frame_ms` each (about 6x speed)."""
    box = _window_box()  # read once here: UI Automation isn't safe from the capture thread
    frames, stop = [], threading.Event()

    def grab():
        shown_pick = False
        while not stop.is_set():
            if brushlib.picking:
                # keep one frame of the color dialog per pick, not the whole wait
                if not shown_pick:
                    time.sleep(1.4)
                    if brushlib.picking:
                        frames.append(_decorate(ImageGrab.grab(box).convert("RGB"), box))
                    shown_pick = True
                time.sleep(0.05)
                continue
            shown_pick = False
            frames.append(_decorate(ImageGrab.grab(box).convert("RGB"), box))
            time.sleep(every)

    thread = threading.Thread(target=grab, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        overlay.at = None
        frames.append(_decorate(ImageGrab.grab(box).convert("RGB"), box))
        size = (width, round(frames[-1].height * width / frames[-1].width))
        out = [f.resize(size, Image.LANCZOS).quantize(colors=160, method=Image.Quantize.MEDIANCUT) for f in frames]
        durations = [frame_ms] * (len(out) - 1) + [2500]  # hold the finished painting
        out[0].save(path, save_all=True, append_images=out[1:], duration=durations, loop=0, optimize=True)
        print(f"Saved {path} ({len(out)} frames)")
