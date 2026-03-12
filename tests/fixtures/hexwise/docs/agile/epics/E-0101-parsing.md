# E-0101 — Color Parsing

The oracle's front door. Every color Hexwise will ever process enters through
this epic's code — hex triplets, RGB tuples, HSL values, and the auto-detector
that figures out which is which. If parsing is wrong, everything downstream
is wrong. Rusti has Opinions about this.

| Field | Value |
|-------|-------|
| Saga | S01 |
| Stories | 4 |
| Total SP | 16 |
| Release | R1 |
| Sprints | 1–2 |

---

### US-0101: Parse Hex Color Input

| Field | Value |
|-------|-------|
| Story Points | 3 |
| Priority | P0 |
| Release | R1 |
| Saga | S01 |
| Epic | E-0101 |
| Personas | Rusti Ferris, Checker Macready |
| Blocked By | — |
| Blocks | US-0104 |
| Test Cases | TC-PAR-001, TC-PAR-002, TC-PAR-003, GP-001 |

**As a** terminal user, **I want** to pass a hex color code in `#RRGGBB` or `#RGB` shorthand **so that** Hexwise can identify any color I copy from a design tool or stylesheet.

**Acceptance Criteria:**
- [ ] `AC-01`: Parse six-digit hex codes with or without leading `#`
- [ ] `AC-02`: Parse three-digit shorthand (`#RGB`) and expand to six digits
- [ ] `AC-03`: Handle mixed-case input (`#aaBBcc`)
- [ ] `AC-04`: Return a structured `Color` value with normalized RGB components

**Tasks:**
- [ ] `T-0101-01`: Define `Color` struct with `r`, `g`, `b` fields as `u8` (1 SP)
- [ ] `T-0101-02`: Implement hex parsing with `#` stripping and shorthand expansion (1 SP)
- [ ] `T-0101-03`: Add error type for invalid hex input with descriptive message (1 SP)

---

### US-0102: Parse RGB Tuple Input

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P0 |
| Release | R1 |
| Saga | S01 |
| Epic | E-0101 |
| Personas | Rusti Ferris, Checker Macready |
| Blocked By | US-0101 |
| Blocks | US-0104 |
| Test Cases | TC-PAR-004, TC-PAR-005, GP-001 |

**As a** developer, **I want** to pass colors as `rgb(R, G, B)` or `R,G,B` tuples **so that** I can use the same format my CSS or design tokens already use.

**Acceptance Criteria:**
- [ ] `AC-01`: Parse `rgb(R, G, B)` with optional whitespace around values
- [ ] `AC-02`: Parse bare `R,G,B` tuples without the `rgb()` wrapper
- [ ] `AC-03`: Validate each component is in range 0–255
- [ ] `AC-04`: Reject malformed input with a message that shows the expected format

**Tasks:**
- [ ] `T-0102-01`: Implement `rgb()` function-syntax parser with whitespace tolerance (2 SP)
- [ ] `T-0102-02`: Implement bare tuple parser as fallback (1 SP)
- [ ] `T-0102-03`: Add range validation with per-component error reporting (1 SP)
- [ ] `T-0102-04`: Write property tests for round-trip: RGB string → Color → RGB string (1 SP)

---

### US-0103: Parse HSL Color Input

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P1 |
| Release | R1 |
| Saga | S01 |
| Epic | E-0101 |
| Personas | Rusti Ferris, Palette Jones |
| Blocked By | US-0101 |
| Blocks | US-0104 |
| Test Cases | TC-PAR-006, TC-PAR-007, GP-001 |

**As a** designer, **I want** to input colors in HSL format **so that** I can work in the color space I actually think in when choosing hues and adjusting saturation.

**Acceptance Criteria:**
- [ ] `AC-01`: Parse `hsl(H, S%, L%)` with H in 0–360 and S/L in 0–100
- [ ] `AC-02`: Convert HSL to RGB using the standard conversion algorithm
- [ ] `AC-03`: Handle edge cases: H=360 wraps to 0, S=0 produces grayscale
- [ ] `AC-04`: Preserve original HSL values alongside computed RGB in the `Color` struct

**Tasks:**
- [ ] `T-0103-01`: Implement HSL parser with degree/percentage validation (2 SP)
- [ ] `T-0103-02`: Implement HSL-to-RGB conversion (standard algorithm) (2 SP)
- [ ] `T-0103-03`: Extend `Color` struct to carry optional source-space metadata (1 SP)

---

### US-0104: Auto-Detect Color Format

| Field | Value |
|-------|-------|
| Story Points | 3 |
| Priority | P0 |
| Release | R1 |
| Saga | S01 |
| Epic | E-0101 |
| Personas | Rusti Ferris |
| Blocked By | US-0101, US-0102, US-0103 |
| Blocks | US-0107 |
| Test Cases | TC-PAR-008, TC-PAR-009, GP-001 |

**As a** user, **I want** Hexwise to figure out what format my color is in without me specifying it **so that** I can just paste a value and get an answer.

**Acceptance Criteria:**
- [ ] `AC-01`: Detect hex vs. RGB vs. HSL from input string alone
- [ ] `AC-02`: Attempt parsers in priority order: hex, RGB, HSL, named color
- [ ] `AC-03`: Return the first successful parse, not all possible parses
- [ ] `AC-04`: On no match, produce an error listing the formats that were tried

**Tasks:**
- [ ] `T-0104-01`: Implement format-detection dispatcher with ordered fallback (2 SP)
- [ ] `T-0104-02`: Write integration tests covering ambiguous inputs (1 SP)
