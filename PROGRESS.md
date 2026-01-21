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
