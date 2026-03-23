# Predictions (Run 4 — Targeted)

Based on recon of the entry-semantics changes and custom lens definitions:

## P1 (HIGH): done state description will include post-transition work
**Rationale:** Entry semantics require the state description to match the moment of entry. Terminal states often accumulate side effects in their descriptions that actually happen after the transition.
**What to look for:** `done` description including burndown updates or other post-transition work.

## P2 (MEDIUM): integration state will lack entry guard asymmetry
**Rationale:** Entry guards verify prior-phase deliverables. The semantic-fidelity lens checks whether each guard actually validates what the description claims. States without guards are likely to have undocumented reliance on process enforcement.
**What to look for:** `integration` having no preconditions while its description implies review approval.

## P3 (LOW): sync paths will have different temporal guarantees not documented in kanban-protocol.md
**Rationale:** The temporal-protocol lens checks for protocol drift between files. Two sync paths with different enforcement levels may not be documented in the primary protocol reference.
**What to look for:** kanban-protocol.md not mentioning that sync_tracking accepts any valid state.
