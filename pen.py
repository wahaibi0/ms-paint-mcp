"""Draws with an injected synthetic pen, so the user's mouse cursor never moves."""

import ctypes
import time
from ctypes import wintypes as W

import overlay

PT_PEN = 3
INRANGE, INCONTACT, DOWN, UPDATE, UP = 0x2, 0x4, 0x10000, 0x20000, 0x40000


class POINTER_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerType", W.DWORD), ("pointerId", ctypes.c_uint32), ("frameId", ctypes.c_uint32),
        ("pointerFlags", ctypes.c_uint32), ("sourceDevice", W.HANDLE), ("hwndTarget", W.HWND),
        ("ptPixelLocation", W.POINT), ("ptHimetricLocation", W.POINT), ("ptPixelLocationRaw", W.POINT),
        ("ptHimetricLocationRaw", W.POINT), ("dwTime", W.DWORD), ("historyCount", ctypes.c_uint32),
        ("InputData", ctypes.c_int32), ("dwKeyStates", W.DWORD), ("PerformanceCount", ctypes.c_uint64),
        ("ButtonChangeType", ctypes.c_int),
    ]


class POINTER_PEN_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerInfo", POINTER_INFO), ("penFlags", ctypes.c_uint32), ("penMask", ctypes.c_uint32),
        ("pressure", ctypes.c_uint32), ("rotation", ctypes.c_uint32), ("tiltX", ctypes.c_int32), ("tiltY", ctypes.c_int32),
    ]


class POINTER_TOUCH_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerInfo", POINTER_INFO), ("touchFlags", ctypes.c_uint32), ("touchMask", ctypes.c_uint32),
        ("rcContact", W.RECT), ("rcContactRaw", W.RECT), ("orientation", ctypes.c_uint32), ("pressure", ctypes.c_uint32),
    ]


class POINTER_TYPE_INFO(ctypes.Structure):
    class _U(ctypes.Union):
        # The union is sized by its largest member, so touch info must be declared even though only pen is used.
        _fields_ = [("touchInfo", POINTER_TOUCH_INFO), ("penInfo", POINTER_PEN_INFO)]

    _fields_ = [("type", W.DWORD), ("u", _U)]


_u32 = ctypes.windll.user32
_u32.CreateSyntheticPointerDevice.restype = W.HANDLE
_u32.InjectSyntheticPointerInput.argtypes = [W.HANDLE, ctypes.POINTER(POINTER_TYPE_INFO), ctypes.c_uint32]
_device = None


def _send(x, y, flags):
    global _device
    if _device is None:
        _device = _u32.CreateSyntheticPointerDevice(PT_PEN, 1, 3)  # 3 = POINTER_FEEDBACK_NONE
        if not _device:
            raise ctypes.WinError()
    info = POINTER_TYPE_INFO(type=PT_PEN)
    pen = info.u.penInfo
    pen.pointerInfo.pointerType = PT_PEN
    pen.pointerInfo.pointerFlags = flags
    pen.pointerInfo.ptPixelLocation = W.POINT(x, y)
    pen.penMask = 0x1  # pressure
    pen.pressure = 1024 if flags & INCONTACT else 0  # full pressure: the brush scales its width by it
    if not _u32.InjectSyntheticPointerInput(_device, ctypes.byref(info), 1):
        raise ctypes.WinError()
    overlay.at = (x, y)


def stroke(points, delay=0.008):
    """Put the pen down at the first screen point, drag through the rest, lift at the last."""
    _send(*points[0], INRANGE | UPDATE)
    time.sleep(0.02)
    _send(*points[0], INRANGE | INCONTACT | DOWN)
    time.sleep(0.02)
    for p in points[1:]:
        _send(*p, INRANGE | INCONTACT | UPDATE)
        time.sleep(delay)
    _send(*points[-1], INRANGE | UP)
    time.sleep(0.02)
    _send(*points[-1], UPDATE)  # pen leaves hover range
    time.sleep(0.2)
