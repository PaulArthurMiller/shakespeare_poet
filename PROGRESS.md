# PROGRESS.md

> Add a new entry after **every commit**.
> Timezone: America/New_York.
> Format: ISO-like `YYYY-MM-DD HH:MM` (24h).
> Entries are additive; never rewrite prior history.

## 2026-01-14 00:00 — Project initialized
- Added initial planning documents:
  - AGENT.md
  - ARCHITECTURE.md
  - PROGRESS.md
- Next steps:
  - Create repo skeleton per ARCHITECTURE.md file tree
  - Add pyproject.toml and settings/logging scaffolding
  - Implement typed contracts in `common/types.py`
  - Add minimal FastAPI health endpoint
- Risks/notes:
  - Keep deterministic core modules pure and testable
  - Centralize prompts and enforce versioning early


## 2026-01-14 19:41 — Milestone 0 scaffold + health endpoint
- Added project scaffolding with FastAPI entrypoint, settings, and logging config.
- Added basic API health test and README run instructions.
- Added base packaging metadata and dependencies for development.
- Next steps:
  - Implement shared typed contracts in `common/types.py` with signature helpers.
  - Add deterministic unit tests for signature stability.
  - Begin expander planning scaffolding once contracts exist.
- Risks/notes:
  - Dependency install is required before running tests (`pip install -e .`).

## 2026-01-15 16:53 — Milestone 1 contracts + signatures
- Added shared typed contracts for planning, guidance, and scoring.
- Added deterministic signature helpers and domain error classes.
- Added unit tests to confirm signature stability.
- Next steps:
  - Implement expander planning artifacts and anchor planner for Milestone 2.
  - Add validators and demo planning script.
- Risks/notes:
  - Signature payloads may need expansion as state shape evolves.

## 2026-01-15 18:06 — Milestone 2 expander + anchor planner
- Implemented expander planning pipeline with anchor planning and validations.
- Added markdown brief renderer, prompt placeholders, and demo plan script.
- Added expander unit test coverage for anchors and beat obligations.
- Next steps:
  - Implement corpus ingestion and chunking for Milestone 3.
  - Add deterministic tests for line IDs and provenance.
- Risks/notes:
  - Anchor selection is heuristic and will evolve once LLM planning is integrated.

## 2026-01-15 18:07 — Fix UTC timestamps in contracts
- Updated plan/brief timestamps to use timezone-aware UTC datetimes.
- Next steps:
  - Proceed to Milestone 3 ingestion and chunking.
- Risks/notes:
  - None.

## 2026-01-15 19:05 — Milestone 3 ingestion + line chunking
- Added ingestion pipeline to normalize raw text and build canonical line indices.
- Added line chunker and corpus store with processed JSONL outputs.
- Added build_corpus script and tests for stable IDs and provenance.
- Next steps:
  - Implement Tier-1 feature extraction and stub vectorstore for Milestone 4.
  - Add tests for feature derivation and stub embeddings.
- Risks/notes:
  - Header parsing is heuristic and may need refinement for full corpus imports.

## 2026-01-16 08:15 — Milestone 4 Tier-1 features + vectorstore
- Added Tier-1 feature extraction for tokens, punctuation, syllables, and rhyme tails.
- Added deterministic stub embeddings and Chroma build/query utilities.
- Added build_index script and tests for features and vectorstore queries.
- Next steps:
  - Implement macro guidance components for Milestone 5.
  - Add unit tests for guidance output and anchor obligations.
- Risks/notes:
  - Metadata serialization is lossy for nested fields; revisit once schema stabilizes.

## 2026-01-18 08:01 — ChromaStore lifecycle fix for Windows cleanup
- Added explicit ChromaStore wrapper and close() to release handles after tests.
- Updated vectorstore helpers to use explicit store lifecycle.
- Added cleanup steps in vectorstore tests to avoid Windows file locks.
- Next steps:
  - Continue Milestone 5 macro guidance implementation.
- Risks/notes:
  - Pytest should be run with the same Python used for dependency installs.

## 2026-01-18 08:02 — Fix JSON import in vectorstore build
- Restored JSON parsing import for chunk loading in vectorstore build utility.
- Next steps:
  - Continue Milestone 5 macro guidance implementation.
- Risks/notes:
  - None.

## 2026-01-18 10:43 — Add Windows-safe vectorstore cleanup retry
- Updated vectorstore test teardown to retry temp directory cleanup after closing Chroma.
- Next steps:
  - Continue Milestone 5 macro guidance implementation.
- Risks/notes:
  - None.

## 2026-01-20 22:07 — Milestone 5 macro guidance
- Added macro graph, state manager, and guidance emitter for beat-level runtime guidance.
- Added macro unit tests covering beat ordering, guarded transitions, and anchor-aware guidance.
- Next steps:
  - Implement constraint enforcement and transition engine for Milestone 6.
  - Add reuse lock and anchor constraint logic with tests.
- Risks/notes:
  - Guidance priors are heuristic placeholders and will need tuning with scoring.

## 2026-01-20 22:43 — Milestone 6 constraints + transition engine
- Added reuse lock, grammar/anchor constraints, and deterministic transition engine for candidate enumeration.
- Added unit tests covering reuse pruning, anchor enforcement, and candidate enumeration.
- Next steps:
  - Implement scoring and beam search for Milestone 7.
  - Add checkpoint and rollback support in search.
- Risks/notes:
  - Anchor constraint is lexical and will need semantic matching later.

