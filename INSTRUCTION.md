# INSTRUCTION.md — Autonomous Build Cycle for Shakespearean Poet (Vibe-Coded)

You are an autonomous coding agent building this repository end-to-end.

## Read first (required)
1) `AGENT.md` — project goals, constraints, and workflow rules  
2) `ARCHITECTURE.md` — module responsibilities + file tree + design details  
3) `PROGRESS.md` — additive changelog; MUST update after each commit

You must follow the architecture and constraints exactly. If something is unclear, make a best effort, document assumptions, and continue.

---

## Operating Mode: Build → Test → Fix → Test (Repeat)

### Golden rule
**Never move to the next milestone until the current milestone's acceptance tests pass.**

### Your cycle for every task
1) **Plan**: briefly identify what you will implement in the current milestone.
2) **Implement**: add or modify code.
3) **Test**: run the repo test suite (or the milestone subset).
4) **Fix**: resolve failures; repeat Test → Fix until green.
5) **Document**: update docs and `PROGRESS.md` (additive, timestamped).
6) **Commit**: commit with a descriptive message.
7) Move to the next milestone.

If you cannot execute tests in your environment:
- Still implement the milestone.
- Provide **exact commands** for Paul to run locally.
- Ask Paul to paste the test output logs back.
- Do not proceed beyond the milestone until passing status is confirmed via logs.

### Branch discipline (required):
Before starting each milestone, update your working copy of main and create a new branch from it.
Run git status and git branch --show-current and include the output in your milestone notes.
Branch name must be milestone-<N>-<short-name>.
Do not commit to an existing milestone branch.
If you cannot create a new branch for any reason, stop and report the exact git error output.

---

## Definition of Done (Project-Level)
The project is considered “complete enough” when:
- A FastAPI service runs and exposes endpoints for:
  - generating a plan (`POST /plan`)
  - approving a plan (`POST /plan/{id}/approve`)
  - generating a play (`POST /generate`)
  - checking status (`GET /generate/{job_id}`)
  - exporting output (`GET /export/{job_id}`)
  - health check (`GET /health`)
- The pipeline produces:
  - a user-readable Play Design Brief (markdown)
  - a machine-readable PlayPlan (JSON)
- The generator produces a play draft from the plan using:
  - deterministic traversal for most choices
  - windowed critic evaluation
  - optional chooser toggle
  - strict no-reuse constraints
- A minimal test suite exists and passes:
  - unit tests for chunk/feature/constraints/search skeleton
  - integration test for plan→approve→generate on a tiny corpus sample
- Logging is structured and includes decision traces and signatures.
- Docs include “how to run,” “how to rebuild index,” and “next steps.”

This is a demonstration build. Prefer minimal viable implementations that match the architecture and can be iterated later.

---

## Milestones (Do in order)

### Milestone 0 — Repo scaffold + tooling (must be done first)
**Goal:** create a runnable python project with tests and FastAPI skeleton.

**Tasks:**
- Create file tree from `ARCHITECTURE.md`.
- Add `pyproject.toml` with dependencies:
  - fastapi, uvicorn
  - pydantic
  - pytest
  - chromadb
  - python-dotenv (optional)
  - httpx (for API tests)
- Add `src/shpoet/config/settings.py` and logging config.
- Add `src/shpoet/api/main.py` with `GET /health`.
- Add `tests/test_api.py` for `/health`.
- Add `README.md` with basic run instructions.

**Acceptance:**
- `pytest` passes.
- `uvicorn shpoet.api.main:app --reload` runs.
- `/health` returns OK.

---

### Milestone 1 — Shared typed contracts + signatures + errors
**Goal:** stable cross-module data contracts.

**Tasks:**
- Implement `common/types.py`:
  - `UserPlayInput`
  - `CharacterInput`
  - `SceneInput`
  - `PlayDesignBrief`
  - `PlayPlan` (acts/scenes/beats)
  - `AnchorRegistry`, `AnchorPlan`, `BeatObligation`
  - `GuidanceProfile`, `StateBundle`
  - `CandidateScore`, `CriticReport`
- Implement `common/signatures.py`:
  - `StateSignature`, `TailSignature`, `FailureSignature`
- Implement `common/errors.py`.

**Acceptance:**
- mypy is optional; but type hints must be consistent.
- unit tests verifying signatures stable for same input.
- `pytest` passes.

---

### Milestone 2 — Expander (planning) + anchor planner + validation
**Goal:** convert user input into a plan + anchors + brief.

**Tasks:**
- Implement `expander/expander.py`:
  - takes `UserPlayInput`
  - returns `PlayDesignBrief` (markdown) and `PlayPlan` (JSON)
  - keep prompts centralized (`llm/prompts/*`)
- Implement `expander/anchor_planner.py` per ARCHITECTURE:
  - detect likely anchors
  - choose parallel term + related words
  - define recurrence strategy (soft obligations + a few explicit placements)
  - populate beat obligations
- Implement `expander/validators.py`:
  - required fields present
  - anchor plan non-empty
  - beats contain obligations

