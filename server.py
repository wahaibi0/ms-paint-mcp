"""MCP server that paints in Windows 11 Paint by driving its real UI.

Controls are found by name through UI Automation (native FindFirst/FindAll only:
pywinauto's Python-side tree walk is slow enough to hang Paint). Mouse input goes
through mouse_event because Paint ignores pywinauto's drag moves.
"""

import ctypes
import io
import os
import re
import subprocess
import time
from typing import Literal

from mcp.server.mcpserver import Image, MCPServer
from PIL import ImageGrab
from pywinauto import Desktop, keyboard
from pywinauto.controls.uiawrapper import UIAWrapper
from pywinauto.uia_defines import IUIA
from pywinauto.uia_element_info import UIAElementInfo

mcp = MCPServer(
    "ms-paint",
    instructions="Paints in Microsoft Paint. Start with new_canvas, then draw with stroke/shape/fill "
    "and call view to see the result. Coordinates are image pixels, origin top-left.",
)

_u32 = ctypes.windll.user32
_uia = IUIA()
MOVE, DOWN, UP, ABSOLUTE = 0x1, 0x2, 0x4, 0x8000

Shape = Literal[
    "Line", "Oval", "Rectangle", "Rounded rectangle", "Triangle", "Right triangle", "Diamond",
    "Pentagon", "Hexagon", "Right arrow", "Left arrow", "Up arrow", "Down arrow",
    "Four-point star", "Five-point star", "Six-point star", "Heart", "Lightning",
    "Rounded rectangular callout", "Oval callout", "Cloud callout",
]
STROKE_TOOLS = {"brush": ("Brushes", "RadioButton"), "pencil": ("Pencil", "Button"), "eraser": ("Eraser", "Button")}


def _paint():
    """Return Paint's main window (launching it if needed), maximized and focused."""
    for _ in range(50):
        windows = Desktop(backend="win32").windows(class_name="MSPaintApp")
        if windows:
            break
        if _ == 0:
            subprocess.Popen("mspaint")
        time.sleep(0.3)
    else:
        raise RuntimeError("Paint did not start")
    w = windows[0]
    if not w.is_maximized():
        w.maximize()
        time.sleep(1.5)
    w.set_focus()
    return w


def _find(prop, value, control_type=None, required=True):
    cond = _uia.iuia.CreatePropertyCondition(getattr(_uia.UIA_dll, f"UIA_{prop}PropertyId"), value)
    if control_type:
        ct = _uia.iuia.CreatePropertyCondition(_uia.UIA_dll.UIA_ControlTypePropertyId, _uia.known_control_types[control_type])
        cond = _uia.iuia.CreateAndCondition(cond, ct)
    el = _uia.iuia.ElementFromHandle(_paint().handle).FindFirst(_uia.tree_scope["descendants"], cond)
    if not el:
        if required:
            raise RuntimeError(f"Paint control not found: {value}")
        return None
    return UIAElementInfo(el)


def _mouse(flags, x, y):
    sw, sh = _u32.GetSystemMetrics(0), _u32.GetSystemMetrics(1)
    _u32.mouse_event(flags | MOVE | ABSOLUTE, round(x * 65535 / (sw - 1)), round(y * 65535 / (sh - 1)), 0, 0)


def _drag(points, delay=0.004):
    """Press at the first screen point, move through the rest, release at the last."""
    _mouse(0, *points[0])
    time.sleep(0.05)
    _mouse(DOWN, *points[0])
    time.sleep(0.05)
    for p in points[1:]:
        _mouse(0, *p)
        time.sleep(delay)
    _mouse(UP, *points[-1])
    time.sleep(0.2)


def _click(name, control_type="Button"):
    c = _find("Name", name, control_type).rectangle.mid_point()
    _drag([(c.x, c.y)])
    time.sleep(0.2)


def _canvas():
    """(screen rect, image width, image height) of the canvas."""
    rect = _find("AutomationId", "image", "Group").rectangle
    w, h = map(int, re.findall(r"\d+", _find("AutomationId", "CanvasSizeTextBlock").name)[:2])
    return rect, w, h


def _to_screen(points):
    rect, w, h = _canvas()
    scale = rect.width() / w  # shortcut: assumes the whole canvas is visible (new_canvas fits it to the window)
    out = []
    for x, y in points:
        if not (0 <= x < w and 0 <= y < h):
            raise ValueError(f"point ({x}, {y}) is outside the {w}x{h} canvas")
        out.append((round(rect.left + (x + 0.5) * scale), round(rect.top + (y + 0.5) * scale)))
    return out


@mcp.tool()
def new_canvas(width: int = 1000, height: int = 700, discard_unsaved: bool = False) -> str:
    """Start a fresh white canvas of the given size in pixels, fitted to the window.
    If the current image has unsaved changes this fails unless discard_unsaved is true."""
    if not (1 <= width <= 5000 and 1 <= height <= 5000):
        raise ValueError("width and height must be 1-5000")
    _paint()
    keyboard.send_keys("{ESC}^n")
    time.sleep(1)
    dont_save = _find("AutomationId", "SecondaryButton", "Button", required=False)  # "Don’t save"
    if dont_save:
        if not discard_unsaved:
            keyboard.send_keys("{ESC}")
            raise RuntimeError("Paint has unsaved changes. Save them first, or pass discard_unsaved=true.")
        c = dont_save.rectangle.mid_point()
        _drag([(c.x, c.y)])
        time.sleep(1)
    keyboard.send_keys("^e")
    time.sleep(1)
    _click("Pixels", "RadioButton")
    for box, value in (("WidthNumberBox", width), ("HeightNumberBox", height)):
        c = _find("AutomationId", box).rectangle
        _drag([(c.left + 40, c.bottom - 15)])
        keyboard.send_keys(f"^a{value}{{TAB}}")
    _click("OK")
    time.sleep(0.5)
    _click("Fit to window")
    _, w, h = _canvas()
    return f"New {w}x{h} canvas ready."


