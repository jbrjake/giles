# PRD-01: Color Parsing & Conversion — Design

## Purpose

Parse and normalize color inputs from multiple formats into a canonical internal
representation. This is the front door: every other capability in Hexwise depends
on parsing working correctly. Color input that fails silently here will produce
wrong output everywhere downstream.

## Internal Representation

All supported formats convert to a single canonical form: an sRGB u8 triple `(r, g, b)`
where each channel is an integer in [0, 255]. This is the only form the rest of
the system sees. Conversion happens at parse time, not at use time.

Choosing sRGB u8 as the canonical form is a deliberate tradeoff: it is lossy for
HSL inputs (rounding occurs), but it is universal, cheap to store, and easy to
reason about. Perceptual color spaces (OKLab, Lab) are future work.

> "HSL is how humans think about color. RGB is how computers think about color.
> We need to speak both languages fluently."
> — Palette Jones

## Format Support Matrix

| Format | Example | Notes |
|--------|---------|-------|
| 6-digit hex | `#FF5533` or `FF5533` | `#` prefix optional |
| 3-digit hex | `#F53` | Expands to `#FF5533` |
| RGB function | `rgb(255, 85, 51)` | Values 0–255, whitespace-tolerant |
| HSL function | `hsl(14, 100%, 60%)` | H: 0–360, S/L: 0–100% |
| CSS named color | `coral` | Case-insensitive, full CSS Level 4 list |

## Auto-Detection Algorithm

Format is determined by inspection, not by an explicit flag from the caller. The
detection order is:

1. If the value starts with `#` or matches `[0-9A-Fa-f]{6}` or `[0-9A-Fa-f]{3}`,
   treat as hex.
2. If the value starts with `rgb(`, parse as RGB function syntax.
3. If the value starts with `hsl(`, parse as HSL function syntax.
4. Otherwise, attempt a case-insensitive lookup in the CSS named color table.
5. If none match, return a structured parse error.

This order is chosen so that ambiguous short strings (e.g. `fed`) are interpreted
as hex before attempting a name lookup, which is the expectation from the user's
perspective.

## Functional Requirements

**REQ-PAR-001:** Parse 6-digit hex with or without `#` prefix. Values must be
in range [00–FF] per channel.

**REQ-PAR-002:** Parse 3-digit hex shorthand. Each digit is doubled: `#F53`
expands to `#FF5533`.

**REQ-PAR-003:** Parse `rgb(R, G, B)` syntax. R, G, B are integers in [0, 255].
Whitespace around values and after the opening parenthesis is ignored. Values
outside [0, 255] are a parse error, not a clamp.

**REQ-PAR-004:** Parse `hsl(H, S%, L%)` syntax. H is a float in [0, 360),
S and L are percentages in [0, 100]. Convert to sRGB u8 at parse time using
standard HSL-to-RGB math. Hue values ≥ 360 wrap modulo 360.

**REQ-PAR-005:** Look up CSS named colors case-insensitively. The lookup table
covers the full CSS Color Level 4 named color list (148 names). Whitespace in
input names is not normalized — `coral reef` is not `coralreef`.

**REQ-PAR-006:** Auto-detect input format without an explicit format flag from
the caller. Detection follows the algorithm above. A failed detection returns
a structured error that names the input and lists the formats that were tried.

## Non-Functional Requirements

**REQ-PAR-NF-001:** Parse any single color in under 1ms on modern hardware.
The named-color lookup table is a compile-time constant; no file I/O occurs at
parse time.

## Out of Scope for This PRD

- Alpha channel (RGBA, HSLA): tracked as a future work item in `reference.md`
- CMYK, Lab, OKLab: future work
- Color correction or gamut mapping: out of scope entirely
