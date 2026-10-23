# Lessons learned

What painting in Windows 11 Paint through this server has taught so far. The server's `painting_guide` tool returns this file, so an AI client can read it before painting in whatever style the user asks for.

## How to paint

- **Brush strokes only.** No fills or shapes (the server has neither). Flood fill only works on a region that is one even color, which forces an unnatural painting order. One mis-aimed fill point also recolored a whole dress in the first Mona Lisa.
- **The one fill allowed is a toned ground.** If the canvas should start as a color, tone the blank canvas with `new_canvas(background=...)` before painting, as a painter primes a canvas. Nothing else is ever filled.
- **Fix mistakes on the same canvas, with the brush.** Never start a new painting to correct one: paint over each mistake locally, as a painter would (Great Wave correction pass). Paint the area back in its surrounding colors, then redraw what the correction covered, such as outlines.
- **Back to front:** background, distant scenery, foreground, main subject, shadows, highlights, fine details. Later strokes simply paint over earlier ones, as on a real canvas.
- **Broad to fine.** Block in large areas with big brushes (30-60 px), then switch to smaller ones (2-12 px) near edges and for details.
- **Every edge must be smooth on its own.** Never rely on a later line or layer to hide a ragged rim.
- **Cover an area from the outside in** (`cover()` in `challenges/brushlib.py`):
  1. Cut in the edge with one continuous small-brush stroke (about 5 px) whose outer side runs exactly along the outline.
  2. Lay rings that follow the outline, the brush growing about 2.4× each time up to the big size. Each ring's outer side sits on the previous ring's center line.
  3. Fill the core with parallel rows (spaced 0.55 × size) as continuous zigzags, their centers inside the last ring.

  Rows alone leave a scalloped rim, because round tips stop at different depths. Along curves they also leave white slivers where the outermost rows shrink to dots. Measured on test shapes, the rings removed both.
- **Shrink the outline by a true perpendicular offset** to place strokes. Insetting row ends horizontally lets tips poke out on slanted edges.
- **Let areas that touch the canvas edge run past it**, otherwise the edge looks scalloped.
- **Draw dividing lines last** (Mondrian), but the blocks under them still get clean edges.
- **Check the canvas with `view` after each stage** and fix mistakes locally, not by repainting large areas.
- **Every color change opens Paint's color dialog (about 3 s)**, so group strokes by color.

## Know the brushes

Measured with one straight black stroke at size 20, full opacity:

| Brush type | Painted width | Edge | Coverage | Use for |
|------------|---------------|------|----------|---------|
| Brush | 21 px | perfectly smooth | solid | flat areas, clean edges, lines |
| Calligraphy brush | 15 px (direction-dependent) | smooth | solid | lines that swell and thin |
| Calligraphy pen | 15 px (direction-dependent) | smooth | solid | crisp outlines (ukiyo-e) |
| Airbrush | sparse spray | soft | very light per pass | soft shading in many passes |
| Oil brush | 31 px | rough (±2.5 px) | nearly solid | textured, visible brushwork |
| Crayon | 12 px | rough (±2.8 px) | grainy | expressive texture |
| Marker | 24 px | smooth | about 75% (see-through) | glazes with a clean edge |
| Natural pencil | 1 px | slightly rough | light gray | sketch lines |
| Watercolor brush | 22 px | soft, uneven | about 75%, textured | washes and blends |

- **`size` is the painted width in pixels for the Brush.** Paint's own size slider paints true up to about 24, then much wider (slider 50 paints 78 px, 90 paints 250 px). The server converts through a measured curve.
- **`opacity` 1-100 lets a stroke glaze over what is beneath.** Watercolor at 40% over white came out light blue.

## Style playbook

| Style | Approach | Status |
|-------|----------|--------|
| Geometric abstraction (Mondrian) | Brush at full opacity; flat blocks in wide horizontal rows; black lines thickest first, ending inside the line they meet | Verified (challenge 1) |
| Ukiyo-e woodblock (The Great Wave) | Flat color areas built outside-in; Calligraphy pen for the key-block outlines; stripes that follow the wave's curve; foam as tapered claws (a light blue rim, then white on top, thinning to the tip) with droplets; shadows as see-through glazes, not solid dark bars; Prussian blue, indigo, cream sky | Tried (challenge 2), in review |
| Post-impressionism (The Starry Night) | Oil brush, size 6-12; short directional dabs following the swirls, never flat areas; layer yellows over blues; outline shapes with dark strokes | Plan |
| Impressionism (Impression, Sunrise) | Watercolor brush or Airbrush at opacity 30-60; broken horizontal strokes; build color by glazing one hue over another; the sun's reflection as short orange dashes | Plan |
| Expressionism (The Scream) | Long flowing curved strokes with Oil brush or Crayon; saturated oranges against blues; simplified figure; strong diagonal composition | Plan |
| Baroque portrait (Girl with a Pearl Earring) | Dark background first; model the face with low-opacity Airbrush from a single light source; small brushes for eyes and lips; the pearl's highlight last | Plan |
| Renaissance full scene (The Birth of Venus) | Plan the composition on a grid; many thin layers; soft edges; pale palette; measure figure proportions | Plan |

