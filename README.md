# Shakespearean Poet

A FastAPI service for generating a Shakespeare-quote-assembled five-act play. This repository follows the architecture described in `ARCHITECTURE.md`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Build the demo corpus

```bash
python -m shpoet.scripts.build_corpus
```

## Build the vector index

```bash
python -m shpoet.scripts.build_index
```

## Run the API

```bash
uvicorn shpoet.api.main:app --reload
```

Visit `http://localhost:8000/health` to confirm the service is healthy.

## Run the plan demo

```bash
python -m shpoet.scripts.demo_plan
```

## Generate a demo play via the API

1. Create a plan:

```bash
curl -X POST "http://localhost:8000/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "demo-plan",
    "user_input": {
      "title": "The Glass Crown",
      "overview": "A court fractures as an ambitious heir courts fate and power.",
      "characters": [
        {
          "name": "Valen",
          "description": "An heir torn between duty and desire.",
          "voice_traits": ["measured", "resolute"]
        }
      ],
      "scenes": [
        {
          "act": 1,
          "scene": 1,
          "setting": "A shadowed hall in the royal keep.",
          "summary": "Valen confides fears while whispers gather.",
          "participants": ["Valen"]
        }
      ]
    }
  }'
```

2. Approve the plan by replacing `<PLAN_ID>` with the `plan_id` from the response:

```bash
curl -X POST "http://localhost:8000/plan/<PLAN_ID>/approve" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "demo-approve",
    "approve": true,
    "regenerate": false
  }'
```

3. Generate the play by replacing `<PLAN_ID>`:

```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "demo-generate",
    "plan_id": "<PLAN_ID>",
    "config": {
      "beam_width": 3,
      "max_length": 3,
      "checkpoint_interval": 2
    }
  }'
```

4. Fetch status or export output by replacing `<JOB_ID>` from the generate response:

```bash
curl "http://localhost:8000/generate/<JOB_ID>"
curl "http://localhost:8000/export/<JOB_ID>"
```

## Run the replay suite

```bash
python -m shpoet.learning.replay_suite
```

## Run tests

```bash
pytest
```

## Next Steps

- Expand ingestion to the full Shakespeare corpus with richer metadata.
- Implement meter/rhyme constraints with Tier-3 scans.
- Add Tier-3 lazy features for semantic and stylistic enrichment.
- Learn macro-graph edges and guidance priors from replay outcomes.
- Build a lightweight UI for plan review and playback.
