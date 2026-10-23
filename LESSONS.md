# Lessons learned

What painting in Windows 11 Paint through this server has taught so far. The server's `painting_guide` tool returns this file, so an AI client can read it before painting in whatever style the user asks for.

## How to paint

- **Brush strokes only.** No fills or shapes (the server has neither). Flood fill only works on a region that is one even color, which forces an unnatural painting order. One mis-aimed fill point also recolored a whole dress in the first Mona Lisa.
- **Back to front:** background, distant scenery, foreground, main subject, shadows, highlights, fine details. Later strokes simply paint over earlier ones, as on a real canvas.
- **Broad to fine.** Block in large areas with big brushes (30-60 px), then switch to smaller ones (2-12 px) near edges and for details.
- **Cover areas with parallel rows of overlapping strokes**, spaced about 0.55 × brush size, as one continuous zigzag per area. `challenges/brushlib.py` has `cover()` for this.
- **Brush tips are round.** Keep the first and last row a brush radius inside the edge, or color spills past it. Let areas that touch the canvas edge run past it, otherwise the edge looks scalloped.
- **Draw dividing lines last.** Paint blocks up to the line's center, then paint the line over the seam (Mondrian).
- **Check the canvas with `view` after each stage** and fix mistakes locally, not by repainting large areas.
- **Every color change opens Paint's color dialog (about 3 s)**, so group strokes by color.

## Style playbook

Brush types are Paint's own: Brush, Calligraphy brush, Calligraphy pen, Airbrush, Oil brush, Crayon, Marker, Natural pencil, Watercolor brush. `opacity` 1-100 lets a stroke glaze over what is beneath.

| Style | Approach | Status |
|-------|----------|--------|
| Geometric abstraction (Mondrian) | Brush at full opacity; flat blocks in wide horizontal rows; black lines thickest first, ending inside the line they meet | Verified (challenge 1) |
| Ukiyo-e woodblock (The Great Wave) | Flat color bands; Calligraphy pen for crisp outlines that swell and thin; foam as many small hooked white strokes along the crest; Prussian blue, indigo, cream sky | Plan |
| Post-impressionism (The Starry Night) | Oil brush, size 6-12; short directional dabs following the swirls, never flat areas; layer yellows over blues; outline shapes with dark strokes | Plan |
| Impressionism (Impression, Sunrise) | Watercolor brush or Airbrush at opacity 30-60; broken horizontal strokes; build color by glazing one hue over another; the sun's reflection as short orange dashes | Plan |
| Expressionism (The Scream) | Long flowing curved strokes with Oil brush or Crayon; saturated oranges against blues; simplified figure; strong diagonal composition | Plan |
| Baroque portrait (Girl with a Pearl Earring) | Dark background first; model the face with low-opacity Airbrush from a single light source; small brushes for eyes and lips; the pearl's highlight last | Plan |
| Renaissance full scene (The Birth of Venus) | Plan the composition on a grid; many thin layers; soft edges; pale palette; measure figure proportions | Plan |

## How Paint behaves

- **Paint ignores input while in the background.** Posted mouse and key messages do nothing, so Paint must be in front while it paints.
- **Querying UI Automation while the Edit colors dialog is open hangs Paint.** `set_color` clicks the hex box by its offset from the dialog's center instead.
- **pywinauto moves the mouse:** `set_focus` and `type_keys` push the cursor off-screen. The server brings Paint forward itself and types only through its own guarded helper.
- **Pen pressure scales brush width.** At half pressure, size 30 painted about 15 px, so the pen always presses fully.
- **The first input right after Paint comes to the front is sometimes swallowed.** The server waits after activating and retries color picks and Ctrl+E.
- **Save As remembers the last file type.** Paint saves in that format whatever the extension (a `.png` once came out as HEIF), so `save` picks PNG explicitly.
- **The overlay is hidden from screen capture**, so the GIF recorder draws the border, label and pen cursor into each frame itself.
