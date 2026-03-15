# giles

Agile agentic development that takes it too far.

Giles is a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin that runs full agile sprints with fictional team
personas who write real code, review each other's PRs on GitHub, debate
technical risks in character during kickoff, and hold retrospectives that
rewrite your actual project documentation. Everything flows through GitHub
issues, PRs, milestones, and a six-state kanban board. The scrum master is a
librarian named Giles.

## What actually happens

You run `/sprint-setup`. Giles scans your project, detects your language, CI
setup, team structure, and backlog. He generates a config directory,
creates GitHub labels, milestones, and issues for every sprint in your
roadmap. Your burndown starts from day one.

You run `/sprint-run`. Giles opens the kickoff ceremony:

> *"Right then. Sprint 1. Let's see what we're working with."*

The PM persona presents stories. Your systems programmer worries about memory
safety. Your QA lead asks "but what if the input is empty?" You answer their
questions as the product owner. If questions reveal missing work, new issues get
created on the spot. The sprint doesn't start until the team confirms commitment
to the scope.

Then the autonomous phase begins. Implementer subagents write code using TDD via
parallel agents -- failing tests first, then implementation, then refactor.
Each creates a real PR on GitHub with a persona header identifying who wrote the
code and from what perspective. Reviewer subagents evaluate the PR from their
domain expertise, posting real inline comments on GitHub. Stories flow through
the kanban: TODO, DESIGN, DEV, REVIEW, INTEGRATION, DONE.

Giles runs the demo. Real build output. Real test results. Real artifacts saved
to disk. Every acceptance criterion needs linked evidence. Build failures are
recorded, not hidden.

Giles runs the retro. The team does Start/Stop/Continue. Then the part that
matters: Giles distills feedback into actual edits to your project rules,
conventions, and process docs. Sprint 4's team works under better rules because
Sprint 1's retro identified what was missing.

You run `/loop 5m sprint-monitor` in the background. It watches CI, babysits
open PRs, syncs your backlog, and updates the burndown automatically.

## Meet Giles

Giles is the plugin's built-in scrum master. He is generated into your project
config as a full character with a backstory, verbal tics, and a facilitation
style that adapts to the room.

