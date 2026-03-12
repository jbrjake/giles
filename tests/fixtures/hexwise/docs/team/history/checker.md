# Sprint History — Checker Macready

Appended by Giles after each sprint retro. Do not edit manually.

---

### Sprint 1 — First Light

Checker reviewed all four Sprint 1 stories and found edge cases in three of them before the implementers did. The hex parser did not initially handle the case where a user passes `#` with nothing after it, which Checker described as "an invitation to a segfault that just hasn't RSVP'd yet." Rusti fixed it within the hour and added three test cases that Checker deemed "acceptable."

The fixture naming detente with Palette was established this sprint. Checker wanted `test_input_001`; Palette wanted `viva_magenta`. They settled on `viva_magenta_empty_hex`, which Checker considers a tactical victory because the descriptive suffix is doing the actual work. Palette considers it a strategic victory because every test file now has color names in it. I consider it resolved and am not reopening the discussion.

**Worked on:** Reviews of US-0101, US-0102, US-0104, US-0105
**Surprised by:** The hex parser's initial blindness to the bare `#` input
**Wary of next time:** RGB parsing boundary values. She has a list of 47 "technically valid but wrong" RGB inputs that she has not yet deployed.

---

### Sprint 2 — Finding Words

Checker's adversarial testing reached a new level this sprint. She wrote a fuzzer for the HSL parser that generated 10,000 edge-case inputs overnight, and it caught a rounding error at exactly `hsl(0, 0%, 100%)` that would have produced `rgb(254, 254, 254)` instead of pure white. Rusti was impressed enough to not be annoyed, which I am recording for posterity.

Her review of the fuzzy matching in US-0106 was the most thorough of the sprint — she tested every CSS color name with one character deleted, one character swapped, and one character duplicated. The Levenshtein implementation held up. She said "I tried to break it. It held. For now." I believe this is the highest praise she is capable of offering.

The description review (US-0108) was faster than expected. Checker approved the deterministic descriptions on the first pass, noting only that the description for `MediumSlateBlue` was "trying too hard." Palette revised it without argument, which surprised everyone present.

**Worked on:** Reviews of US-0103, US-0106, US-0107, US-0108
**Surprised by:** The fuzzer catching a rounding error that manual testing would have missed for months
**Wary of next time:** Palette's output formatting code has no adversarial test coverage yet. She intends to fix that.
