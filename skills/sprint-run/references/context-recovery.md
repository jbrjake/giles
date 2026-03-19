<!-- §context-recovery.context_recovery_6_step_state_reconstruction_after_context_loss -->
# Context Recovery

If Claude loses context mid-sprint (new conversation, context window
overflow, etc.), reconstruct state before resuming. All paths are read
from `config [paths]`:

1. Read `{sprints_dir}/SPRINT-STATUS.md` -- current sprint number,
   phase, velocity history.
2. Read `{sprints_dir}/sprint-{N}/burndown.md` -- what is done,
   what is in-flight.
3. Read in-flight story files in
   `{sprints_dir}/sprint-{N}/stories/` -- YAML frontmatter has
   exact state (status, branch, PR number, issue number).
4. Run `"${CLAUDE_PLUGIN_ROOT}/skills/sprint-run/scripts/sync_tracking.py" {sprint_number}` to reconcile local tracking files
   with GitHub state (issues, PRs, labels).
5. Query GitHub directly:
   - `gh issue list --milestone "Sprint {N}"`
   - `gh pr list --label "sprint:{N}"`
6. Resume from the detected phase via the phase detection table in SKILL.md.

Context recovery is aggressive by design. Every piece of sprint state
is persisted to files or GitHub, so no information depends on
conversation memory alone.
