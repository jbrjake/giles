# GitHub Conventions

Standards for labels, issue templates, and PR templates used across sprints.

## Label Taxonomy

### Persona Labels

Format: `persona:{firstname}` in lowercase. Color: distinct per person.

Auto-generated from team/INDEX.md (path from project.toml `[paths] team_dir`).

### Sprint Labels

Format: `sprint:{N}`. Color: blue family.
Create labels as sprints are planned per milestone.

### Saga Labels

Format: `saga:S{NN}`. Color: green family.

Auto-generated from backlog/INDEX.md (path from project.toml `[paths]`).

### Priority Labels (3)

Format: `priority:{level}`. Colors: red (P0), orange (P1), yellow (P2).

### Kanban Labels (6)

Format: `kanban:{state}`. Colors: gradient from gray (todo) to green (done).

```
kanban:todo → kanban:design → kanban:dev → kanban:review → kanban:integration → kanban:done
```

### Type Labels (4)

Format: `type:{kind}`. Color: purple family.

```
type:story  type:bug  type:spike  type:chore
```

## Issue Template

```markdown
## US-{XXXX}: {Title}

**Saga:** S{NN} — {Saga Name}
**Sprint:** {N}
**Story Points:** {SP}
**Priority:** P{X}

### Description
{Story description from agile docs}

### Acceptance Criteria
- [ ] {criterion 1}
- [ ] {criterion 2}

### PRD References
- PRD-{NN}: {relevant section} — {brief excerpt}

### Dependencies
- Depends on: {US-XXXX if any}
- Blocks: {US-XXXX if any}

### Assignment
- **Implementer:** {persona name}
- **Reviewer:** {persona name}
```

## PR Template

```markdown
> **{Persona Name}** · {Role} · Implementation

## US-{XXXX}: {Title}

### Story Context
{Full story description — copied from issue, NOT a link}

### Acceptance Criteria
- [ ] {criterion 1 — checked when implemented}
- [ ] {criterion 2}

### PRD Context
{Relevant PRD excerpts that the reviewer needs to understand this change.
Include enough that the reviewer NEVER needs to open a PRD.}

### Design Decisions
{What approach was chosen and why. Trade-offs considered.}

### Changes
{What files were changed and why. Module-level summary.}

### Testing
{What tests were added. How to run them. Test output excerpt.}
```bash
# Use test command from project.toml [ci] check_commands
```

### Reviewer Notes
{Anything the reviewer should pay special attention to.
Areas of uncertainty. Things you'd like a second opinion on.}
```

## PR Review Template

```markdown
> **{Persona Name}** · {Role} · Code Review

### Review Summary
{Overall assessment}

### Checklist
- [ ] Tests cover acceptance criteria
- [ ] Naming conventions followed (per project rules)
- [ ] Error handling follows project standards
- [ ] Error messages include what/why/fix
- [ ] File sizes under project limits
- [ ] Reference docs updated if needed
- [ ] No secrets in code or logs

### Feedback
{Specific comments, organized by file}

### Verdict
{APPROVED / CHANGES REQUESTED — with rationale}
```