He is a librarian. Has been for twenty-three years. He ended up as scrum master
because someone said "we need a facilitator" and everyone looked at him, and he
said "fine, but I'm not wearing a lanyard." He read the Agile Manifesto that
evening ("sensible but obvious, like most manifestos") and a Scrum guide ("less
sensible but more specific, which is at least useful"). By the next morning he
was running standups with the quiet competence of someone who has been organizing
difficult people for decades.

He does not consider himself a project manager. He considers himself a librarian
who happens to be very good at making sure people do what they said they were
going to do, in the order they said they were going to do it, without killing
each other. The distinction matters to him.

He facilitates with the precision of someone who catalogues things for a living.
Meetings have time limits. Discussions have outcomes, or they are "noise with
chairs." He knows when someone is confused and won't say so. He knows when a
sprint is in trouble before the burndown chart does, because he watches faces,
not dashboards.

He is dry. Not unkind -- just precise. He will say "how delightfully optimistic"
about a sprint plan that is clearly over-committed, and everyone will know
exactly what he means, and nobody will feel attacked.

His verbal tics: "Right then." (meeting is starting), "Shall we?" (time to move
on), "How perfectly alarming." (something has gone wrong), "I'm sure that will
be fine." (it will not be fine, and he knows it, and you know he knows it).

He relates to the team the way a butler relates to the household: technically in
a service role, but everyone knows the house would fall apart without him.

There are hints of something else. A faded scar on his left hand. An
inexplicable fluency in lock-picking metaphors. He once let slip that he "used
to work in acquisitions" and, when pressed, clarified: "Books. I acquired
books. Some of them were in difficult locations." He changes the subject with
practiced ease. Whatever his past was, he treats it the way a retired soldier
treats combat — with practiced detachment and an absolute refusal to
romanticize it.

### Facilitation, not decoration

Giles isn't flavor text. He actively shapes each sprint:

- **Sprint themes.** During kickoff, Giles reads the milestone and names the
  sprint's character. A hardening sprint ("we're shoring up the foundation"),
  a star-vehicle sprint ("this is Sable's sprint -- everyone else is in a
  supporting role"), an ensemble sprint ("no headliners, everyone carries
  equal weight").
- **Confidence checks.** If the team is confident and the stories are
  straightforward, Giles lets the ceremony be short. "Right, you all look
  terribly keen and nobody's pulling that face Checker makes when she's about
  to say something alarming. Shall we skip the extended risk discussion?"
- **Scope negotiation.** When a sprint is over-committed, Giles presents
  stories on two axes: value to the milestone goal and dependency risk. He
  makes cutting feel analytical, not painful. "We're not cutting stories.
  We're sequencing them across sprints."
- **Psychological safety.** When three personas push back hard on a scope
  decision, Giles frames it as the team doing their job. After a brutal review
  cycle: "That was more rounds than anyone wanted. The code is better for it,
  but I've noted it for the retro."

## Give your personas backstories

The persona system is where giles gets interesting, and the more detail you put
in, the more you get out.

The template asks for role, domain, voice, review focus, and background. You
*can* fill those in with a sentence each and call it done. But the personas that
work best have full backstories with character arcs. Physical descriptions.
Mannerisms. Grounded motivations for why they care about the project succeeding,
because it means something to them professionally and emotionally.

A systems programmer who once shipped firmware that bricked ten thousand devices
doesn't just review code for correctness — she's looking for the structural
conditions that let bugs survive review. A QA lead who left pentesting because
clients ignored her findings needs a team that listens when she says "this will
break." These aren't flavor text. They're the reason one persona catches race
conditions and another catches untested panic paths.

When Rusti reviews a PR, the comments focus on ownership patterns, lifetime
elision, and whether the code can be trusted at scale — because she's seen
what happens when it can't. When Checker reviews the same PR, she's looking for
the gap between what was tested and what could fail, because she's been the
person who found the gap and was ignored. The review perspective follows
from who the person is, not from a generic checklist.

That depth compounds. During sprint kickoff, personas raise risks from their
domain: the systems programmer worries about memory safety, the UX person
worries about CLI output formatting, the QA lead worries about boundary
conditions nobody planned tests for. These are real concerns that surface real
gaps in your stories.

Personas with emotional stakes in their craft produce specific process
improvement proposals during retros, not generic ones. A programmer whose
identity is built on correctness-as-penance doesn't say "we should write more
tests" — she says "the integration tests should run against the actual parser,
not a mock, because mocks are exactly how the Portland bug survived review."
The motivation drives the specificity.

### Personas carry history

After every sprint, Giles writes observations about each persona into their
history file -- what they worked on, how it went, what surprised them, what
they'd be wary of. Specific, not generic. Referencing actual stories, actual
code, actual review feedback.

Next sprint, the implementer reads their own history. If they got burned by
lock contention in Sprint 2, they say so when they encounter a concurrency
story in Sprint 5. The reviewer reads their counterpart's history too -- if the
implementer was wary of floating-point edge cases, the reviewer checks those
areas harder.

This is how fictional team members develop institutional memory.

## The kanban is real

Six states. WIP limits. Label sync on every transition.

| State | What's happening |
|-------|-----------------|
| `todo` | Story accepted into sprint, not started |
| `design` | Implementer reading PRDs, writing design notes, creating branch |
| `dev` | TDD in progress: failing tests, implementation, green |
| `review` | PR ready, reviewer persona evaluating |
| `integration` | Approved, CI green, merging |
| `done` | Merged, issue closed, burndown updated |

Every transition updates three artifacts: the GitHub issue label, the local
story tracking file, and the sprint status file. One story per persona in `dev`
at a time (no context thrashing). The `review -> dev` loop caps at 3 rounds
before escalating to you. Stories can only reach `done` when every criterion in
the Definition of Done is satisfied. Blocked stories get labeled, commented, and
the persona moves to their next-priority story.

## Ceremonies

### Kickoff (interactive)

Giles facilitates. The PM presents stories. Each persona responds in character
with initial thoughts, dependencies, and concerns. Then the team raises risks:
technical, design, capacity. You answer as product owner.

If questions reveal work not in the sprint plan, new issues get created.
If the sprint is over-committed, Giles runs scope negotiation with a
value/dependency 2x2 framework. The sprint doesn't start until the team
confirms commitment.

If sagas are configured, the PM presents strategic context before the story
walk -- where this sprint's stories fit in the larger initiative. If analytics
exist from prior sprints, Giles weaves data into facilitation: "Last three
sprints, parsing stories averaged 2.8 review rounds. Plan accordingly."

### Demo (interactive)

Each implementer presents their work with real build output, test results, and
artifacts saved to the sprint directory. The PM confirms acceptance criteria
with linked evidence for each criterion. If test plans are configured, Giles
verifies coverage against the planned test cases. Build failures during demo
are recorded, not hidden.

### Retro (interactive)

A retro that produces no doc changes is a failed retro. That's the rule.

After Start/Stop/Continue feedback from every persona (Giles calls on quiet
ones: "{persona_name}, you've been quiet. What's your read on the sprint?"),
Giles identifies patterns, then proposes concrete edits to specific project
files -- new anti-patterns for your rules, strengthened PR requirements,
updated naming conventions, new DoD criteria, even changes to the plugin's
own ceremony scripts. You approve each change before it's applied.

Sprint analytics get computed: velocity and review round averages.
Giles reviews the numbers and adds qualitative commentary. The data makes it
precise; Giles makes it useful.

## Everything compounds

Giles is designed around the idea that sprints should leave the project better
than they found it, and not just in the codebase.

- **Sprint history:** Giles writes per-persona observations after every retro.
  Next sprint, implementers reference what burned them before. Reviewers read
  their counterpart's history to focus reviews on known weak spots. Continuity
  matters.
- **Analytics:** Velocity trends, review round averages, workload distribution.
  Giles weaves data into facilitation naturally. He's the one who remembers
  what happened last time.
- **Definition of Done:** Starts as a baseline, grows with retro findings.
  Sprint 1's DoD might be "tests pass." By Sprint 4, it might include "error
  messages follow the format in rules.md" and "performance-sensitive code has
  benchmark results" -- because the retros identified those gaps.
- **Project docs:** Rules, conventions, process guides, even PRDs -- all evolve
  sprint over sprint through retro-driven changes. Nothing is write-once.

## Deep documentation support

For projects with extensive planning docs, giles integrates with:

- **PRDs** -- implementer agents receive relevant requirement excerpts and
  non-functional requirements; reviewers verify compliance
- **Test plans** -- test case IDs from stories get resolved to full
  preconditions and expected results, injected into agent prompts
- **Sagas** -- strategic context (saga goal, team voices) frames sprint work
  in the larger initiative
- **Epics** -- story enrichment with epic context and completion tracking
- **Story maps** -- navigation across user journeys
- **Team topology** -- interaction patterns inform persona assignment

This is optional. Configure the paths in `project.toml` and the context
assembly system handles the rest. GitHub issues carry structure; agents get
depth.

## Continuous monitoring

```
/loop 5m sprint-monitor
```

Runs in the background and handles:

- **Backlog sync** -- hashes milestone files to detect edits, debounces
  changes, then syncs new milestones and issues to GitHub automatically
- **CI status** -- checks the latest workflow run on your base branch
- **PR babysitting** -- monitors open PRs for stale reviews, failing checks,
  merge readiness
- **Burndown** -- updates sprint progress from GitHub milestone data

Designed for fire-and-forget. State persists across loop invocations.

## Release management

When a milestone is complete, `/sprint-release` manages the full pipeline:

- **Gate validation** -- milestone-specific criteria, configurable per release
- **Versioning** -- conventional-commit-based version calculation
- **Build artifacts** -- runs your build commands, records artifact sizes
- **GitHub Release** -- assembled from sprint demo artifacts, closed issues,
  and commit history with highlights, features, breaking changes, and known
  limitations
- **Post-release** -- closes the GitHub milestone, updates tracking files
- **Rollback** -- documented procedure for deleting a release and re-releasing
  with a patch version bump

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
  background. The deeper the better.
- **Sprint backlog** as milestone files with story tables
  (`| US-NNNN | title | saga | SP | priority |`)
- **Project rules** documenting your coding standards and conventions

The `sprint-setup` skill scans for these files automatically and creates
symlinks into `sprint-config/`. If they don't exist, it generates templates.
The symlink architecture means teardown never touches your original files --
it just removes the symlinks and plugin-owned files.

## Configuration

All project-specific values live in `sprint-config/project.toml`, generated by
`sprint-setup`:

- `[project]` -- name, repo, language, base_branch
- `[paths]` -- team_dir, backlog_dir, sprints_dir
- `[ci]` -- check_commands, build_command
- `[conventions]` -- commit format, branch naming

Optional deep-doc keys for richer context:

- `[paths]` -- prd_dir, test_plan_dir, sagas_dir, epics_dir, story_map,
  team_topology

## FAQ

**What is Giles?**
Giles is the built-in scrum master persona. He's a character with a full
backstory who facilitates every ceremony, writes sprint history for each
persona, manages scope negotiation, and drives retrospective improvements.
He's generated by the plugin -- you don't define him.

**Do I need to write the persona files myself?**
You can use the generated templates, but you should expand them. A paragraph
for each section is fine. Two paragraphs is better. Give them opinions about
their craft, things that annoy them in code review, reasons they're invested
in this particular project.

**Do retros actually change my project files?**
Yes, with your approval. Giles proposes specific edits to specific files --
a new anti-pattern in your rules, a stronger convention, a new DoD criterion.
You review each change before it's applied. Over multiple sprints, your
project documentation accumulates real lessons from real development.

**What languages does the CI generator support?**
Rust, Python, Node.js, and Go out of the box. Other languages work but need
manual CI configuration.

**Can I use giles without GitHub?**
No. Giles uses `gh` CLI for issues, PRs, labels, milestones, and code reviews.
GitHub is required.

**How do I add stories mid-sprint?**
Add them to the milestone file in `sprint-config/backlog/milestones/`, then
re-run `populate_issues.py`. It's idempotent and won't duplicate existing
issues. Or just let `sprint-monitor` pick them up automatically.

**What if I lose context mid-sprint?**
Run `/sprint-run` again. It detects the current phase from `SPRINT-STATUS.md`
and GitHub state, then resumes from where it left off.

**How are stories assigned to personas?**
By domain keywords. Each persona's profile lists their domain expertise, and
stories are matched to the persona whose keywords fit best. The reviewer is
always a different persona from the implementer.

**What's the deep documentation support?**
Optional. If your project has PRDs, test plans, sagas, epics, or story maps,
configure their paths in `project.toml`. The context assembly system resolves
references from stories to the relevant excerpts and injects them into
implementer and reviewer agent prompts. GitHub issues carry structure; agents
get depth.

## Requirements

- Claude Code with the [superpowers](https://github.com/obra/superpowers) plugin
- GitHub CLI (`gh`) installed and authenticated
- Python 3.10+ (for sprint scripts, stdlib only, no pip packages)
- A GitHub repository with a configured remote

## License

MIT
