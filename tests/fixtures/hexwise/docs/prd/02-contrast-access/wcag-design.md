# PRD-02: Contrast & Accessibility — Design

## Purpose

Check foreground/background color pairs against WCAG 2.1 accessibility standards
and report whether they pass. This is not a suggestion engine — it is a compliance
checker. The output is a verdict: pass or fail, with the actual ratio and the
threshold it was compared against.

Downstream use: palette generation (PRD-03) will use these calculations to flag
generated palettes that fail accessibility review. The math in this PRD is the
shared foundation.

## WCAG 2.1 Relative Luminance

Relative luminance is calculated from a linearized sRGB value. The two-step
process is:

**Step 1: Linearize each channel.** Given a channel value C in [0, 1] (divide
the u8 value by 255 first):

```
if C <= 0.04045:
    C_linear = C / 12.92
else:
    C_linear = ((C + 0.055) / 1.055) ^ 2.4
```

**Step 2: Apply luminance weights.**

```
L = 0.2126 * R_linear + 0.7152 * G_linear + 0.0722 * B_linear
```

The coefficients (0.2126, 0.7152, 0.0722) are the ITU-R BT.709 primaries. They
encode the fact that the human eye is most sensitive to green, less sensitive to
red, and least sensitive to blue. These values are normative in WCAG 2.1 and must
not be approximated.

## Contrast Ratio

Given luminances L1 and L2 where L1 >= L2:

```
ratio = (L1 + 0.05) / (L2 + 0.05)
```

The 0.05 offset accounts for ambient light reflecting off a display. It prevents
the ratio from becoming infinite when one color is pure black (L = 0).

Result is a float. Round to two decimal places before comparing against thresholds.

> "The edge case is exactly 4.5:1. We round to two decimal places BEFORE
> comparing. Checker will test this."
> — Checker Macready

## WCAG 2.1 Thresholds

| Level | Text Size | Minimum Ratio |
|-------|-----------|---------------|
| AA | Normal text | 4.5:1 |
| AA | Large text (18pt+ or 14pt+ bold) | 3.0:1 |
| AAA | Normal text | 7.0:1 |
| AAA | Large text | 4.5:1 |

"Large text" is defined by WCAG as 18pt regular or 14pt bold (approximately
24px and 18.67px at 96dpi). Hexwise does not know the font size of the consumer's
terminal, so large-text thresholds are reported as informational alongside the
normal-text verdict.

## Functional Requirements

**REQ-CON-001:** Calculate relative luminance from any color that parses via
PRD-01. Luminance is a float in [0.0, 1.0]. Black (`#000000`) yields 0.0; white
(`#FFFFFF`) yields 1.0.

**REQ-CON-002:** Calculate contrast ratio between two colors. Identify which
luminance is L1 (the lighter) and which is L2 (the darker) automatically — the
caller does not specify order.

**REQ-CON-003:** Report WCAG AA and AAA compliance for normal text. Output
includes the actual ratio rounded to two decimal places, the threshold, and
a pass/fail verdict for each level.

**REQ-CON-004:** Report WCAG AA compliance for large text using the 3.0:1
threshold. This is reported separately from normal-text results and labeled
clearly so callers understand which threshold applies.

## Implementation Notes

The linearization threshold (0.04045) and the exponent (2.4) are normative WCAG
values. Do not use 0.03928 (an older, slightly incorrect value that appears in
some implementations). The correct value is 0.04045 per WCAG 2.1 errata.

Luminance calculation must happen in linear light (after the sRGB linearization
step). Applying the weighted sum to raw u8 channel values without linearizing
first is a common error that produces systematically incorrect contrast ratios,
particularly for mid-range grays.

## Out of Scope for This PRD

- Color blindness simulation: tracked as future work in `reference.md`
- Suggesting alternative colors that would pass: out of scope for the checker;
  that is palette generation territory (PRD-03)
- Font size awareness: Hexwise has no font context; large-text thresholds are
  informational only
