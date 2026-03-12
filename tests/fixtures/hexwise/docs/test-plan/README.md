# Test Plan

| Metric | Count |
|--------|-------|
| Golden Path Scenarios | 5 |
| Functional Test Cases | ~30 |
| Adversarial Test Cases | 10 |
| **Total** | **~45** |

## Test Pyramid

```
           Golden Paths (E2E)
          Adversarial + Perf
         Integration Tests
        Unit Tests (>80% core)
```

## Document Map

| Prefix | File | Domain |
|--------|------|--------|
| GP-* | `01-golden-paths.md` | End-to-end scenarios |
| TC-PAR-* | `02-functional-tests.md` | Parsing & conversion |
| TC-NAM-* | `02-functional-tests.md` | Named colors |
| TC-OUT-* | `02-functional-tests.md` | Output & formatting |
| TC-CON-* | `02-functional-tests.md` | Contrast checking |
| TC-PAL-* | `02-functional-tests.md` | Palette generation |
| TC-BAT-* | `02-functional-tests.md` | Batch mode |
| TC-ADV-* | `03-adversarial-tests.md` | Edge cases & adversarial |
