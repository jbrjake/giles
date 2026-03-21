## Part 1: The Theater Teacher

*"You've built an improv troupe that writes software. Let's talk about what makes ensembles actually work."*

### 1. Emotional Memory

Right now, persona files are static. Sable always cares about cache lines. Conor always says "that's not ideal" when things are catastrophic. But real characters accumulate experience. After Sprint 3, a persona who had a brutal review cycle on a concurrency bug should carry that scar. Add a `## History` section to persona files that the retro appends to. Not a full diary. Just two or three lines per sprint: what they worked on, what surprised them, what they'd be wary of next time. When the implementer subagent loads their character, they'd read this and it would color their decisions. Sable, who got burned by a lock contention bug in Sprint 2, would be quicker to reach for lock-free data structures in Sprint 5. Characters who learn are characters who live.

### 2. Status Games

Every interesting scene has a status dynamic. Who has authority right now? Who's deferring to whom? The reviewer always has structural power over the implementer, but that's one-dimensional. What if personas had explicit status relationships? "Zara defers to Sable on memory layout but pushes back hard on API design." "Conor and Zara have a running argument about error handling philosophy." These tensions would make reviews actually interesting. When Zara reviews Conor's error handling, she should be harder on him than on anyone else, because they disagree about something real. That's where drama lives.

Use the team topology and personas to achieve this, it's already baked in.

### 6. Scene Beats

The kickoff ceremony has an agenda, but it doesn't have beats. A beat is the smallest unit of dramatic action: something changes. In a kickoff, the beats might be: (1) PM states goal, everyone nods. (2) First story presented, implementer is confident. (3) Second story presented, implementer raises a concern. (4) Concern creates tension. (5) Tension resolved by user. Each beat shifts the energy. Right now, the story walk just iterates through stories in priority order. Instead, the PM persona should read the room: after a complex story discussion, follow up with a simpler one to let things breathe. After a story with no concerns, probe harder. "Really? No concerns from anyone? Zara, what happens when we get 10 million of those?" Facilitation should have rhythm.

### 7. Character Relationships Are Not Symmetric

The persona guide says "the reviewer is ALWAYS a different persona from the implementer." Fine. But it doesn't track relationships. In any ensemble, the dynamic between A and B is different from the dynamic between A and C. Create a lightweight relationship matrix in the team index. Not pages of backstory. Just a few words: "Sable and Conor: respectful disagreement on error handling." "Zara and Sable: Zara pushes Sable to think about adversarial inputs; Sable pushes Zara to think about memory." When you know the relationship, the review reads differently. It's the difference between "this variable name is unclear" and "we've talked about this before, Conor. Name your variables like someone else has to read them at 2am."

Leverage the team personas and topology for this, it's already baked in.

### 8. The Callback

