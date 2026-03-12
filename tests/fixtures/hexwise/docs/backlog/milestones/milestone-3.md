# M3: Polish — Batch Mode and Resilience

The oracle learns to handle a crowd. Batch mode is the difference between a
toy and a tool: piping a CSS file's worth of color values through Hexwise and
getting structured output on the other end, with errors reported per-line
instead of as a fatal crash. This is the milestone where Checker gets to be
the most herself.

| Field | Value |
|-------|-------|
| Sprints | 5 |
| Total SP | 13 |
| Release | R2 |

---

### Sprint 5: The Crowd (Weeks 9-10)

**Sprint Goal:** Process colors from stdin in batch, with compact output and graceful error handling.

| Story | Title | Epic | Saga | SP | Priority |
|-------|-------|------|------|----|----------|
| US-0207 | Read colors from stdin (one per line, streaming) | E-0203 | S02 | 5 | P1 |
| US-0208 | Batch output formatting (TSV and NDJSON) | E-0203 | S02 | 5 | P2 |
| US-0209 | Batch error handling (per-line errors, partial success) | E-0203 | S02 | 3 | P0 |

**Total SP:** 13

**Key Deliverables:**
- Streaming stdin reader that processes line-by-line without buffering
- Compact output formats for piping: tab-separated and newline-delimited JSON
- Per-line error reporting to stderr with line numbers and summary

**Sprint Acceptance Criteria:**
- [ ] `cat colors.txt | hexwise --batch` processes each line independently
- [ ] Mixed-format input (hex, RGB, named) in a single stream works correctly
- [ ] Line 47 being garbage doesn't affect lines 1–46 or 48–100
- [ ] Exit code is 0 for all-clean, 1 for any errors
- [ ] `--format json` in batch mode produces valid NDJSON

**Risks & Dependencies:**
- Batch output shares formatting with US-0107 — changes to display affect both
- stdin EOF handling varies by platform (pipe vs. terminal vs. redirect)
- Memory usage must stay constant regardless of input size (streaming, not buffering)

---

## Cumulative Burndown

| Sprint | Stories Done | Cumulative SP | % Complete |
|--------|-------------|---------------|------------|
| Sprint 5 | 3 | 13 | 100% |

## Release Gate Checklist

- [ ] All 3 stories accepted and merged
- [ ] Batch mode processes 1000+ lines without memory growth
- [ ] Errors on stderr, results on stdout, never mixed
- [ ] Exit codes reflect partial failure correctly
- [ ] `cargo test` passes, `cargo clippy` clean
- [ ] End-to-end test: pipe a file with known errors, verify output
