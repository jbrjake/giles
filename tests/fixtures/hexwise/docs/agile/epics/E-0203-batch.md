# E-0203 — Batch Processing

The oracle learns to listen to a crowd. Batch mode lets Hexwise read colors
from stdin — one per line, a hundred per file, piped from `grep` or `jq` or
whatever cursed shell pipeline the user has constructed. This epic is where
Checker's adversarial instincts really earn their keep: what happens when line
47 is garbage and lines 1–46 were fine?

| Field | Value |
|-------|-------|
| Saga | S02 |
| Stories | 3 |
| Total SP | 13 |
| Release | R2 |
| Sprints | 5 |

---

### US-0207: Read Colors from Stdin

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P1 |
| Release | R2 |
| Saga | S02 |
| Epic | E-0203 |
| Personas | Rusti Ferris, Checker Macready |
| Blocked By | US-0104 |
| Blocks | US-0208 |
| Test Cases | TC-BAT-001, TC-BAT-002, GP-004 |

**As a** power user, **I want** to pipe a list of colors into Hexwise via stdin **so that** I can process colors from files, scripts, or other tools without invoking Hexwise once per color.

**Acceptance Criteria:**
- [ ] `AC-01`: Read one color per line from stdin when no positional argument is given
- [ ] `AC-02`: Auto-detect format for each line independently
- [ ] `AC-03`: Handle mixed formats in a single stream (hex on line 1, RGB on line 2)
- [ ] `AC-04`: Process input line-by-line without buffering the entire input into memory

**Tasks:**
- [ ] `T-0207-01`: Implement stdin line reader with `BufRead` (2 SP)
- [ ] `T-0207-02`: Wire stdin path into CLI argument parser (1 SP)
- [ ] `T-0207-03`: Add `--batch` flag as explicit opt-in for stdin mode (2 SP)

---

### US-0208: Batch Output Formatting

| Field | Value |
|-------|-------|
| Story Points | 5 |
| Priority | P2 |
| Release | R2 |
| Saga | S02 |
| Epic | E-0203 |
| Personas | Palette Jones, Rusti Ferris |
| Blocked By | US-0207, US-0107 |
| Blocks | US-0209 |
| Test Cases | TC-BAT-003, TC-BAT-004, GP-004 |

**As a** user processing many colors, **I want** batch output to be compact and machine-readable **so that** I can pipe Hexwise's output into other tools or save it to a file.

**Acceptance Criteria:**
- [ ] `AC-01`: Default batch output: one result per line, tab-separated fields
- [ ] `AC-02`: Support `--format json` for newline-delimited JSON (one object per line)
- [ ] `AC-03`: Include line number in output for cross-referencing with input
- [ ] `AC-04`: Maintain field order consistency across all output lines

**Tasks:**
- [ ] `T-0208-01`: Implement compact single-line output formatter (2 SP)
- [ ] `T-0208-02`: Implement NDJSON output formatter (2 SP)
- [ ] `T-0208-03`: Add line-number tracking to batch pipeline (1 SP)

---

### US-0209: Batch Error Handling

| Field | Value |
|-------|-------|
| Story Points | 3 |
| Priority | P0 |
| Release | R2 |
| Saga | S02 |
| Epic | E-0203 |
| Personas | Checker Macready, Rusti Ferris |
| Blocked By | US-0208 |
| Blocks | — |
| Test Cases | TC-BAT-005, TC-BAT-006, GP-004 |

**As a** user running Hexwise on untrusted input, **I want** parse errors on individual lines to be reported without stopping the entire batch **so that** one bad value in a hundred doesn't waste the other ninety-nine results.

**Acceptance Criteria:**
- [ ] `AC-01`: Invalid lines produce an error message on stderr with the line number
- [ ] `AC-02`: Valid lines continue processing after an error (no early exit)
- [ ] `AC-03`: Exit code reflects whether any errors occurred (0 = all clean, 1 = partial failure)
- [ ] `AC-04`: Summary line at end: "Processed N colors, M errors"

**Tasks:**
- [ ] `T-0209-01`: Implement per-line error collection with line-number context (1 SP)
- [ ] `T-0209-02`: Route errors to stderr while results go to stdout (1 SP)
- [ ] `T-0209-03`: Add summary footer and exit-code logic (1 SP)