Good ensembles reference earlier scenes. If a persona raised a risk in kickoff that turned out to be real, the demo should call back to it. "I said during kickoff that this API would be tricky to test, and I was right. Here's how I solved it." If a retro action item from Sprint 2 is relevant to a Sprint 4 story, the persona should say so. This requires the persona to have access to previous ceremony docs, which they technically do (they're in sprints_dir), but nothing in the current prompts encourages looking backward. Add a line to the implementer subagent: "Before starting, scan previous sprint retros for action items relevant to this story." Make the characters remember their own show.

### 11. The Stage Manager

The PM persona facilitates ceremonies, but there's no stage manager. In theater, the stage manager is the person who keeps the show running when things go sideways. The director (user) makes creative decisions. The stage manager makes sure transitions happen cleanly. Right now, sprint-run itself is the stage manager, but it's also the director, and also the lighting designer. What if the PM persona explicitly took on stage management duties between ceremonies? Posting status updates. Noticing when a review has gone three rounds. Flagging when velocity suggests the sprint is at risk. The PM becomes an active presence throughout the sprint, not just during ceremonies.

User feedback: The stage manager should, instead of the PM, be Giles personified, modeled on an comically exasperated but ever gentlemanly British librarian in kind of a butler-like role.

### 12. Ensemble vs. Star Vehicle

Some shows are ensemble pieces. Some are star vehicles. Right now, giles treats every sprint as an ensemble piece, which is good. But sometimes a sprint is really about one big feature, and the other stories are supporting cast. Recognize this. When one story has 3x the story points of everything else, the PM should frame the sprint around it. "This is Sable's sprint. Everyone else is in a supporting role." It changes the energy. The other personas focus their review attention on that big story. The demo spends 60% of its time on it. Naming the star doesn't diminish the ensemble; it gives the sprint a spine.

---

## Part 2: The Agile Process Coach

*"I've seen a thousand retros produce sticky notes that go in the trash. This system actually writes the changes into the codebase. That alone is worth the price of admission. But there's more to get right."*

### 4. Ceremonies Should Earn Their Time

The current structure is: kickoff, then stories, then demo, then retro. Every sprint. This is the standard Scrum cadence and it makes sense. But after the 5th sprint on the same project, the kickoff might be a formality. The team knows the codebase. They know each other's concerns. If the PM reads the room and all personas respond with "no concerns, let's go," the kickoff should be allowed to be short. Add a "confidence check" after the story walk. If all personas express high confidence and the user agrees, skip the extended risk discussion and commit immediately. Don't cargo-cult the ceremony. Let the team earn the right to move fast. Similarly, if a sprint is entirely bug fixes, the demo can be abbreviated. "Tests pass. Here are the before/after outputs. Next."

### 5. Feedback Loops Within the Sprint

Right now, feedback happens at review time and at retro. That's two feedback loops per sprint. In my experience, shorter feedback loops produce better outcomes. Add a mid-sprint check-in. Not a full ceremony. Just the PM persona doing a quick sync after half the stories are through dev: "How are we tracking? Any stories taking longer than expected? Any design decisions we should revisit before more code gets written?" This is where you catch the problem of two personas building in different directions. It's cheap and it prevents demo-day surprises.

### 6. Explicit Definition of Done (That Evolves)

The kanban protocol says done requires CI green, PR approved, merged, issue closed, burndown updated. That's the mechanical definition. But "done" should also be semantic. Does the feature actually solve the user's problem? The acceptance criteria in the story are a proxy, but they were written at planning time, before anyone knew how the implementation would go. Add a "definition of done" section to the sprint-level config that starts generic and gets refined by retros. Sprint 1's DoD might be "tests pass and acceptance criteria met." By Sprint 5, retros might have added: "error messages follow the format in rules.md," "performance-sensitive code has benchmark results," "new public APIs have usage examples." The DoD becomes a living document.

### 7. Scope Negotiation Is a Skill

The kickoff protocol says: "If the sprint is over capacity, the PM negotiates scope reduction with the user until commitment is reached." This is glossed over. Scope negotiation is where most sprints succeed or fail. Give the PM persona a framework. When cutting scope, evaluate stories on two axes: value to the milestone goal and dependency risk. Stories that are high-value and low-dependency stay. Stories that are low-value and high-dependency go first. Stories in the middle get discussed. The PM should present this as a 2x2 to the user, not just ask "what should we cut?" A PM who makes cutting feel analytical instead of painful is a PM worth having.

### 8. Pair Reviews

The current model is 1 implementer, 1 reviewer. What about pair reviews for high-risk stories? Two reviewers looking at the same PR, bringing different expertise. Sable reviews for performance, Zara reviews for security. They might disagree. That's the point. The implementer gets two perspectives and has to reconcile them. This is expensive (two review cycles), so reserve it for stories above a certain point threshold or stories that touch critical paths. Add a `pair_review: true` flag that sprint-run sets when a story is both high-point and touches files that multiple personas have domain ownership over.

### 9. Sprint Themes

Milestones have goals. But sprints within a milestone often feel undifferentiated. "We're doing the next batch of stories." Give each sprint a theme that the PM articulates during kickoff. Not a slogan. A focus area. "This sprint is about hardening the API layer." "This sprint is about catching up on test debt." The theme influences how personas approach their work. In a hardening sprint, the reviewer is pickier about edge cases. In a test debt sprint, the implementer writes more tests per line of production code. The theme isn't a constraint; it's a lens. And it gives the retro a natural anchor: "Did we achieve what we set out to focus on?"

### 11. Psychological Safety (for the User)

This is weird to say about a system with no real people, but hear me out. The user is the only human in the room. When three personas push back on a story during kickoff, it can feel like getting ganged up on. When a reviewer requests changes on something the user thought was fine, it can feel like criticism. The PM persona should be explicitly calibrated to protect the user's experience. After a tough review cycle: "I know that was a lot of rounds, but the code is genuinely better for it." After cutting scope: "We'll get to those stories. This is the right call for this sprint." It's not sycophancy. It's facilitation. A good scrum master makes the product owner feel supported, especially when the team is pushing back.

### 12. Cross-Sprint Learning

Velocity tracking across sprints is a start, but the system should also track qualitative patterns. Which types of stories consistently take more review rounds? Which personas have the smoothest review cycles together? Which domain areas produce the most retro action items? This is meta-data that accumulates over the life of a project and makes sprint planning smarter over time. A persistent `sprint-config/analytics.md` that gets a few lines added each retro. Not a dashboard. Just a growing document that the PM can reference during planning. "Last three sprints, API stories averaged 2.3 review rounds. Infrastructure stories averaged 1.1. Plan accordingly."

---

## Part 3: The Agentic Coding Engineer

*"I've been shipping features with Claude Code for months. Some of what this plugin does makes me grin. Some of it makes me wince. Here's what I think."*

### 1. Context Budget Awareness

This is the thing that will kill you before anything else does. Sprint-run loads: the SKILL.md, the ceremony reference, the persona guide, the persona file, the story details, the PRD excerpts, the rules file, the tracking files. That's a LOT of context. Every token spent on ceremony is a token not spent on implementation. The implementer subagent should have a context budget strategy. Load the persona file and rules at the start. Load PRD excerpts on demand, not upfront. When context gets long, summarize design notes instead of carrying the full text. Add explicit guidance to the implementer subagent: "If your context exceeds 50% of the window, summarize your design notes and drop the PRD excerpts. You've already internalized them." Context management is the difference between an agent that finishes stories and one that starts hallucinating at the 80% mark.

### 2. The Persona Cache

Here's a concrete implementation idea. When sprint-run dispatches an implementer subagent, it templates the persona into the prompt. But if the same persona implements three stories in a row, they're re-reading their own character file three times. Create a `sprint-config/.persona-cache/` directory that stores pre-rendered persona prompts. Not the full subagent template, just the character-specific parts: voice, review focus, domain, history (if idea #1 from the theater section happens). These get invalidated when the persona file changes (check mtime). Small optimization, but it adds up across a sprint.

### 3. Checkpoint and Resume

The context recovery reference exists, but it's reactive. You lose context and then try to figure out where you were. Instead, build checkpoints INTO the workflow. After every kanban transition, write a checkpoint file to `sprint-config/.checkpoints/{story_id}.json` with: current state, design decisions made so far, files modified, tests written, open questions. When the agent picks up a story, it reads the checkpoint first. This isn't the tracking file (which is for humans and ceremonies). This is machine-readable state specifically designed for agent resumption. Include a hash of the relevant source files so the agent can detect if someone edited code while it was away.

### 4. The Review Diff Problem

The reviewer subagent runs `gh pr diff` and reviews the whole thing. On a big story, that's hundreds of lines of diff. The reviewer is supposed to check correctness, conventions, security, file sizes, testing, and progressive disclosure. That's too many concerns for one pass through a long diff. Split the review into passes. First pass: correctness and acceptance criteria (does the code do what it's supposed to?). Second pass: conventions and style (does it follow the rules?). Third pass: testing (are the tests adequate?). Each pass produces findings. Then the reviewer synthesizes. This is how good human reviewers actually work. They don't catch everything in one read. Neither will an agent.

### 8. The Confidence Signal

When an agent writes code, it knows (sort of) how confident it is. A straightforward CRUD endpoint? High confidence. A custom lock-free concurrent data structure? Low confidence. Surface this. Have the implementer include a confidence annotation in their PR description. "Confidence: high on the API layer, medium on the serialization logic, low on the edge case handling in parse_header." The reviewer can then spend proportionally more time on the low-confidence areas. The demo can probe harder on the low-confidence features. It's metadata that makes every downstream step smarter.

### 9. Plugin Composition

Giles already depends on superpowers for TDD and parallel dispatch. But the Claude Code plugin ecosystem is growing. What about composing with other plugins? A documentation plugin that generates API docs from code. A testing plugin that generates property-based tests. A security plugin that runs SAST. Instead of building all these capabilities into giles, define integration points. The implementer subagent should have a hook: "after implementation, run these additional skills." The reviewer subagent should have a hook: "before review, run these analysis skills." Make giles an orchestration layer that's good at managing people (personas) and process (ceremonies), and let specialized plugins handle specialized tasks.

### 10. Sprint-Monitor as a First-Class Loop Agent

The architecture has sprint-monitor designed for `/loop 5m sprint-monitor`. This is correct and good. But the current monitor just checks CI status, PR status, and milestone progress. It should also watch for drift. Is a story's branch diverging too far from main? Did someone push directly to main while a sprint is running? Did a dependency update break something? Sprint-monitor should be the system's peripheral vision. It runs in the background and surfaces things the focused agents miss. Think of it as the nervous system. The implementer and reviewer are the hands. The monitor is the eyes looking around while the hands are busy.

### 12. Offline Mode

Not every project is on GitHub. Not every developer wants to push to a remote during development. Build an offline mode where giles tracks everything locally. Kanban state lives in markdown files instead of GitHub labels. PR reviews happen as local files instead of GitHub comments. When the developer is ready, a sync command pushes everything to GitHub in one shot: creates issues, opens PRs, posts reviews. This would make giles usable for prototyping, for private projects, for airgapped environments. The ceremony system works fine without GitHub. The tracking system is the part that needs an abstraction layer.

### 14. The Context Window Is the Sprint Timebox

Here's a philosophical one. In real agile, the sprint timebox forces prioritization. You can't do everything, so you do the most important things. With agentic coding, the equivalent constraint is the context window. The agent can't hold everything in its head, so it needs to prioritize what it remembers. Lean into this. Instead of fighting context limits with summarization and caching (which you should still do), also use them as a design constraint. A story that requires more context than fits in 40% of the window is too big. A ceremony that takes more than 10% of the window is too elaborate. A persona file that takes more than 5% of the window has too much backstory. Set context budgets the way you set time budgets. It's a weird but natural fit.

---

## Cross-Cutting Themes

A few ideas that came up from all three directions at once:

**Memory matters.** The theater teacher wants character history. The process coach wants cross-sprint analytics. The engineer wants checkpoints. All three are saying the same thing: a system that forgets everything between invocations is leaving value on the floor.

**Relationships are underspecified.** The personas exist as individuals but barely interact as an ensemble. The review relationship is the only structured interaction, and it's one-dimensional. Status dynamics, recurring disagreements, teaching relationships, and trust levels would all make the system richer AND produce better code reviews.

User feedback: all the relationship stuff is declared in the team personas and topology, leverage it.

**The PM persona is underutilized.** Right now they show up for ceremonies and disappear. They should be the connective tissue. Sprint-monitor is doing some of this, but it's impersonal. The PM should be a character with opinions about how the sprint is going, not just a reporting function.

User feedback: instead of the PM, the stsge management should be Giles personified, modeled on an comically exasperated but ever gentlemanly British librarian in kind of a butler-like role. Give him his own detailed persona file.

**Context is the scarce resource.** Every feature idea needs to pass the test: "Is this worth the context tokens it will cost?" Some ideas here are cheap (checkpoint files, confidence signals). Some are expensive (pair reviews, pre-mortems). The expensive ones should be opt-in.
