# M2: Toolkit — Contrast and Palettes

The oracle gets opinions. This milestone adds the features that turn Hexwise
from a lookup tool into something you actually reach for during design work:
accessibility contrast checking with real WCAG verdicts, and palette generation
that does the color wheel math so you don't have to.

| Field | Value |
|-------|-------|
| Sprints | 3–4 |
| Total SP | 30 |
| Release | R2 |

---

### Sprint 3: The Numbers (Weeks 5-6)

**Sprint Goal:** Implement WCAG-compliant contrast checking with luminance, ratio, and verdict.

| Story | Title | Epic | Saga | SP | Priority |
|-------|-------|------|------|----|----------|
| US-0201 | Relative luminance calculation (WCAG 2.1) | E-0201 | S02 | 5 | P0 |
| US-0202 | Contrast ratio calculation between two colors | E-0201 | S02 | 5 | P0 |
| US-0203 | WCAG AA/AAA compliance verdict | E-0201 | S02 | 5 | P0 |

**Total SP:** 15

**Key Deliverables:**
- Relative luminance with correct sRGB linearization
- Contrast ratio with automatic lighter/darker ordering
- Pass/fail verdicts for AA and AAA at normal and large text sizes

**Sprint Acceptance Criteria:**
- [ ] Black-on-white returns contrast ratio 21:1
- [ ] White-on-white returns contrast ratio 1:1
- [ ] `hexwise contrast #000000 #FFFFFF` reports AA pass, AAA pass
- [ ] Luminance values match W3C reference to 4 decimal places

**Risks & Dependencies:**
- sRGB linearization piecewise function is easy to get subtly wrong
- Contrast formula ordering (L1 > L2) must be enforced, not assumed
- Need reference values from W3C for validation, not just "looks right"

---

### Sprint 4: The Taste (Weeks 7-8)

**Sprint Goal:** Generate complementary, analogous, and triadic palettes with visual display.

| Story | Title | Epic | Saga | SP | Priority |
|-------|-------|------|------|----|----------|
| US-0204 | Complementary color generation (hue + 180 degrees) | E-0202 | S02 | 5 | P1 |
| US-0205 | Analogous and triadic palette generation | E-0202 | S02 | 5 | P1 |
| US-0206 | Palette display with horizontal swatch strip | E-0202 | S02 | 5 | P1 |

**Total SP:** 15

**Key Deliverables:**
- Hue rotation engine with wraparound at 360 degrees
- Three palette modes: complementary, analogous, triadic
- Horizontal swatch strip with hex labels and true-color rendering

**Sprint Acceptance Criteria:**
- [ ] Complement of `hsl(0, 100%, 50%)` (red) is `hsl(180, 100%, 50%)` (cyan)
- [ ] Analogous of hue 350 produces hues 320 and 20 (correct wraparound)
- [ ] Triadic of hue 0 produces hues 120 and 240
- [ ] Palette display degrades to 256-color when true-color is unavailable

**Risks & Dependencies:**
- Hue rotation depends on HSL parsing (US-0103) from Milestone 1
- Palette display shares rendering code with US-0107 — coordinate with that output
- Analogous/triadic naming: some sources use different degree offsets — we follow the standard

---

## Cumulative Burndown

| Sprint | Stories Done | Cumulative SP | % Complete |
|--------|-------------|---------------|------------|
| Sprint 3 | 3 | 15 | 50% |
| Sprint 4 | 6 | 30 | 100% |

## Release Gate Checklist

- [ ] All 6 stories accepted and merged
- [ ] Contrast ratios match W3C reference implementation
- [ ] Palette hue rotations are mathematically correct
- [ ] WCAG verdicts are accurate for AA and AAA levels
- [ ] All output modes work in both color and no-color terminals
- [ ] `cargo test` passes, `cargo clippy` clean
