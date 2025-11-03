# Cover Layout Rules (Reusable)

This document records the cover composition rules and the adjustable parameters used by `scripts/local_picker/create_mixtape.py` (function `compose_cover`). The rules are designed to be parameter-driven so you can reuse them across batches.

## Base canvas
- Base rectangle: 7680 x 4320 px (8K, 16:9). All layout fractions are relative to this base.

## Colors and text
- Each issue uses a unique background color (hex). The foreground text is white at 95% opacity.

## Main regions and fractions (configurable via `CoverLayoutConfig`)
- `x_margin_frac` (default 0.08): left/right margin percentage of canvas width.
- `y_margin_frac` (default 0.18): top/bottom vertical margin percentage of canvas height.
- `left_block_width_frac` (default 0.38): width fraction reserved for the left song block (where full tracklist appears).
- `spine_width_frac` (default 0.03): physical spine area fraction used to reserve/align the vertical title.

## Typography and scaling
- `title_size_frac` and `body_size_frac` set base font sizes as fractions of canvas height.
- The code will autoscale the body font so that every track line fits in one line within the left block's allowed width. It reduces font size stepwise until all lines fit or `min_body_px` is reached.
- Title (first occurrence) is placed on the right area and will be shrunk if it overflows its area.
- Title (second occurrence) is rendered vertically on the spine by stacking characters. The code selects a small font size for the spine and ensures single-character width fits the spine.

## Safe areas and behavior
- Left tracklist x-position is `x_margin_frac * canvas_width` (keeps consistent across issues).
- Track names are rendered as `NN. Title` and kept to one line per item.
- If some track names are too long, decrease their frequency/length in the source CSV or increase `left_block_width_frac`.
- Vertical spine title is centered vertically; it uses small font size so it doesn't extend beyond the spine area.

## How to reuse / tune
1. Edit `CoverLayoutConfig` in `scripts/local_picker/create_mixtape.py` to change base fractions or minimum sizes.
2. To test typography quickly, run the script with `--seed <num>` to reproduce the same selection and composition.
3. For different aspect ratios or resolutions, change `canvas_size` in the config and rerun: the layout scales from the base values.

## Example: quick tunables
- To increase left area width: increase `left_block_width_frac` from `0.38` to e.g. `0.45`.
- To allow larger title: increase `title_size_frac` or reduce `x_margin_frac`.
- To make spine thinner: reduce `spine_width_frac` (but remember the vertical title will then become smaller).

## Files touched
- `scripts/local_picker/create_mixtape.py` — updated `compose_cover` and added `CoverLayoutConfig`.
- `output/{id_str}_{title}/` — generated covers saved in episode-specific directories.

If you want, I can add a small CLI flag `--layout-json` to load a JSON file for layout overrides per batch. Would you like that next?