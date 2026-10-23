# ms-paint-mcp

MCP server that paints in Windows 11 Paint by driving the real app. See README.md for tools and setup, and LESSONS.md for what painting here has taught (the server's `painting_guide` tool returns it).

## Layout

- `server.py`: the MCP tools. Finds Paint controls through UI Automation; taps and paints with the pen.
- `pen.py`: synthetic pen input (InjectSyntheticPointerInput), so the user's mouse never moves.
- `overlay.py`: orange border, "Claude is drawing" label and pen cursor while a tool runs; hidden from screen capture.
- `challenges/`: one script per painting challenge, plus `brushlib.py` (brush-only painting helpers) and `record.py` (GIF recorder).
- `gallery/`: older paintings kept in the repo.

## Commands

- `uv run smoke_test.py`: drives real Paint through every tool and checks pixels. It discards Paint's open image; leave the mouse still.
- `uv run challenges/01_mondrian.py`: paints a challenge and writes its `.png` and `.gif` next to the script.

## Painting rules

- **Brush strokes only.** Never use fills, flood fills, shape tools or filled shapes; the server deliberately has none. Every colored area is built from brush strokes, as on a real canvas.
- **Paint back to front:** background, distant scenery, foreground, main subject, shadows, highlights, fine details.
- **Broad to fine:** large brushes for coverage, then smaller ones near edges and for details.
- **Cover areas with continuous, parallel, overlapping strokes**, not dots. Use efficient paths, but never at the cost of quality.
- **Edges must be perfectly smooth.** Cut in each area's edge with a small brush first, then fill the inside with rows whose round tips stop inside that edge. Never rely on a later line or layer to hide a ragged edge.
- **Check the canvas with `view` between stages** and fix mistakes locally, not by repainting large areas.
- **Pick brush type, size and opacity to suit the style** (see LESSONS.md), and record what each challenge teaches there.

## Saving work

- Save every painting and a GIF of it being painted inside this repo, named after the image (`challenges/NN_name.png` + `.gif`). Never save to the user's Pictures folder.
- GIFs show the whole Paint window with the overlay drawn in.

## Challenge workflow

- Paint the challenges in README order, one at a time. The user reviews each one; fix what they flag until they approve, then mark it done in README and commit.

## Paint gotchas

- Paint ignores background input, so it must be in front while painting. Bring it forward without moving the mouse (`_paint()`), and only send keystrokes through `_keys()`, which refuses unless Paint has the foreground.
- Never use pywinauto's `set_focus`, `type_keys` or mouse functions: they move the user's mouse.
- Never query UI Automation while Paint's Edit colors dialog is open; it hangs Paint.

## Git

- No Claude co-author lines or other Claude attribution in commits or PRs.
- Commit in small, logical steps. History rewrites and force pushes only when the user asks.