## Strategy

The goal is to match the reference's proportions, shapes, colors, light and texture as closely as possible, while keeping every mistake correctable. Accuracy and recoverability come before speed; efficiency (few wasted strokes and color changes) and consistency (one coordinate system, one palette) follow.

**This AI has a camera.** `view()` shows the canvas and `zoom()` gives close-ups, so it never has to paint blind from a fixed plan. It observes, acts and checks in a loop.

### The sequence

1. **Analyze and plan.** Split the subject into regions (background, distant scenery, body, clothing, hands, face, hair, fine details). Fix the coordinates of the key landmarks, and plan the layers and the palette (one color change costs about 3 s).
2. **Block in the large shapes.** Tone the ground if the painting has one, then lay in the broad darks and lights. No small details yet.
3. **Develop form and color.** Model volumes in the landscape, fabric, hands and face with thin layers. Use low-opacity glazes for soft transitions, such as sfumato. Keep comparing the whole painting rather than perfecting one feature.
4. **Refine and validate.** Add crisp edges, highlights and final value adjustments. Check at several scales: the whole canvas with `view()`, details with `zoom()`. Stop when more work is more likely to hurt than help.

### Rules

| # | Rule | In this project |
|---|------|-----------------|
| 1 | Large before small | Never refine details while the major proportions are wrong. |
| 2 | Observe before acting | Look at the canvas (`view`, `zoom`) before every meaningful sequence of strokes. |
| 3 | Protect correct regions | Don't repaint areas that are already right; corrections stay local. |
| 4 | Plan the value order | Choose light-to-dark or dark-to-light per area, by opacity and brush, not one rigid order. |
| 5 | Limit stroke risk | In sensitive areas (faces, hands, edges) use short strokes, small brushes and a close zoom. |
| 6 | Recalibrate | The server re-measures the canvas mapping after every zoom; check the color swatch after every pick. |
| 7 | Correct causes | Fix the wrong proportion or color itself rather than repeatedly hiding its symptoms. |
| 8 | Respect the medium | Know each brush's width, edge and opacity (see "Know the brushes") before relying on it. |
| 9 | Test when unsure | Try a technique on a scratch canvas, or make one stroke and undo it, before committing a whole area. |
| 10 | Know when to stop | Don't make a change unless its expected improvement outweighs its risk. |

**Global consistency:** no local improvement is acceptable if it makes the painting as a whole worse. An eye painted sharper or brighter than the rest of the face makes the portrait less faithful, not more.

### Choosing the next action

Before each stroke sequence, weigh three things: the expected gain in quality, the risk of damaging what is already right, and the cost in strokes and color changes. Take the action with the best positive balance, not necessarily the one that fixes the most obvious error. If nothing is clearly worth doing, stop.

### When things go wrong

| Situation | Response |
|-----------|----------|
| Wrong color | `set_color` checks the swatch and retries; if it still fails, stop and look before painting on. |
| An unintended stroke | Look at the damage. Undo if it was the last action; otherwise paint over it locally. Never restart the painting. |
| Paint isn't in front, or something covers it | Stop. The server refuses keystrokes then; get Paint back in view before the next stroke. |
| The view moved (zoom, scroll) | The mapping is recalibrated after `zoom()`; never reuse old screen positions. |
| A dialog is stuck open | Close it with Escape; never query UI Automation while the color dialog is open. |
| A proportion turns out wrong late | Weigh whether fixing it improves the whole painting enough to justify the disruption. |
| Repeated corrections keep making an area worse | Undo if possible, change technique (brush, size, opacity, stroke direction), or leave that area alone. |
| Unsure what a stroke will do | Make one small test stroke, look, then continue or undo. |

### The loop

