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
from pywinauto import Desktop
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
    "catch mistakes early, and correct them locally on the same canvas with the brush; never start "
    "over. The only fill allowed is toning the blank canvas with new_canvas(background=...). "
    "Work in a loop: look (view, zoom), compare with the reference, paint the change with the best gain "
    "against risk, look again; coarse to fine; protect areas that are already right; stop when more work "
    "would hurt more than help. Coordinates are image pixels, origin top-left. "
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
        # Keep trying for about 30 s: when something else holds the foreground for a moment, the
        # painting pauses instead of failing. Minimize-and-restore only once, as a last resort.
        deadline = time.monotonic() + 30
        attempt = 0
        while True:
            fg_thread = _u32.GetWindowThreadProcessId(_u32.GetForegroundWindow(), None)
            me = ctypes.windll.kernel32.GetCurrentThreadId()
            _u32.AttachThreadInput(me, fg_thread, True)
            try:
                if attempt == 12:  # restoring from minimized activates the window
                    _u32.ShowWindow(w.handle, 6)  # SW_MINIMIZE
                    _u32.ShowWindow(w.handle, 3)  # SW_MAXIMIZE
                _u32.BringWindowToTop(w.handle)
                _u32.SetForegroundWindow(w.handle)
            finally:
                _u32.AttachThreadInput(me, fg_thread, False)
            time.sleep(0.8)  # input sent too soon after activation gets swallowed
            if _in_front(w):
                break
            attempt += 1
            if time.monotonic() > deadline:
                raise RuntimeError("could not bring Paint to the front")
            time.sleep(1.2)
    return w


def _in_front(w):
    """Whether a Paint window (main or one of its dialog popups) has the foreground."""
    pid = ctypes.c_ulong()
    _u32.GetWindowThreadProcessId(_u32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value == w.process_id()


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("padding", ctypes.c_byte * 32)]

    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


def _key_event(vk=0, char=None, up=False):
    flags = (4 if char else 0) | (2 if up else 0)  # KEYEVENTF_UNICODE, KEYEVENTF_KEYUP
    event = _INPUT(type=1)
    event.u.ki = _KEYBDINPUT(vk, ord(char) if char else 0, flags, 0, 0)
    _u32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event))
    time.sleep(0.01)


_NAMED_KEYS = {"ESC": 0x1B, "ENTER": 0x0D, "TAB": 0x09}


def _keys(keys):
    """Type into Paint, refusing if anything else has the keyboard so keys never land in the user's
    windows. Understands {ESC} {ENTER} {TAB}, ^ (Ctrl) and + (Shift) before a key, and plain text.
    Independent of the keyboard layout: text goes in as Unicode characters and shortcuts as key codes
    (under an Arabic layout, layout-based typing turned 'F5F1E3' into other letters)."""
    if not _in_front(_paint()):
        raise RuntimeError("Paint is not in front; not sending keystrokes")
    mods, i = [], 0
    while i < len(keys):
        ch = keys[i]
        if ch in "^+":
            mods.append(0x11 if ch == "^" else 0x10)
            i += 1
            continue
        if ch == "{":
            end = keys.index("}", i)
            vk, i = _NAMED_KEYS[keys[i + 1:end]], end + 1
        else:
            vk, i = (ord(ch.upper()) if mods else None), i + 1
        for m in mods:
            _key_event(m)
        if vk is None:
            _key_event(char=ch)
            _key_event(char=ch, up=True)
        else:
            _key_event(vk)
            _key_event(vk, up=True)
        for m in reversed(mods):
            _key_event(m, up=True)
        mods = []


