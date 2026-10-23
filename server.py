"""MCP server that paints in Windows 11 Paint by driving its real UI.

Toolbar controls are found by name and pressed through UI Automation (native
FindFirst/FindAll only: pywinauto's Python-side tree walk is slow enough to hang Paint).
The canvas is drawn on with a synthetic pen. Neither touches the user's mouse.
"""

import ctypes
import functools
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

import overlay
import pen

mcp = MCPServer(
    "ms-paint",
    instructions="Paints in Microsoft Paint like a human painter: brush strokes only. There is deliberately "
    "no fill or shape tool; every colored area is built from overlapping brush strokes. Start with "
    "new_canvas, then paint back to front: background, distant scenery, foreground, main subject, "
    "shadows, highlights, fine details. Cover broad areas with large brushes in continuous parallel "
    "strokes, and switch to smaller brushes near edges and for details. Call view between stages to "
    "catch mistakes early, and correct them locally. Coordinates are image pixels, origin top-left. "
    "Call painting_guide first for brush techniques suited to the style the user asks for.",
)


def tool(fn):
    """Register an MCP tool that shows the "Claude is drawing" overlay while it runs."""
    @functools.wraps(fn)
    def run(*args, **kwargs):
        with overlay.showing():
            return fn(*args, **kwargs)
    return mcp.tool()(run)


_u32 = ctypes.windll.user32
_uia = IUIA()

STROKE_TOOLS = {"brush": ("Brushes", "RadioButton"), "pencil": ("Pencil", "Button"), "eraser": ("Eraser", "Button")}
_tool = None  # stroke tool last selected, so strokes don't re-tap the toolbar; forgotten whenever Paint loses focus


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
    if not _in_front(w):
        global _tool
        _tool = None  # the user may have changed tools while Paint was in the background
        # Paint ignores input while in the background, so it has to come forward. pywinauto's set_focus
        # moves the mouse away, so do it ourselves. Windows refuses SetForegroundWindow from background
        # processes unless we share input with the current foreground thread.
        for attempt in range(4):
            fg_thread = _u32.GetWindowThreadProcessId(_u32.GetForegroundWindow(), None)
            me = ctypes.windll.kernel32.GetCurrentThreadId()
            _u32.AttachThreadInput(me, fg_thread, True)
            try:
                if attempt == 3:  # last resort: restoring from minimized activates the window
                    _u32.ShowWindow(w.handle, 6)  # SW_MINIMIZE
                    _u32.ShowWindow(w.handle, 3)  # SW_MAXIMIZE
                _u32.BringWindowToTop(w.handle)
                _u32.SetForegroundWindow(w.handle)
            finally:
                _u32.AttachThreadInput(me, fg_thread, False)
            time.sleep(0.8)  # input sent too soon after activation gets swallowed
            if _in_front(w):
                break
        else:
            raise RuntimeError("could not bring Paint to the front")
    return w


