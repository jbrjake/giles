# PRD-02: Contrast & Accessibility — Reference

## Acceptance Criteria Cross-Reference

| Requirement | User Story | Title |
|-------------|------------|-------|
| REQ-CON-001 | US-0201 | Relative luminance calculation |
| REQ-CON-002 | US-0202 | Contrast ratio calculation |
| REQ-CON-003 | US-0203 | WCAG compliance verdict |
| REQ-CON-004 | US-0203 | WCAG compliance verdict (large text branch) |

## Observability

N/A for a CLI tool. Errors (e.g. a color that fails to parse) are reported on
stderr with exit code 1. A passing contrast check exits 0; a failing check exits
with a non-zero code to support scripting use cases (e.g. `hexwise contrast
#333 #fff || notify-send "contrast fail"`).

## Open Questions

**Q1: Do we report large-text thresholds separately?**
Status: Resolved — yes, separately, labeled clearly. The WCAG distinction between
normal and large text is meaningful and callers may specifically need to know the
large-text verdict (e.g. for header copy). Collapsing the two into a single result
would discard information.

**Q2: Should output include the actual ratio or just pass/fail?**
Status: Resolved — always include the actual ratio. A pass/fail verdict without
the number is useless to a designer who is trying to push toward a threshold.
Knowing you're at 4.3:1 (fails AA normal) versus 4.49:1 (fails AA normal by 0.01)
changes the decision. The number belongs in the output.

## Future Work

- **Color blindness simulation:** Simulate how a color pair appears to users with
  deuteranopia (red-green), protanopia (red-green, distinct type), or tritanopia
  (blue-yellow). This requires applying a color transformation matrix before
  running the luminance calculation, not a separate code path. Palette wants this;
  it is scoped for a future milestone.
- **Contrast improvement suggestions:** Given a failing pair, suggest the minimum
  adjustment (lightness shift, hue rotation) needed to pass. Requires integrating
  with palette generation math. Post-milestone-2 work.
- **APCA (Advanced Perceptual Contrast Algorithm):** A more accurate model than
  WCAG 2.1 contrast, proposed for WCAG 3.0. Not normative yet. Worth watching.
