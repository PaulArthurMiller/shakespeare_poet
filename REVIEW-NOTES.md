# REVIEW-NOTES.md

> Accumulated patterns from /review, /retro, and /debug sessions.
> Entries are additive; never rewrite prior history.

## debugger session — 2026-07-08

**Problem:** Sonnets were reported as "not being chunked in full" — log showed
lines being skipped with "Skipping line before headers are set" right before
a run ended.

**Root cause:** Not the Sonnets at all. The corpus's raw text uses a small
set of non-numbered structural labels that Shakespeare's plays genuinely
have — `SCENE PROLOGUE` (a Chorus speech before the numbered scenes of an
act), `ACT INDUCTION` (a framing act before Act I), and a play title
containing a semicolon (`TWELFTH NIGHT; OR, WHAT YOU WILL`). The header
regexes in `canon_index.py` only anticipated numbered/simple forms, so:
- `SCENE PROLOGUE` didn't match `_SCENE_RE` → `scene` stayed `None` → every
  line until the next real `SCENE` header was silently dropped.
- `ACT INDUCTION` partially matched `_ACT_RE` (no trailing `\b`) as `ACT I`
  → collided line_ids with the real Act 1.
- The semicolon in the Twelfth Night title wasn't in `_PLAY_HEADER_RE`'s
  character class → the header was never recognized → the whole play
  silently inherited the *previous* play's name → line_id collisions across
  ~2,234 lines.

**Pattern:** When a corpus/text pipeline has a completeness heuristic
(regex matching "what a header looks like"), test it against the *full*
corpus, not a representative sample — real historical text has edge-case
structural forms (inductions, prologues, epilogues, subtitled titles) that
a small fixture won't surface. A single skipped-line warning at the tail
of a log is easy to misattribute to whatever content is nearby (here: the
Sonnets, since that was the last thing fixed) rather than to the content
that's actually failing.

**Trigger:** Any time a "detect this kind of header/marker" regex is
tightened or extended for one corpus edge case — check whether the same
class of edge case (non-numbered labels, unusual punctuation) recurs
elsewhere in the corpus before considering the fix complete.

**Prevention:** After fixing a header-detection bug, re-run the *full*
build and assert two invariants, not just "no warnings for my specific
case": (1) zero "skipped before headers" warnings, and (2) zero duplicate
`line_id` values across the whole corpus. Both invariants caught bugs here
that a narrow regression test alone would have missed — the Twelfth
Night bug produces no warning at all, only a silent collision.
