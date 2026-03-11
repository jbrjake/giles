# giles

Agile agentic development that takes it too far.

Giles is a Claude Code plugin that runs full agile sprints with fictional team
personas. They write code, review each other's PRs on GitHub, debate technical
risks during kickoff, and hold retrospectives that change your actual project
documentation. Everything flows through GitHub issues, PRs, milestones, and a
six-state kanban.

## Give your personas backstories

The persona system is where giles gets interesting, and the more detail you put
in, the more you get out.

The template asks for role, domain, voice, review focus, and background. You
*can* fill those in with a sentence each and call it done. But the personas that
work best have full backstories with character arcs. Physical descriptions.
Mannerisms. Grounded motivations for why they care about the project succeeding,
because it means something to them professionally and emotionally.

A persona who "contributed to several Rust crates and believes `unsafe` needs
justified comments longer than the block itself" reviews code differently from
a generic "senior developer." A QA persona who "keeps a personal list of bugs
per sprint" and asks "but what if the input is empty?" brings a specific,
skeptical energy to every review.

When Rusti reviews a PR, the comments focus on ownership patterns, lifetime
elision, and idiomatic error handling. When Checker reviews the same PR, they
want edge case tests and panic path coverage. The review perspective follows
from who the person is, not from a generic checklist.

That depth compounds. During sprint kickoff, personas raise risks from their
domain: the systems programmer worries about memory safety, the UX person
worries about CLI output formatting, the QA lead worries about boundary
conditions nobody planned tests for. These are real concerns that surface real
gaps in your stories.

## Sprints are interactive

This is not a "press go and wait" system. You are the product owner.

During **kickoff**, the PM persona presents each story. The assigned implementer
and reviewer respond in character with initial thoughts, dependencies, and
concerns. Then the team raises risks: technical, design, capacity. You answer
their questions. If questions reveal missing work, new issues get created on the
spot. The sprint doesn't start until the team confirms commitment to the scope.

During **story execution**, implementer subagents write code using TDD, create
PRs with self-contained descriptions (the reviewer should never need external
docs), and reviewer subagents evaluate from their persona's area of expertise.
Stories move through the kanban: TODO, DESIGN, DEV, REVIEW, INTEGRATION, DONE.
You see it all on GitHub.

During **demo**, each implementer presents their work with real build output,
real test results, and real artifacts saved to the sprint directory. You walk
through acceptance criteria with evidence. No slideware.

During **retro**, personas reflect on what worked and what hurt. This is the
part that matters most.

## Retros change your project

A retrospective with no documentation changes is a failed retrospective. That's
the rule.

After the team shares Start/Stop/Continue feedback, giles distills patterns,
identifies which project file each pattern affects, and proposes specific edits:
add this anti-pattern to the project rules, update this naming convention,
strengthen the PR description requirements, add a dependency check to the
kickoff ceremony. You approve each change before it's applied.

Over multiple sprints, the project's rules, conventions, and process documents
accumulate real lessons from real development. The sprint 4 team works under
better rules than the sprint 1 team because the sprint 1 team's retro identified
what was missing.

This is not "self-learning." It's structured process improvement driven by
retrospective feedback, the same thing good agile teams do, except here it
happens every time because the ceremony enforces it.

## Everything lives on GitHub

Every story becomes a GitHub issue with labels for persona, sprint, saga,
priority, kanban state, and type. Milestones group stories. PRs carry persona
headers identifying who wrote the code and from what perspective. Code reviews
happen on GitHub with inline comments in the reviewer's voice.

You can watch the burndown on GitHub. You can read code reviews between your
fictional teammates. You can look at the kanban board and see which stories
are in development, which are in review, which are blocked.

If you lose your Claude session mid-sprint, run `/sprint-run` again. It reads
GitHub state and local tracking files to figure out where you left off, and
picks up from there.

## Quick start

1. Install the plugin:
   ```
   claude plugin add jbrjake/giles
   ```

2. Bootstrap your project:
   ```
   /sprint-setup
   ```
   This scans your project, generates `sprint-config/`, and creates all GitHub
   labels, milestones, and issues for every sprint upfront so you can watch the
   full burndown from day one.

3. Run your first sprint:
   ```
   /sprint-run
   ```

4. Monitor progress (optional):
   ```
   /loop 5m sprint-monitor
   ```

## Skills

| Skill | What it does |
|-------|-------------|
| `sprint-setup` | One-time bootstrap: scans project, generates config, creates all GitHub labels/milestones/issues, sets up CI |
| `sprint-run` | Runs a sprint: kickoff, story execution (TDD, PRs, reviews), demo, retro |
| `sprint-monitor` | Checks CI status, open PRs, and burndown (designed for `/loop`) |
| `sprint-release` | Release gating: validates milestones, tags, creates GitHub Releases |
| `sprint-teardown` | Removes `sprint-config/` safely without touching original project files |

## Project structure

Giles expects your project to have:

- **Team personas** in markdown: name, role, domain, voice, review focus,
  background. The deeper the better. See above.
- **Sprint backlog** as milestone files with story tables
  (`| US-NNNN | title | saga | SP | priority |`)
- **Project rules** documenting your coding standards and conventions

The `sprint-setup` skill scans for these files automatically and creates
symlinks into `sprint-config/`. If they don't exist, it generates templates.

## Configuration

All project-specific values live in `sprint-config/project.toml`, generated by
`sprint-setup`:

- `[project]` -- name, repo, language
- `[paths]` -- team_dir, backlog_dir, sprints_dir
- `[ci]` -- check_commands, build_command
- `[conventions]` -- commit format, branch naming

## FAQ

**Do I need to write the persona files myself?**
You can use the generated templates, but you should expand them. A paragraph
for each section is fine. Two paragraphs is better. Give them opinions about
their craft, things that annoy them in code review, reasons they're invested
in this particular project.

**What languages does the CI generator support?**
Rust, Python, Node.js, and Go out of the box. Other languages work but need
manual CI configuration.

**Can I use giles without GitHub?**
No. Giles uses `gh` CLI for issues, PRs, labels, milestones, and code reviews.
GitHub is required.

**How do I add stories mid-sprint?**
Add them to the milestone file in `sprint-config/backlog/milestones/`, then
re-run `populate_issues.py`. It's idempotent and won't duplicate existing issues.

**What if I lose context mid-sprint?**
Run `/sprint-run` again. It detects the current phase from `SPRINT-STATUS.md`
and GitHub state, then resumes from where it left off.

**How are stories assigned to personas?**
By domain keywords. Each persona's profile lists their domain expertise, and
stories are matched to the persona whose keywords fit best. The reviewer is
always a different persona from the implementer.

## Requirements

- Claude Code
- GitHub CLI (`gh`) installed and authenticated
- Python 3.10+ (for sprint scripts, stdlib only, no pip packages)
- A GitHub repository with a configured remote

## License

MIT
