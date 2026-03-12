# Traceability Matrix

Bidirectional mapping between user stories and test cases. Use this to verify
that every story has test coverage, and that every test case can be traced back
to a requirement.

---

## Story → Test Cases

| Story | Title | Test Cases |
|-------|-------|-----------|
| US-0101 | Parse hex color input | TC-PAR-001, TC-PAR-002, TC-PAR-003, TC-PAR-004, TC-PAR-005, TC-ADV-001, TC-ADV-002, TC-ADV-003, TC-ADV-004, TC-ADV-006, TC-ADV-007, GP-001 |
| US-0102 | Parse RGB tuple input | TC-PAR-006 |
| US-0103 | Parse HSL color input | TC-ADV-008 |
| US-0104 | Auto-detect color format | TC-PAR-006 |
| US-0105 | CSS named color database | TC-NAM-001, TC-NAM-002, TC-NAM-003, GP-001, GP-005 |
| US-0106 | Color name lookup | TC-NAM-001, TC-NAM-002, TC-NAM-003, TC-ADV-009, GP-005 |
| US-0107 | Formatted color display | TC-OUT-001, TC-OUT-002, GP-001 |
| US-0108 | Synesthetic color descriptions | TC-OUT-003, GP-001 |
| US-0201 | Relative luminance calculation | TC-CON-001, TC-CON-002, TC-CON-003, TC-CON-004, GP-002 |
| US-0202 | Contrast ratio calculation | TC-CON-001, TC-CON-002, TC-CON-003, TC-ADV-005, GP-002 |
| US-0203 | WCAG compliance verdict | TC-CON-003, TC-CON-004, GP-002 |
| US-0204 | Complementary color generation | TC-PAL-001 |
| US-0205 | Analogous and triadic palettes | TC-PAL-002, TC-PAL-003, GP-003 |
| US-0206 | Palette display | TC-PAL-004, GP-003 |
| US-0207 | Read colors from stdin | TC-BAT-001, TC-BAT-003, TC-ADV-010, GP-004 |
| US-0208 | Batch output formatting | TC-BAT-001, TC-BAT-002, TC-ADV-010, GP-004 |
| US-0209 | Batch error handling | TC-BAT-002, GP-004 |

---

## Test Case → Stories

| Test Case | Title | Stories |
|-----------|-------|---------|
| GP-001 | First Impression | US-0101, US-0105, US-0107, US-0108 |
| GP-002 | The Contrast Question | US-0201, US-0202, US-0203 |
| GP-003 | Palette Party | US-0205, US-0206 |
| GP-004 | Batch Judgment | US-0207, US-0208, US-0209 |
| GP-005 | Name That Color | US-0105, US-0106 |
| TC-PAR-001 | Valid 6-digit hex with hash prefix | US-0101 |
| TC-PAR-002 | Valid 3-digit hex shorthand expansion | US-0101 |
| TC-PAR-003 | Case-insensitive hex parsing | US-0101 |
| TC-PAR-004 | Missing hash prefix is accepted | US-0101 |
| TC-PAR-005 | Invalid hex characters produce clear error | US-0101 |
| TC-PAR-006 | RGB tuple input parsing | US-0102, US-0104 |
| TC-NAM-001 | Exact CSS named color match | US-0105, US-0106 |
| TC-NAM-002 | Case-insensitive name lookup | US-0106 |
| TC-NAM-003 | Unknown color name returns error | US-0106 |
| TC-OUT-001 | Default plain text output | US-0107 |
| TC-OUT-002 | JSON output flag | US-0107 |
| TC-OUT-003 | Color description in default output | US-0108 |
| TC-CON-001 | Black-on-white contrast is 21:1 | US-0201, US-0202 |
| TC-CON-002 | Same color contrast is 1:1 | US-0202 |
| TC-CON-003 | AA threshold boundary check | US-0201, US-0202, US-0203 |
| TC-CON-004 | Large text threshold evaluated separately | US-0203 |
| TC-PAL-001 | Complementary color of red is cyan | US-0204 |
| TC-PAL-002 | Analogous palette produces 3 colors | US-0205 |
| TC-PAL-003 | Triadic palette uses 120° rotation | US-0205 |
| TC-PAL-004 | Palette JSON output | US-0206 |
| TC-BAT-001 | Stdin multi-line batch processing | US-0207, US-0208 |
| TC-BAT-002 | Mixed valid and invalid input in batch | US-0208, US-0209 |
| TC-BAT-003 | Empty stdin produces no output | US-0207 |
| TC-ADV-001 | Empty string input returns helpful error | US-0101 |
| TC-ADV-002 | Invalid hex characters identified in error | US-0101 |
| TC-ADV-003 | 3-digit hex shorthand expands correctly | US-0101 |
| TC-ADV-004 | Unicode fullwidth hex input is rejected | US-0101 |
| TC-ADV-005 | Contrast of a color against itself is 1:1 | US-0202 |
| TC-ADV-006 | Extremely long input within timeout | US-0101 |
| TC-ADV-007 | Null bytes in input are rejected gracefully | US-0101 |
| TC-ADV-008 | HSL with out-of-range values is handled | US-0103 |
| TC-ADV-009 | Named color with extra whitespace is trimmed | US-0106 |
| TC-ADV-010 | Batch mode with 10,000 lines within 10s | US-0207, US-0208 |

---

## Persona Coverage

| Persona | Domain | Test Cases |
|---------|--------|-----------|
| Rusti Ferris | Parsing, performance, memory safety | TC-PAR-001, TC-PAR-002, TC-PAR-003, TC-PAR-004, TC-PAR-005, TC-PAR-006, GP-001 |
| Palette Jones | Color theory, UX, output formatting, palettes | TC-NAM-001, TC-NAM-002, TC-NAM-003, TC-OUT-001, TC-OUT-002, TC-OUT-003, TC-PAL-001, TC-PAL-002, TC-PAL-003, TC-PAL-004, GP-003, GP-005 |
| Checker Macready | QA, contrast, batch, adversarial, edge cases | TC-CON-001, TC-CON-002, TC-CON-003, TC-CON-004, TC-BAT-001, TC-BAT-002, TC-BAT-003, TC-ADV-001, TC-ADV-002, TC-ADV-003, TC-ADV-004, TC-ADV-005, TC-ADV-006, TC-ADV-007, TC-ADV-008, TC-ADV-009, TC-ADV-010, GP-002, GP-004 |

---

## Coverage Summary

| Priority | Count | Stories Covered |
|----------|-------|----------------|
| P0 | 14 | US-0101, US-0102, US-0105, US-0106, US-0107, US-0201, US-0202, US-0203, US-0207, US-0208, US-0209 |
| P1 | 15 | All stories at least partially |
| P2 | 2 | US-0108, US-0106 |

All 19 user stories have at least one test case. Stories US-0101 and US-0207/0208
have the deepest coverage, which is appropriate — they are the front door and the
primary output path.