## 2026-01-20 18:14 — Milestone 7 scoring + beam search
- Added scoring feature extraction and scoring engine with anchor/length heuristics.
- Implemented beam search with checkpoints, rollback, and avoid-memory penalties.
- Added unit tests covering scoring preference for anchors and beam no-reuse behavior.
- Next steps:
  - Implement LLM critic and chooser toggle for Milestone 8.
  - Integrate critic into checkpoint loop.
- Risks/notes:
  - Scoring heuristics are minimal placeholders; will need tuning with real data.

## 2026-01-21 10:37 — Milestone 7 demo search script
- Added a demo script to generate a short beam-search sequence without reuse.
- Next steps:
  - Implement LLM critic and chooser toggle for Milestone 8.
  - Integrate critic into checkpoint loop.
- Risks/notes:
  - Demo corpus is minimal; expand once richer constraints are available.

## 2026-01-21 11:09 — Milestone 8 LLM critic + chooser
- Added LLM client abstraction, critic, and chooser modules with versioned prompts.
- Integrated critic reporting and chooser reordering into beam search checkpoints.
- Added unit tests for critic parsing, chooser behavior, and critic integration.
- Next steps:
  - Wire LLM critic/chooser into generation orchestration and API flows.
  - Implement Milestone 9 FastAPI endpoints for plan approval and generation.
- Risks/notes:
  - LLM responses are stubbed; real providers will require stricter validation and rate limits.

## 2026-01-21 12:07 — Milestone 9 API wiring
- Added API request/response models, in-memory plan/job stores, and service layer to orchestrate plan approval and generation.
- Wired FastAPI endpoints for plan creation, approval, generation, status, and export with logging and configuration hooks.
- Added end-to-end API integration test with corpus build step and console logging.
- Next steps:
  - Expand generation orchestration to include critic/chooser toggles and richer status updates.
  - Add persistent storage for plans and generation outputs.
- Risks/notes:
  - Anchor enforcement is relaxed when the corpus lacks required anchors; revisit with richer corpus coverage.

## 2026-01-21 13:53 — Milestone 10 docs + replay suite
- Expanded README with corpus/index build steps, demo plan/generation flow, replay suite, and next steps.
- Added learning replay suite skeleton for regression-style checks.
- Next steps:
  - Expand ingestion to the full Shakespeare corpus with richer metadata.
  - Implement meter/rhyme constraints and Tier-3 lazy features.
  - Add macro-graph learning from replay outcomes and persistent storage for plans/jobs.
  - Build a lightweight UI for plan review and playback.
- Risks/notes:
  - Branch context: `git status -sb` -> `## milestone-10-docs-replay`; `git branch --show-current` -> `milestone-10-docs-replay`.

## 2026-01-21 16:45 — Phrase/fragment chunkers + smart tokenization
- Added phrase chunker (`phrase_chunker.py`) for punctuation-based semantic phrase extraction with minimum 3-word constraint; complete short Shakespeare lines preserved as valid quotes.
- Added fragment chunker (`fragment_chunker.py`) using spaCy NLP for 3-8 word semantic puzzle pieces; identifies noun phrases, verb phrases, prepositional phrases, and clauses; prioritizes smaller units over complete lines for play construction flexibility.
- Enhanced provenance tracking with word index ranges (`start_word_idx`, `end_word_idx`), validation utilities, and human-readable reference formatting for quote map and validation systems.
- Fixed critical tokenization bug: Unicode curly quotes now normalized to straight apostrophes; smart tokenization keeps contractions (`return'd`, `we'll`), possessives (`Neptune's`), archaic forms (`'tis`, `'twas`, `o'er`), and hyphenated words (`good-night`) as single tokens.
- Added spaCy dependency to pyproject.toml.
- Next steps:
  - Integrate phrase/fragment chunks into vectorstore build pipeline.
  - Add Tier-1 features for phrase and fragment chunks.
  - Implement quote map for tracking used words during play generation.
  - Consider rhythm/meter analysis for fragment selection during assembly.
- Risks/notes:
  - Fragment chunker requires spaCy model: `python -m spacy download en_core_web_sm`.
  - Some words may be "lost" in fragment chunking when they don't form valid 3-8 word semantic units; this is by design to prioritize quote quality over coverage.

## 2026-07-08 17:15 — Fix canonical indexer dropping/mislabeling non-numbered headers
- Debugged a report of sonnet-adjacent lines being skipped ("Skipping line before headers are set"); traced the actual cause to `SCENE PROLOGUE` (Chorus speeches), not the Sonnets — the Sonnets themselves parse with 0 skips.
- Fixed three related bugs in `src/shpoet/ingest/canon_index.py`:
  - `_SCENE_RE` didn't accept `PROLOGUE`, so 921 lines across 6 plays (Henry IV Pt.2, Henry V, Henry VIII, Pericles, Romeo and Juliet, Troilus and Cressida, Two Noble Kinsmen) were silently dropped.
  - `_ACT_RE` had no trailing `\b`, so `ACT INDUCTION` (Taming of the Shrew) partially matched as `ACT I`, colliding line_ids with the real Act 1.
  - `_PLAY_HEADER_RE` didn't allow `;`, so `TWELFTH NIGHT; OR, WHAT YOU WILL` was never detected as a play header — its ~2,234 lines were silently mislabeled as whatever play preceded it (Troilus and Cressida), causing 955 duplicate line_ids.
