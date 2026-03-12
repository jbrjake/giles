# PRD-03: Palette Generation — Reference

## Acceptance Criteria Cross-Reference

| Requirement | User Story | Title |
|-------------|------------|-------|
| REQ-PAL-001 | US-0204 | Complementary color generation |
| REQ-PAL-002 | US-0205 | Analogous and triadic palettes |
| REQ-PAL-003 | US-0205 | Analogous and triadic palettes |
| REQ-PAL-004 | US-0206 | Palette display |

## Observability

N/A for a CLI tool. Palette generation errors (e.g. unparseable seed color) are
reported on stderr with exit code 1. Successful output goes to stdout, which
means palette output composes with standard shell pipelines:

```sh
hexwise palette --triadic "#FF5733" | xargs -I{} hexwise contrast {} "#ffffff"
```

This composability is a first-class goal; the output format should not break it.

## Open Questions

**Q1: Split-complementary as a fourth mode?**
Status: Open. Split-complementary uses `hue + 150°` and `hue + 210°` instead
of `hue + 180°`, giving a softer alternative to pure complementary that is
easier to work with in practice. The algorithm is trivial; the question is whether
a fourth mode adds enough value to justify the surface area. Palette wants it.
Rusti wants to understand what it would mean for the CLI argument structure first.
Deferred to post-milestone-2 discussion.

**Q2: Should palette output include contrast info between pairs?**
Status: Open. Including contrast ratios between palette members in the default
output would make it immediately useful for accessibility review. The cost is
verbosity — a three-color palette would produce three pairwise contrast results
alongside the color values. A `--verbose` flag might be the right gate. Not
resolved for milestone 2; Checker has opinions about what the test surface looks
like either way.

## Future Work

- **Split-complementary:** Hue + 150° and hue + 210°. Produces a more nuanced
  alternative to complementary that avoids the high-tension look. Low
  implementation cost; scoped to future milestone pending CLI design decision.
- **Perceptual uniformity via OKLab:** Color wheel arithmetic in HSL produces
  palettes that are mathematically correct but perceptually uneven — a 120°
  rotation in HSL does not always look like equal visual spacing. OKLab-based
  palette generation would produce more uniform results. Palette is interested;
  implementation complexity is significant.
- **User-defined palette sizes:** Analogous and triadic modes produce fixed
  counts today (2 and 3 members respectively). Supporting arbitrary spacing and
  count (e.g. "give me 5 colors evenly spaced") would require a different API
  surface. Future work.
- **Pairwise contrast in palette output:** Report WCAG contrast ratios between
  all pairs in the generated palette. Useful for UI color system validation.
  Depends on PRD-02 math already being available; integration is straightforward
  but output format needs design thought.