**Acceptance:**
- unit tests for expander output shape (no LLM required if mocked).
- Provide a `scripts/demo_plan.py` that runs on a sample input to produce artifacts.

---

### Milestone 3 — Corpus ingestion + chunking skeleton (tiny demo corpus allowed)
**Goal:** build minimal corpus representation with stable IDs.

**Tasks:**
- Implement `ingest/` + `chunking/` minimally:
  - accept a small plaintext corpus file (demo)
  - create stable `line_id` for each line
  - create line chunks
  - optionally phrase/fragments later; for demo, line chunks are enough
- Implement `micro/corpus_store.py` to retrieve chunks and metadata.

**Acceptance:**
- unit tests: stable IDs, provenance.
- demo build script writes `data/processed/` artifacts.

---

### Milestone 4 — Feature pipeline (Tier-1) + Chroma index build/query
**Goal:** store enough metadata to support constraints + scoring.

**Tasks:**
- Implement Tier-1 features:
  - tokenization, punctuation profile, first/last tokens
  - left/right context window (if available)
  - syllable estimate heuristic
  - rhyme tail heuristic
- Implement `vectorstore/build_index.py` and `vectorstore/query.py`:
  - embed and store in Chroma
  - allow retrieval by semantic query + metadata filters (minimal)
- For embeddings:
  - if no API keys, stub with deterministic fake vectors for tests.

**Acceptance:**
- tests pass with stub embeddings.
- a demo script builds Chroma DB and can query top results.

---

### Milestone 5 — MacroGraph + StateManager + GuidanceProfile
**Goal:** turn PlayPlan into runtime guidance.

**Tasks:**
- Implement `macro/state_manager.py` with guarded state transitions.
- Implement `macro/macro_graph.py` as simple adjacency / tables (not necessarily Neo4j).
- Implement `macro/guidance.py`:
  - emits priors + knobs per beat including anchor targets.

**Acceptance:**
- unit tests: guidance emitted for a beat, anchor obligations reflected.

---

### Milestone 6 — Constraints + TransitionEngine (minimal, deterministic)
**Goal:** enumerate allowed next chunks.

**Tasks:**
- Implement `micro/reuse_lock.py` (global no reuse).
- Implement minimal constraints:
  - `constraints/grammar.py` (simple adjacency sanity)
  - `constraints/anchor.py` (track anchor coverage/starvation)
  - meter/rhyme constraints can be placeholder for now with strict hooks
- Implement `micro/transition_engine.py`:
  - returns candidate ids + pruning reasons.

**Acceptance:**
- unit tests: reuse enforcement + deterministic candidate enumeration.

---

### Milestone 7 — ScoringEngine + SearchController (beam + checkpoints)
**Goal:** generate sequences by constrained search.

**Tasks:**
- Implement `scoring/scoring_engine.py` with breakdown output.
- Implement beam search:
  - `search/beam_search.py`
  - `search/checkpoint.py`
  - `search/rollback.py`
  - `search/avoid_memory.py`
- Must support:
  - B beam width
  - checkpoint every K lines
  - rollback + avoid penalties

**Acceptance:**
- unit tests for beam behavior on toy corpus.
- generate a short “speech” sequence without reuse.

---

### Milestone 8 — LLM Critic + optional Chooser (toggle)
**Goal:** supervise generation windows.

**Tasks:**
- Implement `llm/client.py` adapter (OpenAI/Anthropic stub ok).
- Implement `llm/critic.py` (structured JSON output; mocked in tests).
- Implement `llm/chooser.py` (toggle: off by default).
- Integrate critic into checkpoint loop.

**Acceptance:**
- tests using mocks for critic/chooser.
- logs include critic reports.

---

### Milestone 9 — FastAPI endpoints (plan → approve → generate → export)
**Goal:** wire the system through the API.

**Tasks:**
- `POST /plan`: return plan_id + brief + plan JSON
- `POST /plan/{id}/approve`: lock and optionally regenerate
- `POST /generate`: start generation job
- `GET /generate/{job_id}`: status + partial output
- `GET /export/{job_id}`: markdown/json exports

**Acceptance:**
- integration test: plan→approve→generate returns output for toy corpus.

---

### Milestone 10 — Docs + replay suite + future steps
**Goal:** close out demonstration.

**Tasks:**
- README: run server, build index, run demo plan and generate.
- `learning/replay_suite.py` skeleton to run fixed scenarios.
- Add “Next Steps” section:
  - expand real Shakespeare corpus ingestion
  - richer constraints (meter/rhyme)
  - Tier-3 lazy features
  - macro edge learning
  - UI build (later)

**Acceptance:**
- docs are accurate and runnable.
- tests remain green.

---

## Commit discipline
- One milestone may involve multiple commits.
- Each commit must:
  - keep tests passing (or include note if awaiting logs)
  - update `PROGRESS.md` with timestamp and next steps

---

## Style + engineering rules
- Use consistent naming and typed models for cross-module boundaries.
- Deterministic modules must have unit tests and no LLM calls.
- LLM prompts must be versioned in `src/shpoet/llm/prompts/`.
- Avoid overbuilding: produce minimal implementations that preserve future extensibility.

