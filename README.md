# Shakespearean Poet

A FastAPI service for generating a Shakespeare-quote-assembled five-act play. This repository follows the architecture described in `ARCHITECTURE.md`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run the API

```bash
uvicorn shpoet.api.main:app --reload
```

Visit `http://localhost:8000/health` to confirm the service is healthy.

## Run tests

```bash
pytest
```
