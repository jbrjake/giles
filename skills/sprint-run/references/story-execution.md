# Story Execution Reference

Stories flow through four kanban states. Each transition has clear
exit criteria. The goal is to keep stories moving while maintaining
quality through persona-based review.

See `kanban-protocol.md` for the full state machine and transition rules.
See `persona-guide.md` for persona assignment and pairing rules.

---

## TO-DO --> DESIGN

The implementer persona reads the story requirements, relevant PRDs,
and acceptance criteria, then produces a design.

1. Write design notes in
   `{sprints_dir}/sprint-{N}/stories/US-XXXX-slug.md`.
2. Create branch using the pattern from
   `config [conventions] branch_pattern` (e.g., `sprint-{N}/US-XXXX-slug`).
   ```bash
   git checkout -b {branch_name} {base_branch}
   git push -u origin {branch_name}
   ```
3. Open a **draft PR** with full context in the description:
   - Story ID, title, acceptance criteria (copied in full)
   - Relevant PRD excerpts (so the reviewer can work entirely from the
     PR -- no external doc lookup needed)
   - Design decisions and rationale
   - Persona header: who implements, who reviews
   - Links to related stories/PRDs (for reference, not required reading)
   ```bash
   gh pr create --draft --base {base_branch} --head {branch_name} \
     --title "{story_id}: {story_title}" \
     --body "{pr_description}"
   ```
4. Apply labels: persona, sprint, saga, priority, `kanban:design`.
   ```bash
   gh pr edit {pr_number} --add-label "persona:{persona},sprint:{N},saga:{saga},priority:{pri},kanban:design"
   gh issue edit {issue_number} --remove-label "kanban:todo" --add-label "kanban:design"
   ```

The PR description carries full context because reviewers should never
need to leave the PR to understand what they are reviewing.

### Commit Convention

All commits MUST use the conventional commit wrapper:

```bash
python {plugin_root}/scripts/commit.py "feat(module): description"
```

Do not use raw `git commit -m`. The wrapper validates message format and
checks atomicity. See `scripts/commit.py --help` for flags.

---

## DESIGN --> DEVELOPMENT

Dispatch the implementer as a subagent. Read `agents/implementer.md`
for the full agent protocol. The implementer's persona file (from
`{config [paths] team_dir}/`) provides voice, domain focus, and
review style.

1. Subagent works in-persona.
2. Invoke `superpowers:test-driven-development` -- write failing tests
   first, then implement until tests pass.
3. If `config [paths] cheatsheet` or `config [paths] architecture`
   are defined, update those progressive disclosure docs in lockstep
   with code changes. Code without updated docs is incomplete work.
4. Push commits to the branch. Mark PR as ready for review.
   ```bash
   git push origin {branch_name}
   gh pr ready {pr_number}
   gh issue edit {issue_number} --remove-label "kanban:design" --add-label "kanban:dev"
   ```

---

## DEVELOPMENT --> REVIEW

Dispatch the reviewer as a subagent. Read `agents/reviewer.md` for the
full agent protocol. The reviewer's persona file (from
`{config [paths] team_dir}/`) provides voice and review perspective.

1. Reviewer is a **different persona** than the implementer. Read
   `persona-guide.md` for the pairing rules.
2. Reviewer posts a GitHub PR review with a persona header identifying
   who they are and what perspective they bring.
3. Review is conducted entirely from the PR description + diff. This
   validates that the PR description is actually sufficient. If the
   reviewer needs to read external docs to understand the change, that
   is a defect in the PR description, not a defect in the reviewer.
4. If approved: proceed to integration.
5. If changes requested: implementer addresses feedback, then
   re-requests review. This loop repeats until approval.
6. Update the GitHub issue label to `kanban:review`.

---

## REVIEW --> INTEGRATION

1. Confirm CI is green:
   ```bash
   gh pr checks {pr_number} --watch
   ```
2. Invoke `superpowers:verification-before-completion` to run the
   project's verification suite.
3. Squash-merge the PR to the base branch:
   ```bash
   gh pr merge {pr_number} --squash --delete-branch
   ```
4. Update the GitHub issue label and close:
   ```bash
   gh issue edit {issue_number} --remove-label "kanban:review" --add-label "kanban:done"
   gh issue close {issue_number}
   ```
5. Update burndown:
   ```bash
   python skills/sprint-run/scripts/update_burndown.py
   ```
6. Update story tracking file: set status = done, record completion date.
7. Update `SPRINT-STATUS.md` with the completed story.

---

## Parallel Dispatch

Check the story dependency graph before dispatching. Stories with no
dependencies on in-progress work can run simultaneously using
`superpowers:dispatching-parallel-agents`.

Stories that depend on an in-progress story wait. This is enforced
rather than advisory because merging dependent work out of order creates
integration nightmares that cost more time than the parallelism saves.
