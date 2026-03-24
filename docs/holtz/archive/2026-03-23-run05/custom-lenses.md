# Custom Holtz Lenses

Project-specific lenses discovered during the kanban entry-semantics audit
(2026-03-23). These address blind spots in the standard lens registry where
no existing lens reasons about temporal semantics — WHEN things happen
relative to WHEN they claim to happen.

Proposed upstream: https://github.com/jbrjake/holtz (see PRs)

## semantic-fidelity
**Focus:** Whether names (states, functions, variables, enums) accurately describe what they represent at runtime
**Audit priorities:** State machine labels vs actual entry/exit timing, function names vs observed behavior, boolean semantics vs toggle points, enum values vs runtime meaning
**Failure modes:** States labeled for current activity but applied on completion, functions named for actions they don't perform, naming that drifts from semantics across files (same state name means different things to caller vs callee)
**Entry point:** For each state machine or status enum: trace when each value is set and cleared across ALL callers; compare the temporal window of each value against its documented description. Ask: "If I look at this value right now, does its name tell me the truth about what's happening?"

## temporal-protocol
**Focus:** Multi-file orchestration sequences — the actual order of operations vs documented/intended order
**Audit priorities:** State transitions that fire before/after their documented trigger point, transient states with no meaningful duration between entry and exit, operations that assume prior operations completed but don't verify, workflow steps documented in one file but executed differently in another
**Failure modes:** Exit-labeled states (transition fires after work instead of before), double-tap transitions (two consecutive state changes with no work between), phantom states (entered and exited in the same code block — never observable), protocol drift between orchestrator docs and agent docs
**Entry point:** Pick a workflow that spans 2+ files. Trace the actual execution sequence step by step. At each state change, ask: "What work happened since the last state change? What work remains before the next? Is there a state that exists for zero work?"
