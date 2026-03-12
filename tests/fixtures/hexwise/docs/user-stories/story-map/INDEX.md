# Story Map — Hexwise

Five activities, two releases, one oracle that got really into color theory.

## Activities

### 1. Parse Colors

The front door. Accept color values in every format a reasonable human might
use, and a few formats only Checker would think to try.

| Release | Story | Title | SP |
|---------|-------|-------|----|
| R1 | US-0101 | Parse hex color input | 3 |
| R1 | US-0102 | Parse RGB tuple input | 5 |
| R1 | US-0103 | Parse HSL color input | 5 |
| R1 | US-0104 | Auto-detect color format | 3 |

### 2. Convert & Compute

The math layer. Transform between color spaces, compute luminance, and
calculate contrast ratios with the precision that accessibility standards
demand.

| Release | Story | Title | SP |
|---------|-------|-------|----|
| R1 | US-0103 | HSL-to-RGB conversion (part of parsing) | — |
| R2 | US-0201 | Relative luminance calculation | 5 |
| R2 | US-0202 | Contrast ratio calculation | 5 |

### 3. Name & Describe

The personality layer. Match colors to names, suggest corrections for typos,
and describe colors in language that makes a hex code feel like something.

| Release | Story | Title | SP |
|---------|-------|-------|----|
| R1 | US-0105 | CSS named color database | 5 |
| R1 | US-0106 | Color name lookup | 3 |
| R1 | US-0108 | Synesthetic color descriptions | 5 |

### 4. Generate Palettes

The opinion layer. Given one color, produce harmonious companions using
color wheel relationships — and tell the user whether their choices will
pass accessibility review.

| Release | Story | Title | SP |
|---------|-------|-------|----|
| R2 | US-0203 | WCAG compliance verdict | 5 |
| R2 | US-0204 | Complementary color generation | 5 |
| R2 | US-0205 | Analogous and triadic palettes | 5 |
| R2 | US-0206 | Palette display | 5 |

### 5. Format & Output

The presentation layer. Everything the user actually sees — from single-color
display to batch processing to error messages that respect the user's time.

| Release | Story | Title | SP |
|---------|-------|-------|----|
| R1 | US-0107 | Formatted color display | 5 |
| R2 | US-0207 | Read colors from stdin | 5 |
| R2 | US-0208 | Batch output formatting | 5 |
| R2 | US-0209 | Batch error handling | 3 |

---

## Release Summary

| Release | Name | Activities Covered | Stories | SP |
|---------|------|-------------------|---------|-----|
| R1 | Core | 1, 2 (partial), 3, 5 (partial) | 8 | 34 |
| R2 | Toolkit | 2 (partial), 4, 5 (partial) | 9 | 43 |
