# S02 — Give the Oracle Opinions

A tool that identifies colors is useful. A tool that tells you whether your
color choices are accessible, generates palettes that don't fight each other,
and processes a whole stylesheet's worth of values in one pass — that's the
kind of tool people actually keep installed. Saga 02 turns Hexwise from a
lookup table into a design companion that happens to live in your terminal.

| Field | Value |
|-------|-------|
| Stories | 9 |
| Epics | 3 |
| Total SP | 43 |
| Sprints | 3–5 |

## Team Voices

> **Rusti Ferris:** "WCAG contrast is a formula, not a vibe. Relative
> luminance uses specific coefficients — 0.2126, 0.7152, 0.0722 — after
> sRGB linearization. If we get those constants wrong by even one decimal
> place, we're giving people accessibility advice that's technically a lie."
>
> **Palette Jones:** "Complementary is hue plus 180 degrees, sure, but a
> good palette isn't just math. We need to display these relationships so
> people can feel whether the combination works, not just read that it
> passed a ratio check. The terminal is our canvas, and I refuse to waste it
> on a table of numbers."
>
> **Checker Macready:** "Batch mode is where the interesting failures live.
> One bad line in a hundred-line input — does it poison the whole run? Does
> the error message tell you which line? Does stdin handle a pipe that closes
> mid-read? These are the questions I will be answering, whether the code
> likes it or not."

## Epic Index

| Epic | Name | Stories | SP |
|------|------|---------|-----|
| E-0201 | Contrast Checking | 3 | 15 |
| E-0202 | Palette Generation | 3 | 15 |
| E-0203 | Batch Processing | 3 | 13 |

## Sprint Allocation

| Sprint | Stories | SP |
|--------|---------|-----|
| Sprint 3 | US-0201, US-0202, US-0203 | 15 |
| Sprint 4 | US-0204, US-0205, US-0206 | 15 |
| Sprint 5 | US-0207, US-0208, US-0209 | 13 |

## Dependency Graph

```
                  ┌── US-0204 (complementary) ──┐
US-0201 (lum) ── US-0202 (ratio) ── US-0203 (WCAG)     ├── US-0206 (display)
                                     US-0205 (analog) ──┘
                                                              │
                  US-0207 (stdin) ── US-0208 (batch out) ── US-0209 (errors)
```

## Release Gate Checklist

- [ ] WCAG contrast ratios match reference implementation for all test pairs
- [ ] Palette generation produces mathematically correct hue rotations
- [ ] Batch mode processes 1000+ lines without memory growth
- [ ] Broken input mid-stream does not crash or corrupt output
- [ ] All three output modes (human, JSON, batch) produce consistent results
- [ ] `cargo test` passes with zero warnings under `clippy::pedantic`
