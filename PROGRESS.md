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
