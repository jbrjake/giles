# PRD-01: Color Parsing & Conversion — Reference

## Acceptance Criteria Cross-Reference

Requirements in this PRD are verified by the following user stories:

| Requirement | User Story | Title |
|-------------|------------|-------|
| REQ-PAR-001 | US-0101 | Parse hex color input |
| REQ-PAR-002 | US-0101 | Parse hex color input (3-digit shorthand) |
| REQ-PAR-003 | US-0102 | Parse RGB tuple input |
| REQ-PAR-004 | US-0103 | Parse HSL color input |
| REQ-PAR-005 | US-0105, US-0106 | CSS named color database, Color name lookup |
| REQ-PAR-006 | US-0104 | Auto-detect color format |
| REQ-PAR-NF-001 | US-0101–US-0104 | Performance gate in acceptance criteria |

## Observability

N/A for a CLI tool. There is no metrics endpoint, no distributed trace, and no
health check route. Parse errors are surfaced as structured error messages on
stderr with exit code 1.

## Open Questions

**Q1: Should we support 3-digit hex shorthand `#F53`?**
Status: Resolved — yes, include it. REQ-PAR-002 is in scope for milestone 1.
Rationale: 3-digit hex is valid CSS and appears in the wild often enough that
rejecting it would be surprising. The expansion rule is unambiguous.

**Q2: Alpha channel support (RGBA, HSLA)?**
Status: Open. Alpha was descoped from milestone 1 due to output complexity — the
terminal display layer would need to render transparency somehow, and there's no
clean way to do that in a CLI context. If we support alpha at all, it's milestone 2
at earliest, and probably behind a flag.

## Future Work

- **CMYK:** Used in print workflows. Not relevant to a terminal color tool, but
  worth noting that conversion from CMYK to sRGB is not lossless.
- **Lab color space:** Perceptually uniform. Would improve the accuracy of
  palette generation and contrast calculations at the cost of more complex math.
- **OKLab:** A more recent perceptually uniform color space that corrects known
  hue-shift issues in Lab. Palette is interested. Implementation complexity is
  moderate; the tradeoff is whether we want to carry that dependency.
- **Alpha channel (RGBA, HSLA):** Requires a decision about what alpha means
  in a CLI output context. Defer until palette display is stable.
