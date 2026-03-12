# Hexwise Backlog

A color oracle needs a plan. Here's ours.

| Metric | Count |
|--------|-------|
| Sagas | 2 |
| Epics | 6 |
| Stories | 17 |
| Total SP | 77 |
| Sprints | 5 |
| Releases | 2 |

## Numbering Scheme

| Artifact | Pattern | Example |
|----------|---------|---------|
| User Stories | `US-AASS` | `US-0101` (Saga 01, sequence 01) |
| Epics | `E-XXYY` | `E-0101` (Saga 01, epic 01) |
| Tasks | `T-AASS-NN` | `T-0101-01` (Story 0101, task 01) |

## Releases

| Release | Name | Milestones | Sprints | SP |
|---------|------|------------|---------|-----|
| R1 | Core | M1 | 1–2 | 34 |
| R2 | Toolkit | M2, M3 | 3–5 | 43 |

R1 ships the walking skeleton: you hand it a color, it tells you what it is.
R2 gives the oracle its opinions: contrast, palettes, and the ability to
process colors in bulk without complaining.

## Where Things Live

| Artifact | Path |
|----------|------|
| Sagas | `sagas/` |
| Epics | `epics/` |
| Milestones | `../../backlog/milestones/` |
| Story Map | `../../user-stories/story-map/INDEX.md` |