```
while not finished:
    look at the canvas (view, zoom)
    compare it with the reference at several scales
    list the candidate actions that would reduce the biggest errors
    drop the risky ones (they could damage correct areas)
    pick the action with the best gain against risk and cost; if none, stop
    paint it
    look again to verify, and update the plan
```

## From the challenges

### The Great Wave (challenge 2)

- **Correct on the same canvas, in passes.** The wave was painted once, then corrected three times with the brush: a fix pass, a detail pass in phases, and pixel-level cleanups. Each pass is its own script, and the GIF continues across all of them.
- **Look between phases at a close zoom.** Every phase was checked at 200-400%; several mistakes were only visible there.
- **Curves offset from a tight curve loop back on themselves.** Stripes offset from the crest ran off the wave and dangled into the hollow, twice. Trim them before the tight part, or clip each one against the shape it belongs to with a point-in-polygon test.
- **Painting over an object means painting over its outline too.** The pen outline sits on and just outside the shape, so covering only the inside left ghost lines. Cover the outline's path, clipping its segments at boundaries rather than dropping points: dropped points leave the pieces that cross the boundary.
- **Shadows are glazes, not bars.** A solid near-black stroke under the crest read as an object. Two see-through layers (35% and 45%), darkest nearest the foam, read as depth.
- **Opacity persists between strokes.** Paint keeps the last opacity, so always set it explicitly (the helpers default to 100).
- **Irregularity matters.** Claws of even length and spacing looked like a comb; varied lengths, angles and curl looked like foam.
- **Tapered marks are overlapping pieces of decreasing size**, rim color first for all of them, then the light color on top: two color changes instead of two per mark.
- **Pixel-level cleanup:** find stray pixels by color (allowing anti-aliased blends between the expected colors), chain neighbors into short paths, paint over exactly those. Always mask the search to the intended region: an unmasked box counted the hollow's cream as strays and painted a blue block into it.
- **Shapes thinner than the brush's inner rings don't fill.** A thin boat hull kept a streak of the color beneath; make such shapes thicker or paint them as one stroke.
- **Long phases make huge GIFs** (24 MB here). Keep every few frames and encode with one shared palette and no dithering: 941 frames came down to 236 and 4 MB.

### The Great Wave, second attempt

The first version was rejected as a solid blue wall with mechanical foam and stick boats, and painted again from scratch.

- **Paint in dependency order:** silhouette, then major forms, then shading, then foam, then details. A stroke waits until everything it depends on is right; detailed foam on a wrong crest is wasted.
- **Preview before painting.** `canvas(..., preview=True)` simulates every stroke in an image in about 2 seconds, against a phase that takes 10-30 minutes in Paint. The composition went through four previews before any paint went on.
- **Water is layered masses, not one silhouette.** Overlapping tongues of water, each with a foam edge and a dark seam; secondary waves in a lighter blue; each mass casting shadow on the one behind it.
- **Water needs texture.** Depth glazes, hundreds of thin flow lines following each mass's curve, broken edges and foam lace. Without them, even layered shapes read as flat cut-outs.
- **Foam is fingers, not loops.** A dozen claws turning with the curl's rotation, each splitting into a few short claws near its tip. Repeating the same small curl looks mechanical; random directions look like a mop.
- **Cast shadows only fall on water**, never on sky or the far sea.
- **Clip shapes to the canvas before laying rings.** Clamping off-canvas points onto the edge pulled rings sideways into blocky "feet" past the waves' outlines.
- **Sharp tips need the full inset.** Capping how far a corner point moves inward left the brush poking out of the wave's lip as a round bump.
- **Color-selective repair:** fix a spill by repainting only the pixels of the wrong color in the area, each with the color that belongs behind it. Boats and foam in the same area stay untouched.
- **Recording holds frames in memory.** A long phase captured over a thousand full-resolution frames; that is gigabytes, and contributed to the run being stopped for low memory. Shrink frames as they are captured, and thin the GIF out at the end (2,057 frames came down to 258 and 7 MB).

### Paint quirks found on the way

- **The zoom slider rounds to whole percent** (110.3% shows as 111), so the canvas scale is worked out from the pen hovers, not taken from the slider.
- **A swallowed tap can mean the color dialog never opened.** `set_color` checks for the dialog's OK button in a screenshot before typing, so keys never land on the canvas.
- **The keyboard layout matters.** Under an Arabic layout, layout-based typing turned "F5F1E3" into other letters. Text is now sent as Unicode characters and shortcuts as key codes.
- **The Save As dialog fills in its default name a moment after opening.** Typing too soon produced `02_great_wave.png02_great_wave.png`. `save` reads the name back before pressing Enter, and the challenge helper never deletes the old PNG until the new one is written.
- **UI Automation occasionally misses a control for a moment**, and the brush menu sometimes doesn't open on the first tap; both are retried.
- **When another window takes the foreground briefly**, the server waits up to 30 seconds before giving up.