@mcp.tool()
def set_color(hex_color: str) -> str:
    """Set the drawing color (Paint's Color 1), e.g. '#ff8800'."""
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", hex_color):
        raise ValueError("color must look like #RRGGBB")
    hex_color = hex_color.lstrip("#").upper()
    win = _paint()
    radios = _uia.iuia.ElementFromHandle(win.handle).FindAll(
        _uia.tree_scope["descendants"],
        _uia.iuia.CreatePropertyCondition(_uia.UIA_dll.UIA_ControlTypePropertyId, _uia.known_control_types["RadioButton"]),
    )
    swatch = next(UIAElementInfo(r) for r in map(radios.GetElement, range(radios.Length)) if r.CurrentName.startswith("Color 1"))
    swatch = swatch.rectangle.mid_point()
    content = next(c for c in win.children() if "DesktopChildSiteBridge" in c.class_name()).rectangle()
    scale = _u32.GetDpiForWindow(win.handle) / 96
    _click("Edit colors")
    time.sleep(1.2)
    # No UI Automation while this dialog is open: querying it makes Paint hang.
    # shortcut: hex box found by its offset from the centered dialog, re-measure if Paint's layout changes
    cx, cy = content.mid_point()
    _drag([(round(cx + 100 * scale), round(cy - 241 * scale))])
    keyboard.send_keys(f"^a{hex_color}")
    # Paint stamps a dot where the pointer is when the dialog closes, so park it on the title bar.
    _mouse(0, cx, win.rectangle().top + 12)
    keyboard.send_keys("{ENTER}")
    time.sleep(0.6)
    got = "%02X%02X%02X" % ImageGrab.grab().getpixel((swatch.x, swatch.y))[:3]
    if got != hex_color:
        raise RuntimeError(f"color did not apply: swatch shows #{got}")
    return f"Color set to #{hex_color}."


@mcp.tool()
def stroke(
    points: list[tuple[int, int]],
    tool: Literal["brush", "pencil", "eraser"] = "brush",
    size: int | None = None,
) -> str:
    """Drag the brush, pencil or eraser through the given (x, y) image points in one stroke.
    Pass dense points for smooth curves. size is the tool width in pixels (1-90)."""
    if not points:
        raise ValueError("points is empty")
    screen = _to_screen(points)
    _click(*STROKE_TOOLS[tool])
    if size is not None:
        if not 1 <= size <= 90:
            raise ValueError("size must be 1-90")
        UIAWrapper(_find("Name", "Size", "Slider")).iface_range_value.SetValue(size)
    _drag(screen)
    return f"Drew a {tool} stroke through {len(points)} points."


@mcp.tool()
def shape(kind: Shape, x1: int, y1: int, x2: int, y2: int) -> str:
    """Draw a Paint shape outline in the current color, dragged from (x1, y1) to (x2, y2).
    Fill it afterwards with fill() if you want it solid."""
    (sx1, sy1), (sx2, sy2) = _to_screen([(x1, y1), (x2, y2)])
    _click(kind)
    steps = 20
    _drag([(sx1 + (sx2 - sx1) * i // steps, sy1 + (sy2 - sy1) * i // steps) for i in range(steps + 1)], delay=0.01)
    _click(kind)  # commits the shape; Escape would discard it
    return f"Drew {kind}."


@mcp.tool()
def fill(x: int, y: int) -> str:
    """Flood-fill the region containing (x, y) with the current color."""
    (sx, sy), = _to_screen([(x, y)])
    _click("Fill")
    _drag([(sx, sy)])
    return f"Filled at ({x}, {y})."


@mcp.tool()
def undo() -> str:
    """Undo the last action in Paint."""
    _paint()
    keyboard.send_keys("^z")
    return "Undone."


@mcp.tool()
def view() -> Image:
    """Screenshot of the canvas, to check your work."""
    rect, _, _ = _canvas()
    time.sleep(0.2)
    buf = io.BytesIO()
    ImageGrab.grab((rect.left, rect.top, rect.right, rect.bottom)).save(buf, "PNG")
    return Image(data=buf.getvalue(), format="png")


@mcp.tool()
def save(path: str) -> str:
    """Save the image to a new absolute .png path through Paint's Save As dialog."""
    path = os.path.abspath(path)
    if not path.lower().endswith(".png"):
        raise ValueError("path must end with .png")
    if os.path.exists(path):
        raise ValueError(f"{path} already exists; pick a new name")
    win = _paint()
    keyboard.send_keys("^+s")
    dlg = Desktop(backend="win32").window(class_name="#32770", title_re="(?i)save as")
    dlg.wait("ready", timeout=10)
    # The type list remembers the last format used, and Paint saves in that format whatever the extension.
    next(c for c in dlg.descendants(class_name="ComboBox") if "PNG (*.png)" in c.texts()).select("PNG (*.png)")
    name = dlg.descendants(class_name="Edit")[0]
    name.set_edit_text(path)
    name.type_keys("{ENTER}")
    stem = os.path.splitext(os.path.basename(path))[0]
    for _ in range(20):
        # The file appears before Paint finishes writing it; the title changes once it's done.
        if os.path.exists(path) and win.window_text().startswith(stem):
            return f"Saved {path}."
        time.sleep(0.3)
    raise RuntimeError("Save did not complete; check Paint for a dialog")


if __name__ == "__main__":
    mcp.run()
