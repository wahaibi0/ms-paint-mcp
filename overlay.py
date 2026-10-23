"""Orange border, pen cursor and "Claude is drawing" label over Paint while a tool runs.

A click-through, always-on-top Tk window sized to Paint's window. It is excluded from
screen capture so view() and the color check never see it.
"""

import ctypes
import threading
import time
import tkinter as tk
from contextlib import contextmanager
from ctypes import wintypes

ORANGE = "#D97757"
KEY = "#010101"  # color key: pixels of this color are see-through
LINGER = 5  # seconds the overlay stays up after the last tool call, so it doesn't flicker between calls
ARROW = [(0, 0), (0, 26), (6, 20), (11, 31), (16, 29), (11, 18), (20, 18)]

_u32 = ctypes.windll.user32
_dwm = ctypes.windll.dwmapi
at = None  # screen position of Claude's pen (set by pen.py); the orange cursor sits there
_busy = 0
_last = 0.0
_thread = None


@contextmanager
def showing():
    """Show the overlay for the duration of the block."""
    global _busy, _last, _thread
    if _thread is None:
        _thread = threading.Thread(target=_run, daemon=True)
        _thread.start()
    _busy += 1
    try:
        yield
    finally:
        _busy -= 1
        _last = time.monotonic()


def _run():
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True, "-transparentcolor", KEY)
    root.geometry("1x1+0+0")
    canvas = tk.Canvas(root, bg=KEY, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    root.update_idletasks()
    hwnd = int(root.wm_frame(), 16)
    # layered | click-through | no taskbar button | never takes focus
    _u32.SetWindowLongW(hwnd, -20, _u32.GetWindowLongW(hwnd, -20) | 0x80000 | 0x20 | 0x80 | 0x08000000)
    _u32.SetWindowDisplayAffinity(hwnd, 0x11)  # WDA_EXCLUDEFROMCAPTURE

    border = canvas.create_rectangle(0, 0, 0, 0, outline=ORANGE, width=6)
    pill = canvas.create_rectangle(0, 0, 0, 0, fill=ORANGE, outline=ORANGE)
    label = canvas.create_text(0, 0, text="Claude is drawing", fill="white", font=("Segoe UI", 10, "bold"))
    arrow = canvas.create_polygon(0, 0, 0, 0, fill=ORANGE, outline="white", width=2)
    rect = wintypes.RECT()

    def tick():
        paint = _u32.FindWindowW("MSPaintApp", None)
        if paint and not _u32.IsIconic(paint) and (_busy or time.monotonic() - _last < LINGER):
            _dwm.DwmGetWindowAttribute(paint, 9, ctypes.byref(rect), ctypes.sizeof(rect))  # visible frame bounds
            w, h = rect.right - rect.left, rect.bottom - rect.top
            root.geometry(f"{w}x{h}+{rect.left}+{rect.top}")
            canvas.coords(border, 3, 3, w - 3, h - 3)
            canvas.coords(pill, w // 2 - 75, 0, w // 2 + 75, 26)
            canvas.coords(label, w // 2, 13)
            canvas.itemconfigure("all", state="normal")
            if at:
                x, y = at[0] - rect.left, at[1] - rect.top
                canvas.coords(arrow, *[v for dx, dy in ARROW for v in (x + dx, y + dy)])
            else:
                canvas.itemconfigure(arrow, state="hidden")
        else:
            canvas.itemconfigure("all", state="hidden")
        root.after(16, tick)

    tick()
    root.mainloop()
