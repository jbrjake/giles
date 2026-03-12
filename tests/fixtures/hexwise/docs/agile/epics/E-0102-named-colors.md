# E-0102 — Named Colors

The part where numbers become words. CSS defines 148 named colors, from
`aliceblue` to `yellowgreen`, and Hexwise needs to know all of them — both
for lookup ("what's the hex for `rebeccapurple`?") and for matching ("what
named color is closest to `#8B4513`?"). Palette has been waiting for this
epic since the project started.

| Field | Value |
|-------|-------|
| Saga | S01 |
| Stories | 2 |
| Total SP | 8 |
| Release | R1 |
| Sprints | 1–2 |

---

### US-0105: CSS Named Color Database

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P0 |
| Release | R1 |
| Saga | S01 |
| Epic | E-0102 |
| Personas | Palette Jones, Rusti Ferris |
| Blocked By | US-0101 |
| Blocks | US-0106 |
| Test Cases | TC-NAM-001, TC-NAM-002 |

**As a** color tool, **I want** a complete database of all 148 CSS named colors with their RGB values **so that** I can translate between names and values in either direction.

**Acceptance Criteria:**
- [ ] `AC-01`: Include all 148 CSS Level 4 named colors
- [ ] `AC-02`: Store as compile-time constant (no runtime allocation for the table)
- [ ] `AC-03`: Support case-insensitive lookup by name
- [ ] `AC-04`: Include `rebeccapurple` (it matters and we will not argue about this)

**Tasks:**
- [ ] `T-0105-01`: Generate static color table from CSS specification (2 SP)
- [ ] `T-0105-02`: Implement case-insensitive name-to-RGB lookup (1 SP)
- [ ] `T-0105-03`: Implement nearest-match by Euclidean distance in RGB space (2 SP)

---

### US-0106: Color Name Lookup

| Field | Value |
|-------|-------|
| Story Points | 3 |
| Priority | P1 |
| Release | R1 |
| Saga | S01 |
| Epic | E-0102 |
| Personas | Palette Jones, Checker Macready |
| Blocked By | US-0105 |
| Blocks | US-0108 |
| Test Cases | TC-NAM-003, TC-NAM-004 |

**As a** user, **I want** to type a color name like `coral` and get its hex value **so that** I can quickly look up colors I know by name but not by number.

**Acceptance Criteria:**
- [ ] `AC-01`: Accept CSS color names as input (case-insensitive)
- [ ] `AC-02`: Integrate with format auto-detection (named color is last in priority)
- [ ] `AC-03`: Suggest closest name match on typo (e.g., `corl` → "did you mean `coral`?")

**Tasks:**
- [ ] `T-0106-01`: Add named-color branch to format detector (1 SP)
- [ ] `T-0106-02`: Implement fuzzy matching for name suggestions (2 SP)
