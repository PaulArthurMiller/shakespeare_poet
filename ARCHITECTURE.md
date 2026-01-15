# ARCHITECTURE.md

## 1) Conceptual overview

### Goal
Generate a complete 5-act play composed entirely of Shakespeare quotes (3+ sequential words, up to one Shakespeare line), with zero reuse, strong character voice, beat-driven flow, and narrative continuity via Anchors.

### Core design principle
**Language-first, narrative-emergent**:
- We do not translate modern narrative into Shakespeare.
- We design **expressive targets** (tone/intent/rhetoric/motif) and assemble Shakespearean quotes that realize those targets through constrained search.

---

## 2) Layered architecture

### 2.1 Planning Layer (Design phase)
**Input**: user provides play overview, characters+voices, and scene-by-scene descriptions (setting, participants, situation).  
**Process**: Expander generates a “Play Design Brief” and structured artifacts.  
**Output**: approved plan artifacts used by the generator.

Key planning artifacts:
- Five-act structure (expressive: tension arc, revelations, reversals)
- Scene list mapped into acts
- Beat plan per scene (expressive objectives, rhetorical posture)
- Character dossiers (voice traits, diction biases, rhetorical habits)
- Relationship trajectories (coarse states and evolution points)
- **Anchor Registry** + recurrence strategy + beat obligations

User interaction:
- Present a plain-language brief
- User approves or requests changes (regenerate plan artifacts)

### 2.2 Macro Layer (Runtime state & guidance)
- **StateManager**: canonical state pointers (speaker, present chars, current beat, act role).
- **MacroGraph**: nodes/edges for acts, scenes, beats, relationships, rhetorical moves, anchors.
- **GuidanceProfile**: produced per beat; supplies priors and constraint knobs to Micro + Search.

Outputs to runtime:
- constraint knobs: grammar strictness, meter strictness, anchor pressure, lookahead pressure
- scoring priors: rhetorical move preferences, relationship modifiers, anchor/motif targets

### 2.3 Micro Layer (Quote universe + legality)
- **CorpusStore**: chunks + provenance + raw features + derived metadata
- **ChromaDB**: embeddings index for semantic proposals and optional anchor/motif semantic matching
- **TransitionEngine**: deterministic enumeration of “allowed next chunks” based on:
  - reuse locks
  - grammar/compatibility constraints
  - meter feasibility constraints
  - rhyme scheme constraints (if enabled for a passage)
  - adjacency constraints from raw line context features

### 2.4 Search & Assembly Layer
- **SearchController**: beam search across candidate paths with checkpoints and rollback.
- **ScoringEngine**: fast scoring for candidates and partial paths (no LLM calls).
- **Critic (LLM)**: windowed structured evaluation at checkpoints (voice drift, beat progress, anchor coverage, coherence).
- **Chooser (LLM, optional)**: toggleable; used for “wild card” decisions under dead-ends/uncertainty.
- **Learner/Updater**: updates weights/priors/avoid signatures based on critic outcomes.

---

## 3) Module plan

### 3.1 Planning modules
- `expander/`: transforms minimal input into PlayPlan + AnchorPlan + CharacterSheets.
- `planner/`: optional micro-planners (act planner, scene planner, beat planner) used by Expander.

### 3.2 Data and indexing
- `ingest/`: corpus ingestion, normalization, canonical line indexing.
- `chunking/`: produces lines/phrases/fragments linked to source line context.
- `features/`: Tier-1 raw features + Tier-2 derived metadata + Tier-3 lazy features.
- `vectorstore/`: ChromaDB build & query wrappers.

### 3.3 Runtime generation
- `macro/`: StateManager, MacroGraph structures, GuidanceProfile.
- `micro/`: TransitionEngine, reuse locks, constraint evaluators.
- `search/`: beam search, checkpointing, rollback, avoid memory.
- `llm/`: prompts, critic, chooser, model adapters.
- `learning/`: weight updates, replay tests, drift analysis.

### 3.4 API layer
- `api/`: FastAPI app, routers, request/response models, background task stubs.

---

## 4) Project file tree

shakespearean_poet/
AGENT.md
ARCHITECTURE.md
PROGRESS.md
README.md

pyproject.toml
.env.example
.gitignore