def _find(prop, value, control_type=None, required=True, root=None):
    cond = _uia.iuia.CreatePropertyCondition(getattr(_uia.UIA_dll, f"UIA_{prop}PropertyId"), value)
    if control_type:
        ct = _uia.iuia.CreatePropertyCondition(_uia.UIA_dll.UIA_ControlTypePropertyId, _uia.known_control_types[control_type])
        cond = _uia.iuia.CreateAndCondition(cond, ct)
    for attempt in range(3 if required else 1):  # UI Automation occasionally misses a control for a moment
        base = root.element if root else _uia.iuia.ElementFromHandle(_paint().handle)
        el = base.FindFirst(_uia.tree_scope["descendants"], cond)
        if el:
            return UIAElementInfo(el)
        if required and attempt < 2:
            time.sleep(0.4)
    if required:
        raise RuntimeError(f"Paint control not found: {value}")
    return None


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
    for _ in range(3):  # the tap that opens the menu is sometimes swallowed: wait for it, retry
        pen.stroke([((r.left + r.right) // 2, r.bottom - 8)])  # the menu arrow
        for _ in range(8):
            time.sleep(0.25)
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


_mapping = None  # (scale, origin_x, origin_y): screen = origin + image * scale; reset when the view moves


def _pointer_pixel(sx, sy):
    """The image pixel Paint reports in its status bar while the pen hovers at a screen point."""
    pen.hover(sx, sy)
    time.sleep(0.15)
    texts = _uia.iuia.ElementFromHandle(_paint().handle).FindAll(
        _uia.tree_scope["descendants"],
        _uia.iuia.CreatePropertyCondition(_uia.UIA_dll.UIA_ControlTypePropertyId, _uia.known_control_types["Text"]),
    )
    for name in (texts.GetElement(i).CurrentName for i in range(texts.Length)):
        m = re.fullmatch(r"(\d+), (\d+)px", name or "")
        if m:
            return int(m[1]), int(m[2])
    return None


def _calibrate():
    """Measure exactly where the canvas sits on screen at the current zoom and scroll.
    The scale is the zoom level; the origin is pinned down by hovering the pen at a few points:
    each reported pixel bounds the origin to a window one pixel wide, and the windows intersect."""
    global _mapping
    zoom = UIAWrapper(_find("AutomationId", "ZoomSliderControl")).iface_range_value.CurrentValue
    scale = zoom / 100 * _u32.GetDpiForWindow(_paint().handle) / 96
    rect, _, _ = _canvas()  # the visible part of the canvas
    for _ in range(3):  # hovers right after Paint comes forward can go unseen; try again
        samples = []
        for fx, fy in ((0.06, 0.08), (0.21, 0.27), (0.43, 0.61), (0.67, 0.38), (0.82, 0.79),
                       (0.35, 0.86), (0.58, 0.15), (0.94, 0.93)):
            sx, sy = round(rect.left + fx * rect.width()), round(rect.top + fy * rect.height())
            px = _pointer_pixel(sx, sy)
            if px:
                samples.append((sx, sy, *px))
        pen.leave()
        if len(samples) >= 4:
            # The slider rounds the zoom to whole percent (110.3% shows as 111), so try scales
            # around it and keep those every reading agrees with; use the middle one.
            feasible = []
            for i in range(801):
                k = scale * (0.97 + 0.06 * i / 800)
                bx = [max(s - (v + 1) * k for s, _, v, _ in samples), min(s - v * k for s, _, v, _ in samples)]
                by = [max(s - (v + 1) * k for _, s, _, v in samples), min(s - v * k for _, s, _, v in samples)]
                if bx[0] <= bx[1] and by[0] <= by[1]:
                    feasible.append((k, sum(bx) / 2, sum(by) / 2))
            if feasible:
                _mapping = feasible[len(feasible) // 2]
                return
        time.sleep(0.6)
    raise RuntimeError("could not locate the canvas on screen")


def _to_screen(points):
    rect, w, h = _canvas()
    if _mapping is None:
        _calibrate()
    scale, ox, oy = _mapping
    out = []
    for x, y in points:
        if not (0 <= x < w and 0 <= y < h):
            raise ValueError(f"point ({x}, {y}) is outside the {w}x{h} canvas")
        sx, sy = round(ox + (x + 0.5) * scale), round(oy + (y + 0.5) * scale)
        # canvas-edge pixels can land a fraction past the visible rectangle; pull those back in
        if not (rect.left - 2 <= sx < rect.right + 2 and rect.top - 2 <= sy < rect.bottom + 2):
            raise ValueError(f"point ({x}, {y}) is not visible at the current zoom; zoom out or zoom near it")
        out.append((min(max(sx, rect.left), rect.right - 1), min(max(sy, rect.top), rect.bottom - 1)))
    return out


@tool
def new_canvas(
    width: int = 1000, height: int = 700, discard_unsaved: bool = False, background: str | None = None
) -> str:
    """Start a fresh canvas of the given size in pixels, fitted to the window.
    background (#RRGGBB) tones the whole canvas one color first, like a painter's toned ground.
    That is the only fill this server ever does: everything after it is brush strokes.
    If the current image has unsaved changes this fails unless discard_unsaved is true."""
    if not (1 <= width <= 5000 and 1 <= height <= 5000):
        raise ValueError("width and height must be 1-5000")
    global _tool, _mapping
    _tool = _mapping = None
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
    rect, w, h = _canvas()
    if (w, h) != (width, height):
        raise RuntimeError(f"canvas came out {w}x{h}, not {width}x{height}")
    if background:
        set_color(background)
        _press("Fill")
        c = rect.mid_point()
        pen.stroke([(c.x, c.y)])  # the canvas is blank, so this tones all of it
        _tool = None
        return f"New {w}x{h} canvas ready, toned {background}."
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
    ok_button = (round(cx - 140 * scale), round(cy + 283 * scale))

    def dialog_open():
        # No UI Automation while this dialog is open (it makes Paint hang), so look for its blue OK
        # button in a screenshot instead.
        r, g, b = ImageGrab.grab().getpixel(ok_button)[:3]
        return abs(r - 76) + abs(g - 194) + abs(b - 255) < 40

    got = "?"
    for _ in range(3):  # a tap right after Paint comes to the front is sometimes swallowed
        _press("Edit colors")
        for _ in range(10):
            time.sleep(0.2)
            if dialog_open():
                break
        else:
            continue  # the dialog never opened: tap again, and never type at the canvas
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


@tool
def zoom(level: int | None = None, x: int | None = None, y: int | None = None) -> str:
    """Zoom Paint's view to `level` percent (10-1000), centered on image point (x, y), to paint
    and inspect small details close up. While zoomed in, strokes must lie in the visible part and
    view() shows just that part, magnified. Call with no level to fit the whole canvas again."""
    global _mapping
    _paint()
    _mapping = None
    if level is None:
        _press("Fit to window")
        _calibrate()
        return "Zoomed to fit the whole canvas in the window."
    if not 10 <= level <= 1000:
        raise ValueError("level must be 10-1000 (percent)")
    UIAWrapper(_find("AutomationId", "ZoomSliderControl")).iface_range_value.SetValue(level)
    time.sleep(0.5)
    _, w, h = _canvas()
    if x is not None and y is not None:
        if not (0 <= x < w and 0 <= y < h):
            raise ValueError(f"({x}, {y}) is outside the {w}x{h} canvas")
        _calibrate()
        scale, ox, oy = _mapping
        viewer = _find("AutomationId", "scrollViewer")
        box = viewer.rectangle
        scroll = viewer.element.GetCurrentPattern(_uia.UIA_dll.UIA_ScrollPatternId).QueryInterface(
            _uia.UIA_dll.IUIAutomationScrollPattern
        )
        percents = []
        for target, lo, hi, pct, seen in (
            (ox + x * scale, box.left, box.right, scroll.CurrentHorizontalScrollPercent, scroll.CurrentHorizontalViewSize),
            (oy + y * scale, box.top, box.bottom, scroll.CurrentVerticalScrollPercent, scroll.CurrentVerticalViewSize),
        ):
            if seen >= 100 or pct < 0:
                percents.append(-1)  # this axis doesn't scroll
            else:
                content = (hi - lo) * 100 / seen  # the scrollable content's size on screen
                percents.append(min(100, max(0, pct + (target - (lo + hi) / 2) / (content - (hi - lo)) * 100)))
        scroll.SetScrollPercent(*percents)
        time.sleep(0.4)
        _mapping = None
    _calibrate()
    scale, ox, oy = _mapping
    rect, _, _ = _canvas()
    return (f"Zoomed to {level}%. Visible part of the image: x {max(0, (rect.left - ox) / scale):.0f}-"
            f"{min(w, (rect.right - ox) / scale):.0f}, y {max(0, (rect.top - oy) / scale):.0f}-"
            f"{min(h, (rect.bottom - oy) / scale):.0f}.")


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
    # The dialog fills in its default name a moment after opening; text set before that ends up
    # with the default appended (a save once came out as "02_great_wave.png02_great_wave.png").
    # Set the name, read it back, and only press Enter once it is exactly the path.
    for _ in range(10):
        time.sleep(0.3)
        name.set_edit_text(path)
        time.sleep(0.2)
        if name.window_text() == path:
            break
    else:
        _keys("{ESC}")
        raise RuntimeError("could not enter the file name in the Save As dialog")
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
