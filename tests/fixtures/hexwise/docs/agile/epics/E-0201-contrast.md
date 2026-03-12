# E-0201 — Contrast Checking

The math that matters. WCAG accessibility guidelines define specific formulas
for relative luminance and contrast ratio, and getting them wrong means telling
someone their text is readable when it isn't. Rusti has the coefficients
memorized. Checker has the edge cases pre-written. This epic does not get to
be approximately correct.

| Field | Value |
|-------|-------|
| Saga | S02 |
| Stories | 3 |
| Total SP | 15 |
| Release | R2 |
| Sprints | 3 |

---

### US-0201: Relative Luminance Calculation

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P0 |
| Release | R2 |
| Saga | S02 |
| Epic | E-0201 |
| Personas | Rusti Ferris, Checker Macready |
| Blocked By | US-0101 |
| Blocks | US-0202 |
| Test Cases | TC-CON-001, TC-CON-002, GP-002 |

**As a** developer checking accessibility, **I want** Hexwise to compute the relative luminance of any color **so that** I have the foundation for accurate contrast ratio calculations.

**Acceptance Criteria:**
- [ ] `AC-01`: Implement WCAG 2.1 relative luminance: `L = 0.2126*R + 0.7152*G + 0.0722*B` after sRGB linearization
- [ ] `AC-02`: sRGB linearization uses the correct piecewise function (threshold at 0.04045)
- [ ] `AC-03`: Pure black returns luminance 0.0, pure white returns luminance 1.0
- [ ] `AC-04`: Results match W3C reference values to at least 4 decimal places

**Tasks:**
- [ ] `T-0201-01`: Implement sRGB linearization with piecewise gamma correction (2 SP)
- [ ] `T-0201-02`: Implement luminance calculation with WCAG coefficients (1 SP)
- [ ] `T-0201-03`: Validate against W3C reference table (minimum 10 test colors) (2 SP)

---

### US-0202: Contrast Ratio Calculation

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P0 |
| Release | R2 |
| Saga | S02 |
| Epic | E-0201 |
| Personas | Rusti Ferris, Checker Macready |
| Blocked By | US-0201 |
| Blocks | US-0203 |
| Test Cases | TC-CON-003, TC-CON-004, GP-002 |

**As a** developer, **I want** to compute the contrast ratio between two colors **so that** I can check whether a foreground/background pair meets accessibility standards.

**Acceptance Criteria:**
- [ ] `AC-01`: Implement contrast ratio formula: `(L1 + 0.05) / (L2 + 0.05)` where L1 >= L2
- [ ] `AC-02`: Automatically determine which color is lighter (order-independent input)
- [ ] `AC-03`: Black-on-white returns 21:1, white-on-white returns 1:1
- [ ] `AC-04`: Accept two colors in any supported format (hex, RGB, HSL, named)

**Tasks:**
- [ ] `T-0202-01`: Implement contrast ratio with automatic luminance ordering (2 SP)
- [ ] `T-0202-02`: Add CLI subcommand `hexwise contrast <fg> <bg>` (2 SP)
- [ ] `T-0202-03`: Write property tests: ratio is always >= 1.0 and <= 21.0 (1 SP)

---

### US-0203: WCAG Compliance Verdict

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P0 |
| Release | R2 |
| Saga | S02 |
| Epic | E-0201 |
| Personas | Palette Jones, Checker Macready |
| Blocked By | US-0202 |
| Blocks | — |
| Test Cases | TC-CON-005, TC-CON-006, GP-002 |

**As a** designer, **I want** Hexwise to tell me whether a color pair passes WCAG AA or AAA **so that** I get a clear pass/fail verdict instead of doing the ratio lookup myself.

**Acceptance Criteria:**
- [ ] `AC-01`: Report AA pass/fail (ratio >= 4.5 for normal text, >= 3.0 for large text)
- [ ] `AC-02`: Report AAA pass/fail (ratio >= 7.0 for normal text, >= 4.5 for large text)
- [ ] `AC-03`: Display the numeric ratio alongside the verdict
- [ ] `AC-04`: Use color-coded output (green/red) for pass/fail, with fallback for no-color terminals

**Tasks:**
- [ ] `T-0203-01`: Implement WCAG level evaluation (AA/AAA, normal/large text) (2 SP)
- [ ] `T-0203-02`: Build verdict display with color-coded pass/fail indicators (2 SP)
- [ ] `T-0203-03`: Add `--no-color` flag support for plain-text output (1 SP)
