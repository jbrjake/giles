# E-0103 — Output Formatting

The oracle knows what it's looking at. Now it needs to say it out loud — in a
way that respects the user's terminal, their eyes, and their time. This is
where Palette's insistence that "aesthetics are just UX for your visual cortex"
becomes load-bearing architecture.

| Field | Value |
|-------|-------|
| Saga | S01 |
| Stories | 2 |
| Total SP | 10 |
| Release | R1 |
| Sprints | 2 |

---

### US-0107: Formatted Color Display

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P1 |
| Release | R1 |
| Saga | S01 |
| Epic | E-0103 |
| Personas | Palette Jones, Rusti Ferris |
| Blocked By | US-0104 |
| Blocks | US-0208 |
| Test Cases | TC-OUT-001, TC-OUT-002, GP-001 |

**As a** user, **I want** Hexwise to display color information in a clean, readable format with a color swatch **so that** I can visually confirm the color and read its values at a glance.

**Acceptance Criteria:**
- [ ] `AC-01`: Show ANSI color swatch (background block) next to color values
- [ ] `AC-02`: Display hex, RGB, and HSL representations simultaneously
- [ ] `AC-03`: Show nearest CSS named color with distance indicator
- [ ] `AC-04`: Adapt display for dark and light terminal backgrounds

**Tasks:**
- [ ] `T-0107-01`: Implement ANSI true-color swatch rendering (2 SP)
- [ ] `T-0107-02`: Build multi-format display layout (hex, RGB, HSL, name) (2 SP)
- [ ] `T-0107-03`: Add terminal background detection or `--theme` flag (1 SP)

---

### US-0108: Synesthetic Color Descriptions

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P2 |
| Release | R1 |
| Saga | S01 |
| Epic | E-0103 |
| Personas | Palette Jones |
| Blocked By | US-0106 |
| Blocks | — |
| Test Cases | TC-OUT-003, TC-OUT-004, GP-001 |

**As a** curious human, **I want** Hexwise to describe colors with personality — warmth, mood, associations — **so that** using the tool feels less like reading a spec sheet and more like consulting an oracle.

**Acceptance Criteria:**
- [ ] `AC-01`: Generate a one-sentence description for any color based on hue, saturation, and lightness ranges
- [ ] `AC-02`: Descriptions use temperature (warm/cool), intensity (bold/muted), and associative language
- [ ] `AC-03`: Named colors get curated descriptions; computed colors get algorithmic ones
- [ ] `AC-04`: Descriptions are deterministic (same input always produces same description)

**Tasks:**
- [ ] `T-0108-01`: Define description taxonomy: temperature, intensity, mood (1 SP)
- [ ] `T-0108-02`: Implement algorithmic description generator from HSL ranges (2 SP)
- [ ] `T-0108-03`: Curate descriptions for the 20 most common CSS named colors (1 SP)
- [ ] `T-0108-04`: Integrate descriptions into formatted display output (1 SP)
