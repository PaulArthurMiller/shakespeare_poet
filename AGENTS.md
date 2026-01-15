# AGENT.md

# Global Development Standards for Paul A. Miller

These instructions apply to all projects unless specifically overridden in project documentation.

## Development Environment
- **Platform**: Windows with PowerShell
- **Experience Level**: Intermediate developer, still learning - explain complex patterns
- **Code Presentation**: Show complete functions/methods when suggesting changes, not snippets

## Core Principles

### Modularity First
- Design with clear module boundaries based on functionality or architectural layers
- Minimize coupling between modules
- Keep related code together, separate unrelated code
- When uncertain about module organization, ask before proceeding

### Clarity Over Cleverness
- Prioritize readable code over compact code
- Add comments explaining *why*, not just *what*
- Use descriptive names for variables, functions, and classes
- If a pattern seems too complex, discuss simpler alternatives

### Defensive Coding
- Include type hints/annotations (TypeScript types, Python type hints)
- Validate inputs at module boundaries
- Handle errors explicitly - no silent failures
- Think about edge cases during implementation

## Code Organization

### Functions and Methods
- **Comment every function** with purpose and key relationships
- Keep functions focused on single responsibilities
- Limit complexity - if a function does too many things, break it up
- Helper/utility functions should be clearly marked and scoped appropriately

### Classes (for OOP languages like Python)
- Use classes for related state and behavior
- Include class-level docstrings explaining purpose
- Group methods logically (initialization, public interface, private helpers)
- Consider whether a class is needed vs. simple functions

### File Structure
- Group related code in the same file/module
- Separate concerns across files (UI, business logic, data access)
- Use clear naming conventions for files matching their contents

## Logging and Debugging

### Logging Philosophy
**Log generously** - when in doubt, add a log line
- INFO: Key workflow events, successful operations
- DEBUG: Detailed state information, intermediate values
- WARNING: Recoverable issues, deprecated usage
- ERROR: Failures requiring attention

### For Multi-Module Projects
- Implement a consistent logging system
- Identify log source (module/class name)
- Include relevant context (IDs, parameters, state)

## Error Handling
- **Never fail silently** - log all errors
- Provide actionable error messages
- Use try/catch (or try/except) at appropriate boundaries
- Consider retry logic for external dependencies
- Clean up resources in finally blocks

## Testing Approach
- Write tests for public interfaces
- Test edge cases and error conditions
- Keep tests simple and focused
- Run tests before considering work complete

## Type Safety

### Type Tracking
- Always use type hints/annotations
- Follow argument types through the call chain
- Verify object shapes match between caller and callee
- Comment complex type shapes or transformations

### Common Type Issues to Watch
- Returning None when value expected
- Mixing dictionaries/objects with different structures
- List/array element type mismatches
- Async/Promise handling

## Documentation
- README for project setup and usage
- Architecture decisions in ARCHITECTURE.md
- API contracts for module interfaces
- Inline comments for complex logic

## Streaming Implementations - General Guidelines

When implementing any streaming functionality:

### Always Include Comprehensive Logging During Development
```python
# Backend: Log every chunk generated
print(f"🔵 STREAM CHUNK {n}: '{chunk[:50]}...' (len={len(chunk)})")

# Frontend: Log every chunk received
console.log('🟢 RECEIVED CHUNK:', data, 'length:', data.length);
```

### Remove or gate behind debug flag before production

### Test Edge Cases
- Empty messages
- Very long messages (>1000 chars)
- Messages with special characters (\n, \r, \t, unicode)
- Messages with formatting (markdown, HTML)
- Rapid successive messages
- Network interruptions mid-stream

### Phase Completion Reviews
At the end of each development phase, conduct a comprehensive code 
quality review before proceeding:

**Review Areas:**
1. Implementation verification (features exist AND work correctly)
2. Error handling completeness
3. Code quality (type hints, documentation, modularity)
4. Testing coverage for critical paths
5. Performance and security considerations

**Review Format:**
- What's properly implemented ✅
- What exists but isn't being used ⚠️
- What needs improvement 🔧
- Any potential issues 🚩

## Windows/PowerShell Specific
- Use forward slashes or pathlib for cross-platform paths
- Be mindful of case sensitivity differences
- Test commands work in PowerShell when providing examples
- Use PowerShell-compatible syntax for shell commands

## Communication Preferences
- Explain technical concepts at intermediate level
- Show complete functions/methods in code suggestions
- Provide context for changes - the "why" behind the "what"
- Link related concepts to help build mental models
- Don't be afraid to suggest better approaches if I'm headed down a wrong path

## Common Issues

### Server-Sent Events (SSE) Streaming

When implementing SSE streaming (commonly used for AI responses):

#### Critical: SSE Message Boundary Issues
- **Problem**: SSE uses `\n\n` (double newline) as message delimiter
- **Issue**: If streamed content contains `\n\n`, the browser's SSE parser 
  treats it as the end of message, causing data loss
- **Common in**: AI responses with paragraphs, numbered lists, code blocks
- **Symptoms**: Missing text, broken formatting, dropped list markers

#### Solution: JSON-Encode SSE Data
**Always JSON-encode the data field:**
```python
# ❌ WRONG - Raw text with \n\n breaks parsing
yield f"data: {text}\n\n"

# ✅ CORRECT - JSON-encoded text escapes \n\n
yield f"data: {json.dumps({'text': text})}\n\n"
```

**Frontend must parse JSON:**
```javascript
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);  // Parse the JSON
  const text = data.text;                // Extract text
  // ... use text
};
```

