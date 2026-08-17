# DevCrew

A multi-agent system where four LLM agents — Planner, Coder, Tester, and
Reviewer — collaborate to turn a natural-language coding request into
tested, working Python code, with a self-correcting revision loop instead
of one-shot generation.

## Status

Day 1 of a 6-day build. Currently implemented: shared state schema and a
Planner -> Coder chain. Tester, Reviewer, the cyclic revision loop, API
layer, and deployment land over the following days.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in GROQ_API_KEY (free at console.groq.com/keys)
```

## Running tests

```bash
pytest
```

## CI

GitHub Actions runs lint (`ruff`) and the test suite on every push and PR
to `main`. The build and deploy stages get added once Docker (Day 4) and
the eval set exist.

Full architecture, eval results, and usage docs will be added as the
system is completed.