src/
  shpoet/
    init.py

  config/
    settings.py
    logging.yaml

  common/
    types.py
    signatures.py
    errors.py
    utils.py

  ingest/
    source_loader.py
    normalize.py
    canon_index.py

  chunking/
    line_chunker.py
    phrase_chunker.py
    fragment_chunker.py
    provenance.py

  features/
    tier1_raw.py
    tier2_derived.py
    tier3_lazy.py
    phonetics.py
    syntax.py
    meter.py
    rhyme.py

  vectorstore/
    chroma_client.py
    embeddings.py
    build_index.py
    query.py

  expander/
    expander.py
    anchor_planner.py
    play_design_brief.py
    validators.py

  macro/
    state_manager.py
    macro_graph.py
    guidance.py

  micro/
    corpus_store.py
    reuse_lock.py
    constraints/
      grammar.py
      meter.py
      rhyme.py
      anchor.py

    transition_engine.py

  scoring/
    scoring_engine.py
    features_for_scoring.py

  search/
    beam_search.py
    checkpoint.py
    rollback.py
    avoid_memory.py

  llm/
    client.py
    prompts/
      expander_system.md
      expander_user.md
      critic_system.md
      critic_user.md
      chooser_system.md
      chooser_user.md
    critic.py
    chooser.py

  learning/
    updater.py
    replay_suite.py

  api/
    main.py
    routers/
      health.py
      plan.py
      generate.py
      export.py
    models/
      plan_models.py
      generate_models.py

  export/
    render_markdown.py
    render_json.py

  tests/
    test_chunking.py
    test_features.py
    test_transition_engine.py
    test_scoring.py
    test_search.py
    test_expander.py
    test_api.py

  scripts/
    build_corpus.py
    build_index.py
    rebuild_metadata.py
    run_replay_suite.py

  data/
    raw/
    processed/
    chroma/

logs/


---

## 5) Detailed module descriptions

### 5.1 `config/`
- `settings.py`: pydantic settings. Sources: env vars + `.env`. Include:
  - model names, API keys (not committed)
  - Chroma path
  - search defaults (beam width, checkpoint frequency)
  - critic cadence
  - strictness knobs (meter/rhyme/grammar)
- `logging.yaml`: structured logging with JSON format option, request IDs, correlation IDs.

### 5.2 `common/`
- `types.py`: shared typed dataclasses/pydantic models used across modules.
- `signatures.py`: stable hash signatures for caching and learning:
  - `StateSignature`
  - `TailSignature`
  - `FailureSignature`
- `errors.py`: domain exceptions (ConstraintViolation, DeadEnd, PlanInvalid, etc.)

### 5.3 Ingestion + chunking
#### `ingest/`
- Build canonical index of Shakespeare source lines:
  - parsing happens here
  - stable `line_id` for each original line
  - normalized text + original text
  - title, act number and scene number are included in the raw text
  - setting information often follows the scene number in the same line; it can be discarded when parsing
  - treat these headers as state updates; they are not to be included in chunks and do not receive line IDs
  - Canonincal index metadata includes: play, act number, scene number, line number, and word index
  - word index counts each word in the line, starting with "0"
  - this reference system is crucial for verification of quote identity and preventing repeat usage

#### `chunking/`
- Primary unit: **line chunks** (max output unit).
  - full line chunks should include all words in the word index (for example, a two word line would have as the index: "0,1")
- Secondary: **phrases/fragments**, always referencing:
  - `line_id`
  - start/end token offsets
  - left/right context windows from the source line
  - phrase and fragments should include the word index for the words they contain
    - for example, a line "To be or not to be, that is the question" with a phrase or fragment
      of "that is the question" has a word index of: "6,9"
  - Sample metadata for reference: (not actual data):
  {
  "line_id": "hamlet_act1_scene2_line173",
  "play": "Hamlet",
  "act": 1,
  "scene": 2,
  "line_in_scene": 173,
  "word_index": "0,8"
  "raw_text": "Seems, madam! nay it is; I know not 'seems.'"
  }
  - **phrases** are chunked based on punctuation
  - **fragments** are chunked based on semantic relationships, limited to 3-8 words

- `provenance.py`: ensures every chunk tracks source play/sonnet, act/scene/line/word index.

Special consideration:
- Chunk IDs must remain stable once generated (or versioned).

### 5.4 Feature pipeline
#### Tier-1 raw features (`features/tier1_raw.py`)
Compute for every chunk and store in DB/metadata:
- token counts, char counts
- punctuation profile
- first/last tokens
- left/right neighbor windows from source line
- basic POS tags (cheap)
- syllable estimates (heuristic + pronouncing fallback)
- rhyme tail approximation (phonetic or heuristic)
- “starts/ends on function word” flags
- clause boundary heuristics based on punctuation

#### Tier-2 derived (`features/tier2_derived.py`)
Moderate-cost, reusable:
- embeddings (semantic)
- coarse rhetorical labels
- coarse emotion bins
- topic clusters
- “voice/style” embeddings or tags (optional)

#### Tier-3 lazy (`features/tier3_lazy.py`)
Only computed for candidate pools when needed, then cached:
- fine meter scans
- deeper syntax role within line
- multi-line cohesion measures

### 5.5 `vectorstore/` (ChromaDB)
- Build index with embeddings and store metadata needed for filtering/scoring.
- Provide query interfaces:
  - propose starts
  - propose escape candidates
  - optional anchor semantic matching

### 5.6 `expander/` (Planning / Design artifacts)
#### Responsibilities
- Generate a **Play Design Brief** from user input:
  - Acts → Scenes → Beats (expressive, not literal)
  - Character sheets (voice traits, rhetorical habits)
  - Relationship arcs (coarse)
  - **Anchor Registry** + recurrence strategy + beat obligations
- Return:
  - user-friendly brief (markdown)
  - machine-friendly plan (JSON)

