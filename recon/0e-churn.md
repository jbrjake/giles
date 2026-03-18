# 0e — Git Churn Analysis (last 50 commits)

## Top changed files

| Changes | File |
|---------|------|
| 15 | BUG-HUNTER-PUNCHLIST.md |
| 14 | scripts/validate_config.py |
| 12 | BUG-HUNTER-STATUS.md |
| 10 | tests/test_verify_fixes.py |
|  9 | tests/test_sprint_runtime.py |
|  8 | skills/sprint-run/scripts/sync_tracking.py |
|  7 | tests/test_kanban.py |
|  6 | skills/sprint-setup/scripts/populate_issues.py |
|  6 | scripts/manage_epics.py |
|  5 | tests/test_bugfix_regression.py |
|  4 | tests/fake_github.py |
|  4 | skills/sprint-run/scripts/update_burndown.py |
|  4 | scripts/sprint_init.py |
|  4 | scripts/kanban.py |
|  3 | scripts/sprint_teardown.py |
|  2 | tests/test_pipeline_scripts.py |
|  2 | tests/test_lifecycle.py |
|  2 | tests/test_hexwise_setup.py |
|  2 | skills/sprint-setup/scripts/bootstrap_github.py |
|  2 | skills/sprint-run/SKILL.md |

## Recent commits (last 20)

```
6f4de6c feat: centralized kanban state machine (scripts/kanban.py)
d84bf6d test: add kanban.main() integration test for meta-test coverage
3d7ca21 docs: replace gh issue edit with kanban.py across all prompts and docs
80fef38 feat: kanban CLI entry point with argparse subcommands
689dbf9 fix: add assign rollback test, remove dead _make_gh_side_effect helper
d1d37eb feat: kanban GitHub sync — do_transition, do_assign, do_sync, do_status
680339e fix: kanban code quality review fixes
4ef967f feat: kanban core state machine — transitions, preconditions, atomic writes, locking
3d5f942 fix: place §validate_config.TF anchor before @dataclass decorator
41f76a1 refactor: extract TF, read_tf, write_tf into validate_config.py
ccdd1d1 docs: kanban state machine implementation plan
dfaef6b docs: address spec review feedback for kanban state machine
8b2baf9 docs: kanban state machine design spec
59427e2 fix: use ${CLAUDE_PLUGIN_ROOT} for all script paths in skills
0ab9254 fix: plugin.json skills field uses directory path, bump to 0.6.1
074d7fa chore: bump version to 0.6.0
6d1fa52 chore: P21 complete — 22/27 items resolved, 5 deferred (all LOW/MEDIUM)
d59eee6 fix: issue dedup abort, monitor hardening, label arg check (BH21-007/008/019/022/023)
7bbf41b fix: ReDoS multi-char probe, epic enrichment custom IDs, splitlines consistency (BH21-011/017/021)
9c5c37d refactor: consolidate duplicated logic, remove dead wrappers, fix FakeGitHub PR schema (BH21-009/012-016/018)
```

## Analysis

**Hot spots and why:**

- **BUG-HUNTER-PUNCHLIST.md / BUG-HUNTER-STATUS.md** (15, 12 hits): Pure tracking docs updated every bug-hunter pass. Not a code risk signal.

- **scripts/validate_config.py** (14 hits): The shared library that everything imports. High churn because it's the integration point — new features (TF dataclass, kanban states, get_base_branch, etc.) land here. High-value target for bugs since errors here propagate everywhere.

- **tests/test_verify_fixes.py** (10 hits): Growing regression test file. Added new test classes for every bug-hunter pass. Size and complexity have grown significantly.

- **tests/test_sprint_runtime.py** (9 hits): Core runtime behavior tests, heavily updated alongside sync_tracking.py and kanban.py changes.

- **skills/sprint-run/scripts/sync_tracking.py** (8 hits): Frequently adjusted — this is the "GitHub as source of truth" sync logic, touched by both new features and bug fixes.

- **tests/test_kanban.py** (7 hits): New test file for the just-added kanban.py state machine (last ~10 commits).

- **skills/sprint-setup/scripts/populate_issues.py** (6 hits): Milestone→issue parsing has had several fix passes (sprint detection, enrichment edge cases, dedup).

- **scripts/manage_epics.py** (6 hits): Epic CRUD. Multiple bug-fix passes suggest complex parsing logic.

- **scripts/kanban.py** (4 hits): Newly added in the last 10 commits (centralized state machine).

**Emerging pattern:** The kanban state machine (kanban.py, validate_config.py TF extraction, sync_tracking.py) is the current active surface. validate_config.py and sync_tracking.py are the two files most likely to harbor latent bugs given their role as shared infrastructure under continuous change.