#### Testing SSE Implementations
When implementing or debugging SSE:
1. Test with content containing `\n\n` (paragraphs, lists)
2. Add debug logging for raw chunks (both backend and frontend)
3. Verify chunk counts match on both ends
4. Check browser Network tab → EventStream for raw SSE data


## Project: Shakespearean Poet (Quote-Assembled 5-Act Plays)

Build an application that generates a complete 5-act play **entirely from Shakespeare source quotes** (plays + sonnets), with strict constraints:

- Output language is always Shakespearean (direct Shakespeare text).
- Every spoken line in the generated play is assembled from Shakespeare quotes:
  - **No shorter than 3 sequential words**
  - **No longer than a single original Shakespeare line**
  - **No quote fragment reused anywhere in the generated play**
- The system is **not a translator** from modern text. It is a **language-first poet**:
  - The design phase should focus on *emotional/rhetorical/metaphorical intent*
  - The execution phase assembles quotes via constrained search, guided by state and anchors
- Use a **hybrid engine**:
  - Deterministic constraint-based traversal for most selections
  - LLM used primarily for planning + critique + occasional “wild card chooser”
- The system must support **narrative continuity** via explicit **Anchors** (objects/entities/motifs/phrases), planned by an Expander and enforced during assembly.

This repo will contain:
- A FastAPI runtime service for orchestration and API exposure
- An offline build pipeline for chunking + metadata + embeddings (ChromaDB)
- The “Play Plan” workflow: user input → Expander artifacts → user approval → generation

## Read these docs first
- `ARCHITECTURE.md` — required design blueprint and module responsibilities
- `PROGRESS.md` — must be updated after every commit (additive log)

## High-level process to build
1. **Bootstrapping**
   - Create .gitignore, project skeleton, config, logging, typed data models, and test harness.
2. **Data + Index Pipeline (offline)**
   - Utilize cleaned Shakespeare sample text found at "data/raw/shakespeare_sample.txt" for development
   - Raw text includes play titles, act numbers, and scene numbers for reference metadata
   - Chunk into: lines (primary), phrases/fragments (secondary) with provenance (reference, including line number for spoken lines only)
   - Compute Tier-1 raw features (cheap/stable), Tier-2 derived fields (moderate), support Tier-3 lazy fields
   - Build embeddings and store in ChromaDB with rich metadata
3. **Planning Layer**
   - Implement the **Expander**: produces a Play Design Brief from user inputs (emotional/rhetorical plans, act/scene/beat outlines, and Anchor Registry + recurrence strategy).
   - Implement an approval loop: user can accept or request changes (regenerate design artifacts, not quotes).
4. **Generation Layer**
   - Implement MacroGraph + StateManager + GuidanceProfile generation for each beat
   - Implement MicroGraph/TransitionEngine (constraint enumeration)
   - Implement SearchController (beam search + checkpoints + rollback + negative memory)
   - Implement Critic (LLM judge) and toggleable Chooser (LLM selector)
5. **Evaluation + Learning**
   - Add deterministic validators and regression tests
   - Add caches and signature-based logging
   - Add simple Learner updates (winner/loser deltas; avoid-list; knob adjustments)
6. **API and CLI**
   - FastAPI endpoints for: plan generation, plan approval, play generation, status, exporting outputs
   - Minimal CLI for offline pipeline tasks (build index, rebuild metadata, run evaluation suite)

## Key architectural concepts (must implement)
### Conceptual layers
- **Planning (Expander)**: converts minimal user input into structured, Shakespeare-compatible *expressive* design targets + anchors + recurrence strategy.
- **Macro Layer (MacroGraph + StateManager)**: holds low-cardinality canonical state and produces GuidanceProfiles (priors + knobs).
- **Micro Layer (Corpus + Transition Engine)**: quote universe, metadata, legality constraints, transition enumeration.
- **Search & Assembly (SearchController)**: beam search over constrained transitions with checkpoints and rollback.
- **LLM Supervision (Critic & optional Chooser)**: judge windows and suggest knob changes; optionally choose among candidates in hard cases.
- **Learning (Learner/Updater)**: persists improvements across sessions by nudging weights, storing avoid signatures, and refining priors.

### Anchors (narrative continuity)
Expander must:
1) Identify likely anchors from the play overview and scenes.
2) Choose a central Shakespeare-parallel anchor term + small related word set.
3) Create a recurrence strategy (rules, frequency, distribution across acts/scenes/beats).
4) Place anchor obligations into beat plans.

Anchors are enforced as:
- **Hard**: a minimum number of anchor hits per act/scene segment (configurable)
- **Soft**: scoring priors that reward anchor/motif coverage and penalize starvation
- Avoid making anchors purely literal; enforce function and lexical/semantic families.

## Agent instructions (do these every time)
- Keep code modular and testable. Pure deterministic components must be unit-tested.
- Prefer typed dataclasses / pydantic models for all cross-module contracts.
- Add structured logging and signatures for every decision step.
- Do not bake long prompt text everywhere. Keep prompts centralized and versioned.
- Avoid large refactors that rewrite multiple modules at once; incremental commits.
- **Update `PROGRESS.md` after each commit**:
  - timestamp (America/New_York)
  - summary of changes
  - next steps
  - risks/notes

## Non-goals (for now)
- No full frontend build. Only FastAPI endpoints + minimal CLI utilities.
- No production auth/roles yet (stub cleanly).
- No distributed queue unless required; keep architecture ready for it.

