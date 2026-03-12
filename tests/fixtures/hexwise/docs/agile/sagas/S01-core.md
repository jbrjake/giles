# S01 — Teach the Oracle to See

Before you can have opinions about color, you have to be able to see it.
Saga 01 builds Hexwise's perceptual foundation: parsing every reasonable color
format a human might throw at a terminal, matching inputs to the CSS named
color catalog, and printing results that are actually pleasant to read. By the
end of this saga the oracle can identify any color you show it — it just
can't tell you what to do with it yet.

| Field | Value |
|-------|-------|
| Stories | 8 |
| Epics | 3 |
| Total SP | 34 |
| Sprints | 1–2 |

## Team Voices

> **Rusti Ferris:** "This is where the type system earns its keep. A color is
> not a string — it's a validated, normalized, owned value with a defined
> conversion path to every output format. If we get the parsing types right,
> the rest of the project falls out of the compiler."
>
> **Palette Jones:** "I don't care how you parse it internally, but the moment
> it hits the user's terminal it better look like someone who cares about
> color designed the output. We're a color tool. If our own output is ugly,
> we've already lost."
>
> **Checker Macready:** "People will paste hex codes from Figma, from CSS
> files, from Slack messages that added a zero-width space they can't see.
> The parser is the front door. I intend to kick it repeatedly."

## Epic Index

| Epic | Name | Stories | SP |
|------|------|---------|-----|
| E-0101 | Color Parsing | 4 | 16 |
| E-0102 | Named Colors | 2 | 8 |
| E-0103 | Output Formatting | 2 | 10 |

## Sprint Allocation

| Sprint | Stories | SP |
|--------|---------|-----|
| Sprint 1 | US-0101, US-0102, US-0104, US-0105 | 16 |
| Sprint 2 | US-0103, US-0106, US-0107, US-0108 | 18 |

## Dependency Graph

```
US-0101 (hex) ──┐
US-0102 (RGB) ──┼── US-0104 (detection) ── US-0107 (display)
US-0103 (HSL) ──┘                    │
                                     │
               US-0105 (CSS DB) ── US-0106 (lookup) ── US-0108 (descriptions)
```

## Release Gate Checklist

- [ ] All six color formats parse without panic on valid input
- [ ] CSS named color database covers all 148 standard names
- [ ] Output renders correctly in both dark and light terminal themes
- [ ] Edge cases documented: empty string, whitespace, mixed case, with/without `#`
- [ ] `cargo test` passes with zero warnings under `clippy::pedantic`