def _in_front(w):
    """Whether a Paint window (main or one of its dialog popups) has the foreground."""
    pid = ctypes.c_ulong()
    _u32.GetWindowThreadProcessId(_u32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value == w.process_id()


def _keys(keys):
    """Type into Paint, refusing if anything else has the keyboard so keys never land in the user's windows."""
    if not _in_front(_paint()):
        raise RuntimeError("Paint is not in front; not sending keystrokes")
    keyboard.send_keys(keys)


def _find(prop, value, control_type=None, required=True, root=None):
    cond = _uia.iuia.CreatePropertyCondition(getattr(_uia.UIA_dll, f"UIA_{prop}PropertyId"), value)
    if control_type:
        ct = _uia.iuia.CreatePropertyCondition(_uia.UIA_dll.UIA_ControlTypePropertyId, _uia.known_control_types[control_type])
        cond = _uia.iuia.CreateAndCondition(cond, ct)
    root = root.element if root else _uia.iuia.ElementFromHandle(_paint().handle)
    el = root.FindFirst(_uia.tree_scope["descendants"], cond)
    if not el:
        if required:
            raise RuntimeError(f"Paint control not found: {value}")
        return None
    return UIAElementInfo(el)


def _press(name, control_type="Button", prop="Name"):
    """Tap a Paint control with the pen. (UI Automation can't press Paint's tool buttons: they are
    toggle buttons whose Toggle and default action do nothing.)"""
    c = _find(prop, name, control_type).rectangle.mid_point()
    pen.stroke([(c.x, c.y)])
    time.sleep(0.2)


# Paint's size slider paints true to its value up to about 24, then much wider (measured for the
# Brush: slider value, painted width in px).
_SIZE_CURVE = [(1, 1), (24, 25), (30, 38), (32, 41), (36, 49), (40, 57), (45, 67), (55, 87), (60, 97),
               (70, 132), (80, 174), (90, 250)]


def _slider_for(width):
    """Slider value that paints `width` px with the Brush."""
    for (s0, w0), (s1, w1) in zip(_SIZE_CURVE, _SIZE_CURVE[1:]):
        if width <= w1:
            return max(1, round(s0 + (s1 - s0) * (width - w0) / (w1 - w0)))
    return 90


def _pick_brush(kind):
    """Choose a brush type from the menu under the Brushes button (the menu is its own popup window)."""
    r = _find("AutomationId", "BrushesSplitButton").rectangle
    pen.stroke([((r.left + r.right) // 2, r.bottom - 8)])  # the menu arrow
    time.sleep(0.8)
    tops = _uia.iuia.GetRootElement().FindAll(
        _uia.tree_scope["children"],
        _uia.iuia.CreatePropertyCondition(_uia.UIA_dll.UIA_ProcessIdPropertyId, _paint().process_id()),
    )
    for top in map(tops.GetElement, range(tops.Length)):
        item = _find("Name", kind, "MenuItem", required=False, root=UIAElementInfo(top))
        if item:
            c = item.rectangle.mid_point()
            pen.stroke([(c.x, c.y)])
            time.sleep(0.3)
            return
    _keys("{ESC}")
    raise RuntimeError(f"brush type not found: {kind}")


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


@tool
def new_canvas(width: int = 1000, height: int = 700, discard_unsaved: bool = False) -> str:
    """Start a fresh white canvas of the given size in pixels, fitted to the window.
    If the current image has unsaved changes this fails unless discard_unsaved is true."""
    if not (1 <= width <= 5000 and 1 <= height <= 5000):
        raise ValueError("width and height must be 1-5000")
    global _tool
    _tool = None
    _paint()
    _keys("{ESC}^n")
    time.sleep(1)
    dont_save = _find("AutomationId", "SecondaryButton", "Button", required=False)  # "Don’t save"
    if dont_save:
        if not discard_unsaved:
            _keys("{ESC}")
            raise RuntimeError("Paint has unsaved changes. Save them first, or pass discard_unsaved=true.")
        UIAWrapper(dont_save).invoke()
        time.sleep(1)
    for _ in range(2):  # Ctrl+E is occasionally swallowed; retry once
        _keys("^e")
        for _ in range(10):
            time.sleep(0.3)
            if _find("Name", "Pixels", "RadioButton", required=False):
                break
        else:
            continue
        break
    _press("Pixels", "RadioButton")
    for box, value in (("WidthNumberBox", width), ("HeightNumberBox", height)):
        UIAWrapper(_find("AutomationId", "InputBox", "Edit", root=_find("AutomationId", box))).set_edit_text(str(value))
    _press("PrimaryButton", prop="AutomationId")  # OK
    time.sleep(0.5)
    _press("Fit to window")
    _, w, h = _canvas()
    if (w, h) != (width, height):
        raise RuntimeError(f"canvas came out {w}x{h}, not {width}x{height}")
    return f"New {w}x{h} canvas ready."


@tool
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
    cx, cy = content.mid_point()
    # One retry: a tap right after Paint comes to the front is sometimes swallowed.
    for _ in range(2):
        _press("Edit colors")
        time.sleep(1.2)
        # No UI Automation while this dialog is open: querying it makes Paint hang.
        # shortcut: hex box found by its offset from the centered dialog, re-measure if Paint's layout changes
        pen.stroke([(round(cx + 100 * scale), round(cy - 241 * scale))])
        _keys(f"^a{hex_color}{{ENTER}}")
        time.sleep(0.6)
        got = "%02X%02X%02X" % ImageGrab.grab().getpixel((swatch.x, swatch.y))[:3]
        if got == hex_color:
            return f"Color set to #{hex_color}."
        _keys("{ESC}")  # closes the dialog if it is still open
        time.sleep(0.5)
    raise RuntimeError(f"color did not apply: swatch shows #{got}")


@tool
def stroke(
    points: list[tuple[int, int]],
    tool: Literal["brush", "pencil", "eraser"] = "brush",
    size: int | None = None,
    brush: Literal[
        "Brush", "Calligraphy brush", "Calligraphy pen", "Airbrush", "Oil brush",
        "Crayon", "Marker", "Natural pencil", "Watercolor brush",
    ] = "Brush",
    opacity: int | None = None,
) -> str:
    """Drag the brush, pencil or eraser through the given (x, y) image points in one stroke.
    Pass dense points for smooth curves. For the brush, size is the painted width in pixels
    (1-250; other brush types than "Brush" come out somewhat wider or narrower). For the pencil
    and eraser it is Paint's raw size setting (1-90).
    brush picks Paint's brush type (texture), used when tool is "brush".
    opacity (1-100) makes the stroke see-through, for glazing and blending colors."""
    if not points:
        raise ValueError("points is empty")
    if opacity is not None and not 1 <= opacity <= 100:
        raise ValueError("opacity must be 1-100")
    global _tool
    screen = _to_screen(points)
    want = (tool, brush) if tool == "brush" else (tool, None)
    if _tool != want:
        if tool == "brush":
            _pick_brush(brush)
        else:
            _press(*STROKE_TOOLS[tool])
        _tool = want
    if opacity is not None:
        UIAWrapper(_find("Name", "Opacity", "Slider")).iface_range_value.SetValue(opacity)
    if size is not None:
        if tool == "brush":
            if not 1 <= size <= 250:
                raise ValueError("brush size must be 1-250")
            size = _slider_for(size)
        elif not 1 <= size <= 90:
            raise ValueError("size must be 1-90")
        UIAWrapper(_find("Name", "Size", "Slider")).iface_range_value.SetValue(size)
    pen.stroke(screen)
    return f"Drew a {tool} stroke through {len(points)} points."


@mcp.tool()
def painting_guide() -> str:
    """Lessons learned and a per-style playbook (which brush types, sizes, opacity and stroke
    patterns suit Mondrian, ukiyo-e, impressionism and so on). Read it before painting."""
    return open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "LESSONS.md"), encoding="utf-8").read()


@tool
def undo() -> str:
    """Undo the last action in Paint."""
    _press("Undo")
    return "Undone."


@tool
def view() -> Image:
    """Screenshot of the canvas, to check your work."""
    rect, _, _ = _canvas()
    time.sleep(0.2)
    buf = io.BytesIO()
    ImageGrab.grab((rect.left, rect.top, rect.right, rect.bottom)).save(buf, "PNG")
    return Image(data=buf.getvalue(), format="png")


@tool
def save(path: str) -> str:
    """Save the image to a new absolute .png path through Paint's Save As dialog."""
    path = os.path.abspath(path)
    if not path.lower().endswith(".png"):
        raise ValueError("path must end with .png")
    if os.path.exists(path):
        raise ValueError(f"{path} already exists; pick a new name")
    win = _paint()
    _keys("^+s")
    dlg = Desktop(backend="win32").window(class_name="#32770", title_re="(?i)save as")
    dlg.wait("ready", timeout=10)
    # The type list remembers the last format used, and Paint saves in that format whatever the extension.
    next(c for c in dlg.descendants(class_name="ComboBox") if "PNG (*.png)" in c.texts()).select("PNG (*.png)")
    name = dlg.descendants(class_name="Edit")[0]
    name.set_edit_text(path)
    _keys("{ENTER}")  # not name.type_keys: its set_focus moves the mouse
    stem = os.path.splitext(os.path.basename(path))[0]
    for _ in range(20):
        # The file appears before Paint finishes writing it; the title changes once it's done.
        if os.path.exists(path) and win.window_text().startswith(stem):
            return f"Saved {path}."
        time.sleep(0.3)
    raise RuntimeError("Save did not complete; check Paint for a dialog")


if __name__ == "__main__":
    mcp.run()