#### Anchor Planner (`anchor_planner.py`)
Implements:
1. Identify candidate anchors from user input.
2. Choose central Shakespeare-parallel term + related word set.
3. Create recurrence strategy rules:
   - minimum frequency per act/scene
   - distribution (early wonder → mid addiction → late doom)
   - which characters tend to invoke which anchors
4. Place beat obligations:
   - per beat: required/desired anchors/motifs

Anchor dictionary structure (example):
- `obj_anchor`: "orb"
- `parallel`: "orb"
- `related_words`: ["globe","sphere","world","star","eye","crown","circlet"]
- `recurrence_rules`: (human-readable + machine-readable)
- `placements`: list of beat IDs (soft obligations preferred; allow exact placements for a few “lexical identity” anchors)

Important: avoid over-literal scheduling. Use:
- required minimums
- suggested placements
- allow multiple ways to satisfy via lexical family or semantic proximity.

### 5.7 `macro/`
- `state_manager.py`:
  - canonical state pointers
  - guarded transitions at beat boundaries
- `macro_graph.py`:
  - node/edge representations for beats, acts, relationships, anchors
- `guidance.py`:
  - produces `GuidanceProfile` per beat:
    - constraint knobs (hard-ish)
    - scoring priors (soft)
    - anchor targets + starvation thresholds
    - lookahead targets

### 5.8 `micro/`
- `corpus_store.py`: chunk retrieval and metadata projection.
- `reuse_lock.py`: global “no reuse” enforcement.
- `constraints/`:
  - `grammar.py`: adjacency legality from raw features
  - `meter.py`: feasibility checks (Tier-1) + optional Tier-3 scans
  - `rhyme.py`: rhyme scheme constraints when enabled
  - `anchor.py`: lexical/semantic anchor matching and starvation enforcement
- `transition_engine.py`: enumerates allowed next chunks with explainable pruning.

### 5.9 `scoring/`
- `scoring_engine.py`: fast scoring; returns breakdown:
  - semantic fit to beat/target
  - voice fit (heuristic + tags)
  - relationship modifiers
  - anchor coverage / starvation
  - continuity heuristics
  - novelty moderation
- `features_for_scoring.py`: transforms raw metadata into scoring features.

### 5.10 `search/`
- `beam_search.py`: beam logic, diversity preservation, exploration mode.
- `checkpoint.py`: snapshots of path state.
- `rollback.py`: rollback mechanics.
- `avoid_memory.py`: negative memory to penalize known-bad continuations.

### 5.11 `llm/`
- `client.py`: model adapter (OpenAI/Anthropic) behind an interface.
- `critic.py`: structured judge called at windows/checkpoints.
- `chooser.py`: optional decision-maker toggled on for dead ends/high entropy.
- `prompts/`: versioned prompts (do not scatter prompts in code).

### 5.12 `learning/`
- `updater.py`:
  - simple stable updates:
    - winner/loser deltas on weights
    - penalties for avoid signatures
    - slow learning rates
- `replay_suite.py`:
  - fixed test plans to detect regressions and reward hacking.

### 5.13 `api/` (FastAPI)
Endpoints (initial):
- `POST /plan`: user input → Expander returns design brief + plan id
- `POST /plan/{id}/approve`: lock plan, optionally with edits → regenerate or accept
- `POST /generate`: generate play from approved plan → job id
- `GET /generate/{job_id}`: status + partial output
- `GET /export/{job_id}`: markdown/json export
- `GET /health`: health check

Implementation notes:
- Keep generation potentially long-running; provide background task stub or simple in-process for now.
- All requests include `request_id` for log correlation.

---

## 6) Logging and observability

### Requirements
- Structured logs (JSON option) with:
  - request_id, plan_id, job_id
  - state signatures, tail signatures
  - candidate counts, pruning reasons
  - critic reports and decisions
- Save full decision traces for debugging:
  - “why chosen” and “why pruned” breakdowns

---

## 7) Testing strategy

### Unit tests
- chunking correctness (stable IDs, provenance)
- feature computation sanity (syllable/rhyme tail)
- constraints validity (grammar/meter/rhyme)
- transition enumeration (reasons, determinism)
- scoring (breakdown consistency)
- beam search behavior (diversity, rollback)

### Integration tests
- Expander output validation (anchor registry present, beat plan consistent)
- End-to-end: plan → approve → generate (small corpus subset)

### Replay/regression suite
- fixed “mini plays” that must keep anchor coverage and avoid drift
- compare outputs structurally (not exact lines) + verify constraints

---

## 8) Security and safety (pragmatic)
- No secrets committed; `.env.example` only.
- Input validation for API payloads.
- Rate-limit LLM calls at runtime (config).
- Guard prompt injection in planning: treat user input as content; do not execute instructions from it.

---

## 9) Notes on strict Shakespeare output
- “Strict Shakespearean” means:
  - output consists of Shakespeare quotes only
  - assembly must preserve word order within each quoted fragment
  - max fragment length <= original line
- Meter/rhyme strictness is not a “user expectation slider.” It is an engineering knob. Keep it in config, not user-facing initially.

