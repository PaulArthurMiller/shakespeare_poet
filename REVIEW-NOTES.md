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

## build session — 2026-07-31 (M3, evaluation harness)

**Problem:** The replay suite's `run_scenario()` returned `passed=True`
unconditionally with a logged warning. It had done so since Milestone 10 in
January. Nothing was broken, no test failed, and the suite had been run and
reported green — which is worse than having no suite, because a green check
consumes the attention a real check would have earned.

**Root cause:** A placeholder written with a truthful log line
(`"uses placeholder checks"`) but an untruthful *return value*. Logs are read
by whoever is watching at the time; return values are read by everything
downstream, forever. The two diverged and the return value won.

**Pattern — this codebase fails by returning a plausible default.** Four
instances now, all the same shape:
- missing metadata key → `float(chunk.get("iambic_score", 0.0))` → 0.0
- embedding dimension mismatch → exception per collection → empty pool → a
  play generated with no candidates, job status `completed`
- absent provenance → chunk not span-locked → reuse rule silently weakened
- placeholder check → `passed=True`

In every case the default is *in range*. 0.0 is a legal iambic score, an empty
pool is a legal pool, `True` is a legal verdict. Nothing downstream can tell
the default from a measurement, which is what makes these survive so long.

**Prevention — make "unmeasured" a distinct value from "zero", and make it
propagate.** M3's metrics never return `0.0` for something they did not
measure; they return `None` and carry a `measured`/`unmeasured` count beside
every average. The rule that gives this teeth is at the threshold layer: *a
threshold whose metric came back unmeasured is a failure, not a pass.* An
assertion that could not be evaluated has not been satisfied. Without that
second half, `None` just becomes the new silent default.

The same idea, applied at the layer below, is what the M2 work called
`unverifiable_count`: quotes whose provenance is absent are neither passes nor
failures, they are unchecked, and the count says how much of the verdict is
real.

**Trigger:** Any `.get(key, <default>)` where the default is a legal value of
the field, any `except: return <success>`, and any function whose docstring
says "placeholder". Ask: if this key vanished from the data tomorrow, what
would the caller see — an error, or a number?

**Corollary found the same session:** `chromadb.PersistentClient(path=...)`
plus `get_or_create_collection` *creates* a directory and empty collections
rather than failing on a path that holds no index. Opening a typo'd path
therefore succeeded and produced a resolver that found nothing, reporting every
quote in the play as unverifiable. Guarding constructors that create-on-open is
the same class of fix: refuse the empty case explicitly, because the library's
"helpful" default is indistinguishable from success.

## build session — 2026-07-31 (M4, planning blocker)

**Problem:** Any act with more than one scene raised `PlanInvalidError`
outright — not a wrong output, a hard crash before generation started.
Undetected since Milestone 2 (January) because every scenario, in every test
and every replay suite entry, happened to use exactly one scene per act.

**Root cause:** `expander/validators.py::_ensure_non_empty_beats` was
implemented as "every beat in the scene must carry an obligation," while its
own docstring said "every scene includes *at least one* beat with
obligations." `anchor_planner.plan_anchors` was written to the docstring's
looser rule (it only ever placed an obligation on one beat *per act*), so the
two disagreed the moment an act held a second scene: the second scene's beat
had no obligation, and the stricter implementation rejected it.

**Pattern — this is the second time in this codebase a docstring and its
implementation have quietly diverged, and both times the docstring was
right and the code was wrong.** M1's `meter_strictness` inversion
(`check_meter_adjacency` computed the opposite of what its own docstring and
`MeterConstraint`'s described) is the first instance. In both cases: the
docstring reads as a spec someone wrote deliberately; the code reads as
plausible at a glance; and no test pinned which one was true, so the mismatch
shipped and stayed shipped until an input shape exercised it.

**Prevention:** When a docstring makes a specific, checkable claim ("every
X has at least one Y", "score increases as strictness decreases"), write one
test that would fail if the *code* were right and the *docstring* were wrong,
and one that would fail the other way. That test is what forces a human to
notice the disagreement instead of silently picking a side. Absence of such a
test is itself a signal worth searching for: grep docstrings for quantifiers
("every", "at least", "all", "none") and check each one has a test that
distinguishes it from its plausible-sounding neighbor.

**Trigger:** Reviewing or modifying any function whose docstring states a
structural invariant in words ("every scene", "at least one", "must not
exceed") — before trusting the implementation, write the input that would
tell the two apart.