## Zoom

- **`zoom(level, x, y)` zooms Paint in on a point**, so details can be painted and inspected close up. Brush size stays in image pixels at any zoom.
- **Paint's status bar shows the image pixel under a hovering pen.** The server hovers at a few points after each zoom; every reading narrows where the canvas sits, and together they place it to a fraction of a pixel.
- **Hovers right after Paint comes to the front can go unseen**, so calibration retries before giving up.

## Working method

- **Measure, don't assume.** Test a technique on simple shapes and count pixels (paint spilled outside the outline, white gaps inside) before using it in a painting. That's how the brush-size curve and the scalloped rims were found.
- **Rule out wrong explanations.** Scalloped edges first looked like Paint smoothing the pen path at sharp turns. Pinning the turns changed nothing; the real cause was brush width.
- **Paint in stages and look at each one.** A whole painting in one blind run produced the Mona Lisa's olive dress and unfilled corners; staged runs with a view in between catch that early.

## How Paint behaves

### Input

- **Paint ignores input while in the background.** Mouse and key messages posted straight to its windows do nothing; only real system input works, and that lands on whatever window is on top. So Paint must be in front while it paints.
- **The synthetic pen draws without touching the mouse.** Simulated mouse input works but moves the user's real cursor. pywinauto's mouse drags don't register in Paint at all.
- **Pen input hits whatever is on top at that spot.** The click-through overlay is fine, but an always-on-top window covering Paint would get the taps.
- **Pen pressure scales brush width.** At half pressure widths came out inconsistent, so the pen always presses fully.
- **Getting the foreground:** SetForegroundWindow fails from a background process unless the thread first attaches to the foreground thread's input. Even then it occasionally fails, so retry, and as a last resort minimize and re-maximize Paint.
- **The first input right after Paint comes to the front is sometimes swallowed.** Wait about 0.8 s after activating, and retry color picks and Ctrl+E.
- **Launching Paint always takes the focus**, even when asked to start without activating.
- **pywinauto moves the mouse:** `set_focus` and `type_keys` push the cursor off-screen. The server brings Paint forward itself and types only through its own guarded helper.

### Controls

- **Toolbar tool buttons are toggle buttons that ignore UI Automation.** Invoke, Toggle and the default action all do nothing, so the server taps them with the pen. Plain buttons such as Undo and "Don’t save" do accept Invoke.
- **Brush types live in a separate pop-up window**, opened by the arrow under the Brushes button. Find its menu items among the top-level windows of Paint's process.
- **The Size and Opacity sliders only exist while a drawing tool is active.** After Ctrl+A, Paint switches to Select and they disappear.
- **Ctrl+A leaves a whole-canvas selection.** Drags then move the selection instead of painting; Escape clears it.
- **"Don’t save" uses a curly apostrophe.** Match it by automation id (`SecondaryButton`), not by name.
- **Use native UI Automation searches.** pywinauto's Python-side tree walk is slow and once hung Paint; native FindFirst and FindAll take about 0.05 s.
- **Querying UI Automation while the Edit colors dialog is open hangs Paint.** `set_color` clicks the hex box by its offset from the dialog's center instead.
- **With mouse input, closing the color dialog stamped a dot where the pointer was.** The pen leaves no mark.

### Canvas and files

- **A new image starts at the last size used** (once 1149×3120). `new_canvas` sets the size explicitly and fits the canvas to the window, and coordinates are mapped through the canvas's on-screen rectangle.
- **Save As remembers the last file type.** Paint saves in that format whatever the extension (a `.png` once came out as HEIF), so `save` picks PNG explicitly.
- **PrintWindow can capture Paint while it's covered**, but that doesn't help: input still can't reach it.

## Recording GIFs

- **The overlay is hidden from screen capture**, so the recorder draws the border, label and pen cursor into each frame, matching what you see live.
- **Grab frames on a separate thread without UI Automation.** Read the window rectangle once before recording starts.
- **Color picks cover the canvas for about 3 s.** Keep one frame of the dialog per pick, not the whole wait.
- **0.4 s between grabs, played at 70 ms a frame**, is about 6× speed. Hold the last frame for 2.5 s. A full-window GIF of a challenge is about 1-2 MB.
