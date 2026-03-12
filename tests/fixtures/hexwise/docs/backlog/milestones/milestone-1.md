# M1: Core — Parse, Match, Print

The walking skeleton: hand the oracle a color in any format, get back its name,
its values in every representation, and a description that makes you feel
something. By the end of this milestone Hexwise can see.

| Field | Value |
|-------|-------|
| Sprints | 1–2 |
| Total SP | 34 |
| Release | R1 |

---

### Sprint 1: First Light (Weeks 1-2)

**Sprint Goal:** Parse hex, RGB, and named colors; build the CSS color database.

| Story | Title | Epic | Saga | SP | Priority |
|-------|-------|------|------|----|----------|
| US-0101 | Parse hex color input (#RRGGBB and #RGB shorthand) | E-0101 | S01 | 3 | P0 |
| US-0102 | Parse RGB tuple input (rgb() and bare tuples) | E-0101 | S01 | 5 | P0 |
| US-0104 | Auto-detect color format from input string | E-0101 | S01 | 3 | P0 |
| US-0105 | CSS named color database (all 148 colors) | E-0102 | S01 | 5 | P0 |

**Total SP:** 16

**Key Deliverables:**
- Hex and RGB parsing with validation and error messages
- Format auto-detection dispatcher
- Complete CSS Level 4 color table as compile-time constant

**Sprint Acceptance Criteria:**
- [ ] `hexwise #FF5733` returns parsed Color with correct RGB values
- [ ] `hexwise rgb(255, 87, 51)` produces identical result to hex equivalent
- [ ] `hexwise coral` resolves to `#FF7F50` from the CSS database
- [ ] Invalid input produces a helpful error, not a panic

**Risks & Dependencies:**
- Color struct design in US-0101 is load-bearing for everything else — get it right first
- CSS color table source: use the W3C spec directly, not a third-party list

---

### Sprint 2: Finding Words (Weeks 3-4)

**Sprint Goal:** Add HSL parsing, name lookup, formatted display, and color descriptions.

| Story | Title | Epic | Saga | SP | Priority |
|-------|-------|------|------|----|----------|
| US-0103 | Parse HSL color input (hsl() format) | E-0101 | S01 | 5 | P1 |
| US-0106 | Color name lookup with fuzzy matching | E-0102 | S01 | 3 | P1 |
| US-0107 | Formatted color display with ANSI swatches | E-0103 | S01 | 5 | P1 |
| US-0108 | Synesthetic color descriptions | E-0103 | S01 | 5 | P2 |

**Total SP:** 18

**Key Deliverables:**
- HSL parsing with correct conversion to RGB
- Fuzzy name matching (typo suggestions)
- Terminal output with color swatches and multi-format display
- Personality-driven color descriptions

**Sprint Acceptance Criteria:**
- [ ] `hexwise hsl(11, 100%, 60%)` matches `hexwise #FF5733`
- [ ] `hexwise corl` suggests "did you mean `coral`?"
- [ ] Output includes visible color swatch in true-color terminals
- [ ] Every color gets a one-sentence description that is deterministic

**Risks & Dependencies:**
- HSL-to-RGB conversion has known edge cases at saturation boundaries
- ANSI true-color support varies by terminal — need fallback strategy
- Descriptions are the most subjective feature; Palette and Checker will disagree

---

## Cumulative Burndown

| Sprint | Stories Done | Cumulative SP | % Complete |
|--------|-------------|---------------|------------|
| Sprint 1 | 4 | 16 | 47% |
| Sprint 2 | 8 | 34 | 100% |

## Release Gate Checklist

- [ ] All 8 stories accepted and merged
- [ ] All parsing formats handle edge cases without panic
- [ ] CSS color database covers all 148 Level 4 names
- [ ] Output renders in dark and light terminal themes
- [ ] `cargo test` passes, `cargo clippy` clean
- [ ] README updated with usage examples
