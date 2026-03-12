# E-0202 — Palette Generation

Where the oracle starts having taste. Given a single color, Hexwise should be
able to suggest complementary, analogous, and triadic companions — not just
as hex codes, but displayed in a way that lets you feel whether the palette
works. This is Palette Jones's home turf, and she is not going to let a
palette generator ship without proper visual presentation.

| Field | Value |
|-------|-------|
| Saga | S02 |
| Stories | 3 |
| Total SP | 15 |
| Release | R2 |
| Sprints | 4 |

---

### US-0204: Complementary Color Generation

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P1 |
| Release | R2 |
| Saga | S02 |
| Epic | E-0202 |
| PRD | PRD-03 |
| Personas | Palette Jones, Rusti Ferris |
| Blocked By | US-0103 |
| Blocks | US-0206 |
| Test Cases | TC-PAL-001, TC-PAL-002, GP-003 |

**As a** designer, **I want** to see the complementary color for any input **so that** I can quickly find high-contrast accent colors that sit opposite on the color wheel.

**Acceptance Criteria:**
- [ ] `AC-01`: Compute complementary by rotating hue 180 degrees in HSL space
- [ ] `AC-02`: Preserve original saturation and lightness values
- [ ] `AC-03`: Display both colors side-by-side with ANSI swatches
- [ ] `AC-04`: Show hex, RGB, and HSL values for the generated complement

**Tasks:**
- [ ] `T-0204-01`: Implement hue rotation with wraparound at 360 degrees (1 SP)
- [ ] `T-0204-02`: Add `hexwise complement <color>` subcommand (2 SP)
- [ ] `T-0204-03`: Build side-by-side swatch display for color pairs (2 SP)

---

### US-0205: Analogous and Triadic Palettes

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P1 |
| Release | R2 |
| Saga | S02 |
| Epic | E-0202 |
| PRD | PRD-03 |
| Personas | Palette Jones, Rusti Ferris |
| Blocked By | US-0204 |
| Blocks | US-0206 |
| Test Cases | TC-PAL-003, TC-PAL-004, GP-003 |

**As a** designer, **I want** to generate analogous (hue +/- 30 degrees) and triadic (hue +/- 120 degrees) palettes **so that** I have a range of harmonious color options from a single starting point.

**Acceptance Criteria:**
- [ ] `AC-01`: Analogous palette produces colors at hue -30 and hue +30 degrees
- [ ] `AC-02`: Triadic palette produces colors at hue -120 and hue +120 degrees
- [ ] `AC-03`: Both modes preserve saturation and lightness from the input color
- [ ] `AC-04`: Handle hue wraparound correctly (e.g., hue 350 + 30 = 20)

**Tasks:**
- [ ] `T-0205-01`: Generalize hue rotation to accept arbitrary degree offsets (1 SP)
- [ ] `T-0205-02`: Add `hexwise palette <color> --mode analogous|triadic` subcommand (2 SP)
- [ ] `T-0205-03`: Write test cases for wraparound at 0/360 boundary (2 SP)

---

### US-0206: Palette Display

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P1 |
| Release | R2 |
| Saga | S02 |
| Epic | E-0202 |
| PRD | PRD-03 |
| Personas | Palette Jones |
| Blocked By | US-0204, US-0205 |
| Blocks | — |
| Test Cases | TC-PAL-005, TC-PAL-006, GP-003 |

**As a** user, **I want** palettes displayed as a horizontal strip of color swatches with values underneath **so that** I can visually evaluate the palette at a glance in my terminal.

**Acceptance Criteria:**
- [ ] `AC-01`: Render palette as horizontal ANSI swatch blocks (minimum 4 columns wide per color)
- [ ] `AC-02`: Show hex values below each swatch
- [ ] `AC-03`: Indicate the input color distinctly (border or label)
- [ ] `AC-04`: Gracefully degrade on terminals without true-color support

**Tasks:**
- [ ] `T-0206-01`: Build horizontal swatch strip renderer (2 SP)
- [ ] `T-0206-02`: Add value labels below swatches with alignment (2 SP)
- [ ] `T-0206-03`: Detect true-color support and implement 256-color fallback (1 SP)
