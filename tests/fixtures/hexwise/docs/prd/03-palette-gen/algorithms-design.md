# PRD-03: Palette Generation — Design

## Purpose

Generate harmonious color palettes from a seed color using color wheel
relationships. Given one color, produce companions the user can actually use —
colors that are related by design, not by accident. The output should be something
a designer could hand to a developer without embarrassment.

This PRD depends on PRD-01 for parsing the seed color and PRD-02 for contrast
information that may accompany palette output.

## Color Wheel Math

All palette math happens in HSL space. The seed color is converted to HSL first;
palette members are computed as hue rotations; the results are converted back to
sRGB for output.

Hue arithmetic wraps modulo 360. `(14 + 180) % 360 = 194`. `(14 - 30 + 360) % 360 = 344`.

### Harmony Algorithms

**Complementary:** One companion, directly opposite on the color wheel.

```
complement = (hue + 180) % 360
```

Complementary colors create maximum contrast and tend toward vibrant, high-energy
pairings. Two-color palettes. High contrast. Use with intention.

**Analogous:** Two companions on either side of the seed, spaced 30° apart.
Output is three colors: seed, seed+30°, seed-30°.

```
analogous_1 = (hue + 30) % 360
analogous_2 = (hue - 30 + 360) % 360
```

Analogous palettes are cohesive and low-tension. They work well for backgrounds
and UI surfaces where the goal is harmony rather than emphasis.

**Triadic:** Two companions equally spaced around the wheel.
Output is three colors: seed, seed+120°, seed-120°.

```
triadic_1 = (hue + 120) % 360
triadic_2 = (hue - 120 + 360) % 360
```

> "Triadic palettes are heist crews. Each color has a different job, but they
> only work if they showed up together. Analogous palettes are jazz quartets —
> variations on a theme."
> — Palette Jones

Saturation and lightness are preserved from the seed color for all palette
members unless the user explicitly requests variation (future work).

## Output Format

Default output is a list of hex values, one per line. Optional JSON output
(`--json`) wraps each entry in an object with `hex`, `name` (nearest CSS name
if within a threshold), and optionally `contrast_vs_seed` (from PRD-02 math).

Nearest CSS name lookup: if the generated color's sRGB distance to any named
color is within a threshold (to be determined during implementation — likely
Euclidean distance ≤ 5 per channel), include the name. If no named color is
close enough, omit the field rather than reporting a misleading approximation.

## Functional Requirements

**REQ-PAL-001:** Generate a complementary color from any seed color that parses
via PRD-01. Return the seed and complement as a two-color palette.

**REQ-PAL-002:** Generate an analogous palette from a seed color. Return three
colors: seed at hue H, hue H+30°, hue H-30°. Saturation and lightness unchanged.

**REQ-PAL-003:** Generate a triadic palette from a seed color. Return three
colors: seed at hue H, hue H+120°, hue H-120°. Saturation and lightness unchanged.

**REQ-PAL-004:** Output palette as hex values by default. Support `--json` for
structured output including optional CSS name and contrast metadata. All palette
output is to stdout; errors go to stderr.

## Implementation Notes

HSL-to-RGB conversion at the output stage must handle the full range correctly,
including:
- Achromatic colors (S = 0): R = G = B = L. Hue rotation has no effect.
- Hue boundary values: H = 0 and H = 360 are identical; implementation should
  normalize to [0, 360).

Saturation and lightness preservation means palette members will have the same
aesthetic "feel" as the seed (same brightness, same intensity) but different hues.
This is the behavior most color tools use and what users expect.

## Out of Scope for This PRD

- Split-complementary: tracked as future work in `reference.md`
- User-defined spacing (arbitrary hue offsets): future work
- Palette-level contrast checking: out of scope for initial implementation;
  see `reference.md`
