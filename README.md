# ms-paint-mcp

MCP server that lets an AI paint in Windows 11 Paint by driving the real app: it finds controls through UI Automation and draws with the mouse.

## Setup

Needs Windows 11 Paint and [uv](https://docs.astral.sh/uv/).

```
claude mcp add ms-paint -- uv run --directory C:\path\to\ms-paint-mcp python -W ignore server.py
```

## Tools

| Tool | What it does |
|------|--------------|
| `new_canvas(width, height, discard_unsaved=False)` | Fresh canvas, fitted to the window. Refuses if Paint has unsaved changes. |
| `set_color(hex_color)` | Sets the drawing color. |
| `stroke(points, tool="brush"\|"pencil"\|"eraser", size)` | One drag through image-pixel points. |
| `shape(kind, x1, y1, x2, y2)` | Any Paint shape outline (Oval, Rectangle, Heart, ...). |
| `fill(x, y)` | Flood fill. |
| `undo()` | Ctrl+Z. |
| `view()` | Screenshot of the canvas. |
| `save(path)` | Saves a new `.png`. |

## Caveats

- It uses the real mouse and keyboard: hands off while it paints, and Paint stays in front.
- Tested on Paint 11.2605 at 100% display scaling. `set_color` finds the hex box by its position in the Edit colors dialog, because any UI Automation query while that dialog is open hangs Paint.

`uv run smoke_test.py` exercises every tool against real Paint (it discards the current image).