- Added `INDUCTION`/`PROLOGUE` as sentinel act/scene value 0 (they always precede the numbered acts/scenes, so 0 can never collide).
- Added 3 regression tests in `tests/test_chunking.py`. Full corpus re-verified: 0 skipped lines (was 921), 0 duplicate line_ids (was 955).
- Next steps:
  - Re-run `build_corpus` / `build_index` against the full corpus so `data/processed` and the vectorstore pick up the corrected line_ids and previously-dropped lines.
- Risks/notes:
  - Branch: `claude-fix-prologue-induction-header-parsing`. Anyone with cached corpus/vectorstore artifacts built before this fix should rebuild them — old line_ids for Twelfth Night and Taming of the Shrew's Induction are no longer valid.

## 2026-07-08 — Per-batch checkpointing for the embedding loop
- The embedding step in `build_index` had no resume support: `ChromaStore.build_index` computed embeddings for an entire chunk file in one call, and an interruption (crash, network failure, killed process) mid-run meant re-embedding — and re-paying the OpenAI/Voyage API for — the whole file on retry.
- Added `src/shpoet/vectorstore/embedding_cache.py` (`EmbeddingCache`): a disk-backed cache keyed by `chunk_id` + a content hash of the chunk text, stored as `.embed_cache_<collection>.jsonl` next to each Chroma collection, with a `.meta.json` fingerprint (provider/model/dimensions) that invalidates the whole cache if the embedding config changes.
- Added `embed_texts_with_checkpointing()` in `embeddings.py`, which batches by the active embedder's `batch_size` (500 for OpenAI, 128 for Voyage) and writes each completed batch to the cache immediately — a rerun skips any chunk whose id+text hash is already cached and only computes the remainder.
- Wired `ChromaStore.build_index` to use the new checkpointed path instead of the old one-shot `embed_texts`.
- Added `tests/test_embedding_checkpointing.py` covering cache round-trip, invalidation on config change, invalidation on changed source text, and an end-to-end resume-after-simulated-crash scenario.
- Next steps:
  - Re-run `build_index` against the full corpus (per the prior entry's note) — this rebuild is exactly the kind of large, real-API run the checkpointing was added for.
- Risks/notes:
  - Discovered while testing: `tests/test_vectorstore.py` (and any test that instantiates `ChromaStore` without forcing `SHPOET_EMBEDDING_PROVIDER=stub`) will use the real OpenAI embedder and hit the network, since `.env` has `SHPOET_EMBEDDING_PROVIDER=openai` and a real `OPENAI_API_KEY` set. Pre-existing behavior, not introduced by this change.
  - Branch: `claude-embedding-checkpointing`.

## 2026-07-08 — Autouse fixture to force stub embedder in tests
- Added `tests/conftest.py` with an autouse `_force_stub_embedder` fixture: sets `SHPOET_EMBEDDING_PROVIDER=stub` and resets the settings/embedder caches before and after every test, so `pytest` never depends on network access or the real `OPENAI_API_KEY` in `.env`. Tests that need real-provider logic can still override the env var themselves within the test.
- Fixed a latent bug this surfaced: `reset_settings()` in `src/shpoet/config/settings.py` assumed `get_settings` was always the `lru_cache`-wrapped function. `tests/test_embedding_checkpointing.py` monkeypatches `get_settings` to a plain lambda for two tests, and the new fixture's teardown call to `reset_settings()` then hit `AttributeError: 'function' object has no attribute 'cache_clear'`. `reset_settings()` now guards with `hasattr(get_settings, "cache_clear")` before clearing.
- Verified: full suite (109 tests) passes with no `SHPOET_EMBEDDING_PROVIDER` override set in the shell — the fixture alone keeps it from touching the real API.
- Risks/notes:
  - Branch: `claude-embedding-checkpointing` (same PR as the embedding checkpointing work).

## 2026-07-16 17:02 EDT — Frontend workbench
- Added a FastAPI-served frontend with separate setup, composer/viewer, and admin pages for the Shakespearean cento workflow.
- Added generation library, persistent line review marks, and editable admin configuration endpoints backed by SQLite.
- Added API coverage for frontend support endpoints and validated import/health behavior.
- Next steps:
  - Replace synchronous generation with a streaming/background composition job so lines can arrive live in the viewer.
  - Add richer plan review editing before approval and export affordances in the composer.
  - Add browser-based visual regression tests once a browser runtime is available in the environment.
- Risks/notes:
  - Existing full API flow tests still require the `en_core_web_sm` spaCy model for fragment chunking; this environment does not have that model installed.
  - The composer currently loads completed generation records and marks lines persistently; true live scrolling will need an async generation endpoint or SSE feed.

## 2026-07-30 14:10 — State-of-play audit before first quality runs
Reconstructed actual project state after a gap in the log (no entries between
2026-07-08 and the 07-16 frontend commit, while the full-corpus embedding run
finished 07-19 and the Tier-2 feature work landed unlogged in `c459e2d`).
Recording findings here so the next session does not have to re-derive them.

**Confirmed done:**
- Full corpus is chunked and embedded. Chroma holds three complete collections,
  verified against `data/processed/*.jsonl` with exact parity:
  `shpoet_lines` 112,065 / `shpoet_phrases` 147,924 / `shpoet_fragments` 187,099
  = 447,088 embeddings, OpenAI `text-embedding-3-large` @ 3072 dims, ~7.5 GB.
  The `.embed_cache_*.jsonl` checkpoint files are complete for all three.
- Test suite green: 109 passing before this branch.
- Artistic-constraint *machinery* exists and is substantive: `features/meter.py`,
  `features/phonetics.py` (CMUdict rhyme classes + `data/archaic_pronunciations.json`),
  `features/syllables.py`, `features/semantics.py`, `micro/constraints/meter.py`,
  `micro/constraints/rhyme.py`. Tier-2 metadata (`stress_pattern`, `rhyme_class`,
  `iambic_score`, `emotion_valence`) is attached at index time in
  `vectorstore/chroma_store.py:98`.

**Confirmed NOT done — blockers for meaningful quality runs:**
1. *Generation never touches the vectorstore.* `generate_play` reads
   `CorpusStore.list_chunks()` → `data/processed/line_chunks.jsonl`. Nothing
   outside `scripts/build_index.py` and tests imports `shpoet.vectorstore`.
   Consequences: the 447k embeddings are unused at generation time; only the
   112k line chunks feed generation (phrase + fragment chunks never load); and
   there is no semantic narrowing — `TransitionEngine.enumerate_candidates`
   linearly scans all ~112k chunks per beam per depth, rebuilding a fresh
   `TransitionEngine` each time (`search/beam_search.py:72,141-146`).
2. *The artistic metadata is not on the generation path at all.* The processed
   JSONL files carry only `text`/`tokens`/`play`/`act`/`scene`/`word_index` —
   no `stress_pattern`, `rhyme_class`, `syllable_count`, or `emotion_valence`.
   Those exist only inside Chroma. So `MeterConstraint.evaluate` finds an empty
   pattern and returns `(True, "ok")` (`micro/constraints/meter.py:55-57`), and
   `build_scoring_features` defaults every Tier-2 field to `0.0`.
3. *No artistic knob is switched on.* `GuidanceEmitter.guidance_for_beat()`
   emits only `required_anchor_count`/`desired_anchor_count` and
   `anchor_presence`/`primary_anchor_weight` (`macro/guidance.py:55-66`). But
   `TransitionEngine` gates meter on `constraints["meter_strictness"]`
   (`transition_engine.py:56-58`) and `ScoringEngine` reads
   `priors["meter_preference"]` / `priors["emotion_alignment"]`
   (`scoring_engine.py:48-49`) — none of which are ever emitted. Every artistic
   term is multiplied by zero. Effective score today is
   `anchor_hits − |token_count − 10| × 0.1`.
4. *`RhymeConstraint` has never executed.* Constructed in `TransitionEngine.__init__`
   and exposed via `get_rhyme_constraint()`, which nothing calls.
5. *`features/tier3_lazy.py` is dead code.* 260 lines of spaCy dependency trees /
   NER / noun phrases, imported by nothing, not re-exported in
   `features/__init__.py`, no tests.
6. *The frontend does not serve.* `.gitignore` ended with a blanket `*.html`
   (intended for coverage reports; `htmlcov/` already covers those), which
   silently excluded `index.html`, `composer.html`, and `admin.html` from commit
   `d331ff6`. The JS and CSS were committed; the three pages were not, and are
   not present on any machine checked. `GET /` `/composer` `/admin` all return
   500; `/health` and `/static/app.js` return 200. The new tests only exercise
   the JSON support endpoints, so CI stayed green and the gap went unnoticed.
   Removed the blanket `*.html` rule on this branch so the pages can be
   committed once recovered or regenerated.
7. *Admin config knobs are partly inert.* `AdminConfig` persists `model`,
   `temperature`, and `anchor_pressure`, and `static/app.js` posts the whole
   record as the `/generate` config — but `GenerationConfig` declares only
   `beam_width`, `max_length`, `checkpoint_interval`, `use_critic`,
   `use_chooser`, so Pydantic drops the other three silently.

**Assessment:** not ready for quality runs. Generation would be slow *and* every
signal being evaluated is structurally zero. Existing artifacts in `data/output/`
are 227-byte, 3-line toy-corpus smoke tests from 07-08, predating the full corpus.

- Next steps (in order):
  - Retrieval step: per-beat candidate pool queried from Chroma, returning
    top-N chunks *with Tier-2 metadata attached*, fed to `BeamSearch` in place of
    the whole corpus. Prerequisite for everything else — fixes speed, brings
    phrase/fragment chunks into play, and supplies the metadata the constraints
    need. Started on branch `claude-vectorstore-retrieval`.
  - Wire `macro/guidance.py` to emit `meter_strictness`, `meter_preference`,
    `length_preference`, `emotion_alignment`/`target_valence` per beat.
  - Call `RhymeConstraint` from the transition/scoring path, or delete the getter.
  - Recover/regenerate the three missing HTML pages and commit them; add a
    smoke test asserting `GET /`, `/composer`, `/admin` return 200.
  - Widen `GenerationConfig` to carry `anchor_pressure` (and decide whether
    `model`/`temperature` should reach the critic/chooser).
  - Then run quality passes and playbacks.
- Risks/notes:
  - Branch: `claude-vectorstore-retrieval`, cut from `main` @ `c943dfc`.

## 2026-07-30 14:30 — Per-beat candidate retrieval from the vector index
Closes blocker #1 from the audit above: generation now draws its candidates
from Chroma instead of walking the whole processed corpus.

- Added `src/shpoet/micro/candidate_pool.py` (`CandidatePool`). For each beat it
  builds a semantic query from the beat's objective + rhetorical mode + anchor
  vocabulary (`build_beat_query`), queries all three collections, merges and
  dedupes by `chunk_id`, drops ids already consumed elsewhere in the play, and
  returns a deterministically ordered pool sorted by `(distance, chunk_id)`.
- Added `rehydrate_chunk`, which rebuilds search-ready chunk dicts from Chroma
  result rows. `text` comes back from the stored document and `tokens` is
  re-derived (token lists are not scalars, so Chroma drops them from metadata);
  JSON-encoded fields (`punctuation`, `phonemes`, `pos_tags`) are decoded.
  **This is what makes the artistic constraints possible at all** — Tier-1 and
  Tier-2 features are computed at index time and exist nowhere else, so the old
  JSONL path could never have fed them to scoring.
- Exposed `tokenize()` publicly in `features/tier1_raw.py` so rehydration derives
  tokens exactly the way indexing did, rather than diverging on its own split.
- Added `ChromaStore.embedding_dimension()` and `ChromaStore.count()`.
- Wired `CandidatePool` through `api/services.generate_play` (new optional
  `candidate_pool` arg) and `api/main.create_app`. Retrieval is the default path;
  the full-corpus walk remains as an explicit fallback and now logs a warning
  explaining that Tier-2 metadata is unavailable on that path.
- Added `SHPOET_CHROMA_DIR` and `SHPOET_RETRIEVAL_POOL_SIZE` settings
  (pool size 0 disables retrieval).

**Bug found and fixed while testing:** an embedding-dimension mismatch failed
silently in the worst possible way. Querying the 3072-dim index with an 8-dim
stub vector raised inside Chroma once per collection per beat; each beat caught
it, logged, fell back to an empty pool, and the job completed "successfully"
with an empty play. `CandidatePool._verify_dimensions()` now checks stored vs.
configured dimensions at construction and raises with the exact setting to fix.
`_build_candidate_pool()` in `api/main.py` catches that and degrades to the full
corpus rather than failing app startup on a fresh clone with no index.

**Test isolation fixed:** `tests/conftest.py` now also redirects
`SHPOET_CHROMA_DIR` and `SHPOET_OUTPUT_DIR` to a per-test temp directory. The
API flow test had been writing generated plays into the real `data/output`, and
once the app opened a pool at startup it would otherwise have queried the real
447k-chunk production index. `tests/test_api.py::test_plan_approve_generate_flow`
now builds a real index over the fixture corpus so the flow exercises retrieval
end to end.

- Verified against the real full-corpus index (`data/chroma`, 447,088 chunks,
  OpenAI text-embedding-3-large @ 3072):
  - Opening all three collections: ~5.0s, one time at app startup.
  - Per-beat query: ~1.2–2.5s, 800 candidates selected from 1,596 retrieved.
  - Retrieval is on-target. Query "A ruler confronts a mirror that remembers
    every broken oath / soliloquy / crown mirror oath" returned "As doth a ruler
    with unlawful oaths" (1H6 5.5), "Is crowned so soon and broke his solemn
    oath" (3H6 1.4), "Against my crown my oath my dignity" (Err. 1.1), "But now
    two mirrors of his princely semblance" (R3 2.2).
  - Tier-2 metadata arrives intact: e.g. `syllable_count=10 iambic_score=0.9
    stress_pattern=1101010101 rhyme_class=OW_DH_Z`.
- Full suite green: 126 tests (109 prior + 16 new retrieval tests + 1 rewritten).
- Next steps:
  - Wire `macro/guidance.py` to emit `meter_strictness`, `meter_preference`,
    `length_preference`, `emotion_alignment`/`target_valence`. Now unblocked —
    the metadata these read is finally present on the chunks.
  - Dedupe near-identical candidates across collections. The pool currently
    returns e.g. `..._line101` and `..._line101_p0` — the same words differing
    only by trailing punctuation. Worse, the reuse lock keys on `chunk_id`, so
    nothing stops the search from emitting both. Needs normalized-text dedupe in
    the pool and probably a source-span check in `ReuseLock`.
  - Tune `pool_size` (currently 800) once the artistic knobs are live; it trades
    candidate diversity against per-beat search cost.
  - Call `RhymeConstraint` from the transition/scoring path, or delete the getter.
  - Recover/regenerate the three missing HTML pages; add a smoke test asserting
    `GET /`, `/composer`, `/admin` return 200.
- Risks/notes:
  - Measured signal quality in the index before relying on it: `iambic_score` is
    well spread (0.5/0.6/0.333/0.667/0.7 all heavily populated), so the meter
    knob has real signal to work with. **`emotion_valence` is degenerate** —
    396,370 of 447,088 chunks (89%) are exactly 0.0, with the remainder almost
    entirely ±1.0. The keyword lexicon in `features/semantics.py` is too coarse
    to be worth weighting; turning on `emotion_alignment` will do close to
    nothing until that extractor is improved. Do not read a null result from the
    emotion knob as "emotion doesn't help".
  - Retrieval quality is only as good as the beat objective text the expander
    writes; thin or generic objectives will retrieve generic material.

## 2026-07-30 15:05 — BUILD-PLAN.md for the remaining work
- Added `BUILD-PLAN.md`: architecture-as-built diagrams, the metadata-boundary
  explanation, per-beat data flow, and seven milestones with acceptance criteria,
  risks, and open questions. The original `INSTRUCTION.md` milestones 0–10 are
  complete; this plan covers the gap between "every module exists" and "the
  modules are connected and produce measurable quality".
- Milestone order and the reasoning behind it:
  - **M1 Turn on the artistic knobs** — `macro/guidance.py` is the single
    junction box gating meter/length/emotion. Smallest change, largest effect,
    fully unblocked by the retrieval work. Knobs go in settings, not hardcoded,
    so the knobs-off control group stays reproducible for the M3 A/B.
  - **M2 Quote integrity** — `ReuseLock` keys on `chunk_id`, but overlapping
    chunks from one source line have different ids, so the play can reuse the
    same words and still pass. This violates the project's defining rule, and it
    has to be fixed before any quality measurement is trustworthy.
  - **M3 Real evaluation harness** — build the ruler before measuring. Note that
    `learning/replay_suite.py` is worse than absent: `run_scenario()` always
    returns `passed=True`, so a green suite currently means nothing. Replaced,
    not extended.
  - **M4 First quality runs and tuning** — the milestone that answers the actual
    question. Also forces the `RhymeConstraint` decision: wire it or delete it.
  - **M5 Restore the frontend** — independent of M1–M4; required before
    "playbacks" are possible. The JS files are the spec for the missing HTML.
  - **M6 Long-run ergonomics** — background job + incremental status. Deliberately
    after M4, which is what tells us how long a real run takes.
  - **M7 Deferred** — semantics valence fix, Tier-3 decision, `learning/updater.py`.
- Next steps:
  - Merge PR #23 (`claude-vectorstore-retrieval`); M1 builds on it.
  - Start M1: extend `GuidanceEmitter.guidance_for_beat()` to emit
    `meter_strictness`, `meter_preference`, `length_preference`,
    `emotion_alignment`, `target_valence`, with defaults in `config/settings.py`.
- Risks/notes:
  - Branch: `claude-build-plan`, stacked on `claude-vectorstore-retrieval` so the
    PROGRESS.md history stays linear. Merge #23 first.
  - Recurring failure mode named explicitly in the plan's conventions: this
    codebase fails *silently*. A missing metadata key becomes a `0.0` default, a
    dimension mismatch becomes an empty pool, a placeholder returns `passed=True`.
    Every wiring change should land with a test that fails if the wire is cut again.

## 2026-07-30 15:40 — M1: artistic constraint knobs wired and switched on
Completes BUILD-PLAN.md Milestone 1. `macro/guidance.py` now emits every knob its
consumers read, so the meter machinery is live for the first time.

- Added `GuidanceKnobs` (frozen dataclass) in `macro/guidance.py` with
  `from_settings()` and `all_off()`. Held as an explicit value object rather than
  read from global config inside the emitter, so guidance stays a pure function of
  its inputs and tests can vary knobs without touching the environment.
  `all_off()` is the reproducible control group for M3's A/B.
- `GuidanceEmitter.guidance_for_beat()` now emits `constraints["meter_strictness"]`
  and `priors["meter_preference" | "length_preference" | "emotion_alignment" |
  "target_valence"]`, alongside the existing per-beat anchor priors. Knob values
  are logged per beat.
- Added five settings fields (`SHPOET_METER_STRICTNESS`, `SHPOET_METER_PREFERENCE`,
  `SHPOET_LENGTH_PREFERENCE`, `SHPOET_EMOTION_ALIGNMENT`, `SHPOET_TARGET_VALENCE`).
- Added `tests/test_guidance_knobs.py` (18 tests) covering the full chain: knob
  emitted → constraint prunes → score moves. Includes a control-group test proving
  `all_off()` reproduces the old all-zero artistic scoring.

**Bug found and fixed: the meter strictness parameter was inverted.**
`check_meter_adjacency` computed `acceptable = score >= (1.0 - strictness)`, so
strictness 0.0 rejected everything but a perfect transition and 1.0 accepted
everything — exactly backwards from its own docstring and from `MeterConstraint`'s.
No test pinned the direction: `test_strictness_levels` asserted nothing about
acceptance and carried the comment "Implementation-dependent behavior". Had this
shipped, turning the knob "down to be gentle" would have pruned the pool hardest.
Now `acceptable = score >= strictness`, with monotonicity and direction tests.

**The knob has three regimes, not a smooth range.** `_normalize_stress` emits a
binary alphabet, so the branches in `check_meter_adjacency` are exhaustive and
adjacency scores take only {1.0, 0.9, 0.3} — the `else: score = 0.5` branch is
unreachable (kept as a documented defensive fallback). Measured against the real
800-chunk retrieved pool, averaged over five different preceding chunks:

| meter_strictness | survivors | pruned on meter |
|---|---|---|
| 0.0 (off)        | 797 (99.7%) | 0   |
| 0.4 – 0.9        | 291 (36.3%) | 507 |
| 1.0              | 174 (21.8%) | 623 |

Default set to **0.4**, not the 0.3 originally planned: with the inversion fixed,
0.3 is the minimum reachable score and would prune nothing, making the constraint
inert — the exact failure mode M1 exists to end. 0.4 is the mildest setting that
does anything, and ~290 candidates per beat is ample for beam search.

- `emotion_alignment` ships at **0.0 (off)**, deliberately. With `target_valence`
  at 0.0 the scoring term pays `(1.0 - |0.0 - valence|) * weight`, so every neutral
  line scores full marks and every emotionally marked line scores zero — given 89%
  of the corpus is exactly 0.0, enabling it would actively reward blandness. Wired
  for completeness; leave off until `features/semantics.py` is fixed (M7).
- Full suite green: 145 tests.
- Next steps:
  - M2 (quote integrity): `ReuseLock` keys on `chunk_id`, so overlapping chunks
    from one source line can both be used. Fix before any quality measurement.
- Risks/notes:
  - Branch: `claude-guidance-knobs`, cut from `main` @ `6ac6c82`.
  - **Per-beat knob modulation was deliberately not built.** BUILD-PLAN M1
    suggested letting `rhetorical_mode` modulate the knobs, but
    `expander/expander.py:33` hardcodes `rhetorical_mode = "reflection"` for every
    beat, and `_build_scene_plan` emits exactly one beat per scene. A modulation
    table would be branches that can never execute — the same dead-code trap the
    plan warns about. Revisit when the expander produces varied modes; that is
    also a real limit on M4's tuning surface and probably deserves its own
    milestone.

## 2026-07-31 09:20 — M2: quote integrity enforced on source spans
Completes BUILD-PLAN.md Milestone 2. The no-reuse rule — the project's defining
constraint — was never actually enforced; it is now, at four layers.

**The bug.** `ReuseLock` keyed on `chunk_id`. Three chunkers cut overlapping text
out of the same corpus, so one Shakespeare line yields a full-line chunk, phrase
chunks, and fragment chunks, all with different ids and all made of the same
words. `..._line101`, `..._line101_p0` and `..._line101_f2` are three identities
for one piece of text. Locking on id therefore permitted exactly the thing it
existed to prevent, and every prior run "passed" a rule nothing was checking.

- Added `common/spans.py`: `SourceSpan` (`line_id` + inclusive word range — the
  triple every chunker already writes via `chunking/provenance.py`) and
  `span_from_chunk()`, which returns `None` rather than guessing when provenance
  is absent. Callers must treat `None` as *unverifiable*, never as *safe*.
- `ReuseLock` now marks and tests chunk **dicts**. Marking any chunk locks every
  overlapping span on that source line. Ids are kept as the cheap first check and
  as the only identity available for provenance-less chunks, which are counted
  separately (`unverifiable_count`) so degraded locking is visible.
- `CandidatePool.for_beat()` takes the play-level lock in place of `exclude_ids`
  and dedupes on normalized text (tokenized with the indexer's own tokenizer, so
  the rule cannot drift from how `tokens` was derived at index time).
- `api/services.generate_play` holds **one lock for the whole play**. The old
  per-beat `used_ids` set was the cross-beat leak: beat 5 could re-quote words
  beat 1 had spent, under a different chunk id.
- Added `validation/quote_integrity.py`: an independent post-generation check on
  the finished artifact, reporting violations, quotes checked, **and quotes that
  could not be checked**. Stored on `GenerationRecord` (new `quote_integrity`
  column, with an explicit `ALTER TABLE` migration — `CREATE TABLE IF NOT EXISTS`
  does nothing to a pre-existing database) and embedded in the exported play JSON.

**Adjacency is not overlap.** `0–3` and `4–7` on one line quote different words
and both stay legal. Getting this wrong would have deleted most of the usable
phrase corpus for a rule that never asked for it, so it is pinned by test.

**Measured against the real 447k index** (query: "A ruler confronts a mirror that
remembers every broken oath", pool_size 800):

| | |
|---|---|
| retrieved across 3 collections | 1,596 |
| duplicate texts collapsed | **392 (24.6%)** |
| final pool | 800, all with usable spans (0 unverifiable) |
| distinct source lines represented | 628 |
| pool members overlapping an earlier member | 171 |
| candidates excluded after 30 chunks consumed | 72 (≈2.4 per chunk spent) |

Two things worth keeping: a quarter of the retrieval budget was being spent on
chunks that were the same words as another chunk in the pool, and provenance
survives the full chunk → index → query → rehydrate round trip intact, which is
what makes the span rule enforceable at runtime at all. The 171 overlapping
members are *alternatives* — legal to hold in the pool, and it is the lock's job,
not the pool's, to ensure only one is ever selected.

**Corpus-exhaustion risk (BUILD-PLAN M2) measured, and it is mild.** Span locking
costs ~2.4 candidates per chunk consumed, against 1.0 for id locking. At 800
candidates per beat that is not close to starving the pool; revisit only if
rollback counts climb in later acts during M4.

- **Open question resolved:** a sonnet line and a play line that happen to share
  text have different `line_id`s, so quoting both is **not** reuse. They are
  distinct places in the canon and the span rule is right to allow it. Pinned by
  `test_same_indices_on_different_lines_do_not_overlap`.
- Full suite green: 178 tests (145 prior + 33 new).
- Next steps:
  - M3 (real evaluation harness): `learning/replay_suite.py` still returns
    `passed=True` unconditionally. Quote-integrity violation counts are now a
    real metric it can assert on.
- Risks/notes:
  - Branch: `claude-quote-integrity`, cut from `main` @ `bebb33a`.
  - `ReuseLock.mark_used()` takes a chunk dict, not an id — an id alone cannot
    say which source words a line spent. `mark_id_used()` exists for callers that
    genuinely hold only ids (a persisted generation record), and every use of it
    increments `unverifiable_count`.
  - A play that fails integrity is **recorded and logged, not raised**. The play
    is still worth reading, and the violations name exactly which spans clash.
    M3's harness should treat a non-zero violation count as a hard failure.
  - Validating a previously-exported play in `data/output/` needs its stored
    chunk ids resolved back to chunks first; `check_quote_integrity()` accepts
    the resulting usages, but no resolver is written yet.

## 2026-07-31 16:40 — M3: a real evaluation harness
Completes BUILD-PLAN.md Milestone 3. `learning/replay_suite.py` no longer lies,
and there is now a ruler to measure M1 and M2 against.

**What was wrong.** `run_scenario()` logged a warning and returned
`passed=True` unconditionally. A green suite was evidence of nothing while
looking exactly like a suite that checked something — the most expensive kind
of wrong, because it consumes the attention a real check would have earned.
Replaced, not extended.

- Added `learning/metrics.py`: anchor coverage (per beat, per act), quote
  integrity, meter conformity, line length against the pentameter target,
  source diversity, and search health, assembled into a `Scorecard`.
- Added `learning/play_run.py`: normalizes a live run and an exported play into
  one shape, so a metric never has to know which it was handed.
- Added `learning/eval_store.py`: scorecards persist to `data/eval/` named
  `<scenario>-<arm>.<signature>.json`, where the signature hashes the run's
  *inputs* (config + knobs). The same experiment overwrites itself; a different
  configuration gets its own file. Timestamping instead would fill the directory
  with runs nobody could tell apart.
- Added `scripts/score_play.py` — scores a play already sitting in
  `data/output/`, which is what the resolver below was for.
- `BeamSearch` now reports `dead_ends`, `rollbacks`, `depth_reached` and
  `exhausted`; `services` folds those into a `BeatSearchStats` per beat and onto
  the exported play as `search_health`. None of it is recoverable from the verse.
- `generate_play_from_plan` is public and takes explicit `knobs`, which is what
  makes the A/B possible — `GuidanceKnobs.all_off()` is the pre-M1 control arm.

**Closed the resolver gap M2 left.** `validation/chunk_resolver.py` turns an
exported play's stored chunk ids back into chunks, with two backends whose
difference is the metadata boundary itself:

| | JSONL backend | Chroma backend |
|---|---|---|
| availability | always | needs a built index |
| provenance (spans) | yes | yes |
| Tier-2 (`iambic_score`, `syllable_count`) | **no** | yes |
| cost | one streaming pass | key lookup, embeds nothing |

Verified on a real 07-08 artifact in `data/output/`: JSONL gave `PASS, 3 quotes
checked` with meter reported as *3 unmeasured*; Chroma gave the same integrity
result plus `0.53 mean iambic_score, 10.67 syllables`. Same play, same verdict,
different amount of it measurable — which is exactly the distinction the
scorecard is built to keep visible.

**The rule that makes the suite worth running: unmeasured is not zero.** Every
metric that reads chunk metadata reports how many quotes it could measure and
returns `None`, not `0.0`, when that count is zero. A threshold whose metric came
back unmeasured is a **failure**, not a pass. That single rule is what would have
caught the original placeholder, and it is what catches a silently-empty pool or
a Tier-2 field that stops arriving. Every default scenario sets
`require_measured_meter`, pinned by a test that fails if a scenario is ever added
without it.

**First A/B, run against the real 447k index** (`--ab --no-critic`, 8 lines):

| metric | knobs-off (control) | knobs-on |
|---|---|---|
| mean `iambic_score` | 0.73 | **0.79** |
| desired anchor coverage | 25% | **50%** |
| distinct source plays | 8 | 7 |
| lines within ±2 of pentameter | 100% | 88% |

**This is not a result.** Eight lines from one scenario is far too small a
sample, and the diversity and length columns moved the wrong way. It is evidence
that the ruler reads and that the two arms are genuinely different runs. Getting
an answer out of it is M4's job, with more scenarios and more lines.

- Full suite green: **237 tests** (178 prior + 59 new).
- Next steps:
  - M4 (first quality runs and tuning) — but see the blocker below first.
  - Consider promoting "unmeasured is not zero" to REVIEW-NOTES.md; it is now the
    third time this codebase has produced a silent-default bug.

- Risks/notes:
  - Branch: `claude-eval-harness`, cut from `main` @ `db6ef62`.
  - **BLOCKER FOR M4: an act with more than one scene cannot be planned at all.**
    `plan_anchors` attaches an obligation to the first beat of each *act*, while
    `validate_play_plan` requires *every* beat to carry one, so
    `expand_play_input` raises `PlanInvalidError: Beat act1_scene2_beat1 missing
    anchor obligations`. Confirmed by probe: 1 act × 1 scene passes, 2 acts × 1
    scene each passes, **any act with 2 scenes fails**. Every existing test used
    a single scene, so this has never surfaced. M4 wants a full five-act play and
    will hit it immediately.
    Note the validator disagrees with its own docstring:
    `_ensure_non_empty_beats` is documented as "every scene includes *at least
    one* beat with obligations" but implemented as "every beat must have one".
    Fixing it needs a decision that belongs to the expander, not to M3 — should
    later beats in an act re-require the primary anchor (which interacts with the
    reuse lock), or should the validator match its docstring? M3's scenarios work
    around it with 2 acts × 1 scene rather than pre-empting that call.
  - `emotion_valence` remains degenerate (89% zeros) and `emotion_alignment` stays
    at 0.0, so the scorecard deliberately has no emotion metric. Adding one would
    report a number with no signal behind it. Revisit with M7.
  - The critic is **off by default** in the suite (`--critic` to enable): every
    checkpoint is a paid Anthropic call, and the suite is meant to be run often.
  - `data/chroma`, `data/processed`, `data/output` and `data/eval` are now
    gitignored. They were untracked but not ignored — one `git add -A` away from
    committing 7.5 GB.
  - Scenario variety is limited by the expander, not by the harness:
    `expander.py:33` hardcodes `rhetorical_mode = "reflection"` and emits one beat
    per scene, so the two default scenarios differ mainly in anchor vocabulary.
    Same root cause as the M1 note about per-beat knob modulation.

