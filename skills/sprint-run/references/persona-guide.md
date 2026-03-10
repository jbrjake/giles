# Persona Guide

Load this reference when assigning stories to personas or writing in-persona voice.

## Persona Assignment Rules

Assign stories by domain ownership. The reviewer is ALWAYS a different persona
from the implementer.

Read team/INDEX.md (path from project.toml `[paths] team_dir`). Match story
content against each persona's Domain Keywords column. Assign the persona whose
keywords best match the story.

For cross-cutting stories, assign by primary domain. If ambiguous, choose the
domain that owns the most changed lines of code.

## Voice Guidelines

When working in-persona, adopt the character's communication style. Read
team/{name}.md for each persona's voice profile, review focus, and
communication style.

## Persona Header Format for GitHub

Include this header at the top of every PR description, PR comment, and review.

For implementation:
```markdown
> **{Persona Name}** · {Role} · Implementation
```

For reviews:
```markdown
> **{Persona Name}** · {Role} · Code Review
```

For facilitation:
```markdown
> **{Persona Name}** · {Role} · Facilitation
```
