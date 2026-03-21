# Recon Summary — Pass 19

## Baseline
- 758 tests, 84% coverage, 0 fail, 0 skip
- 282 commits, pass 18 just completed (16/18 items resolved)

## Approach
End-to-end data flows, error path audit, FakeGitHub fidelity, boundary values, test theater

## Top Findings

### Real bugs
1. **kanban_from_labels crashes on None label** (BH19-003) — AttributeError when label list contains None
2. **Pipe chars in titles corrupt markdown tables** (BH19-010) — _format_story_section doesn't sanitize |
3. **gh_json slow path has unhandled JSONDecodeError** (BH19-011) — garbage non-JSON input crashes

### Fake/incomplete tests
4. **BH-021 test is theater** (BH19-002) — claims to test do_sync failure but never calls do_sync
5. **BH18-014 path traversal untested** (BH19-004) — defense-in-depth code with no verification
6. **MonitoredMock has near-zero adoption** (BH19-014) — exists but used in only 6/30 mock sites

### FakeGitHub fidelity
7. **PR state lowercase vs uppercase** (BH19-005) — masks production bugs comparing pr["state"]
8. **issue edit doesn't update milestone counters** (BH19-006) — stale counts in tests
9. **Separate issue/PR number counters** (BH19-007) — allows impossible number overlaps

### Missing tests
10. **list_milestone_issues API failure path** (BH19-001) — silent degradation to 0 SP
11. **format_issue_body → extract_sp roundtrip** (BH19-008) — each tested but not together
12. **build_milestone_title_map** (BH19-009) — no direct unit tests
13. **generate_project_toml preservation** (BH19-012) — BH-017 fix untested
