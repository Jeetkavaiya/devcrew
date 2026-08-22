# DevCrew

A multi-agent coding pipeline built on LangGraph. Four LLM agents — **Planner → Coder → Tester → Reviewer** — collaborate through a self-correcting revision loop to turn a plain-English request into tested, reviewed Python code.

**Live demo:** [devcrew-nine.vercel.app](https://devcrew-nine.vercel.app/)

---

## What it does

You give DevCrew a task in plain English — `"write a function that checks if a number is prime"` — and it runs that request through four cooperating agents:

1. **Planner** turns the request into a formal spec: a function signature, requirements, and edge cases.
2. **Coder** writes Python against that spec.
3. **Tester** generates a pytest suite and runs the code in a sandbox.
4. **Reviewer** reads the code, the spec, and the test results, and either approves the result or sends it back to the Coder with specific feedback.

If the Reviewer rejects, the loop repeats — Coder revises, Tester re-runs, Reviewer re-checks — until the code is approved or an iteration cap is hit. The whole exchange, including every rejection and the reasoning behind it, is preserved in the final response and rendered as a full revision timeline in the frontend, not just the final answer.

## Architecture

```
                 ┌─────────────┐
   task  ─────▶  │   Planner   │
                 └──────┬──────┘
                        │ spec
                        ▼
                 ┌─────────────┐
            ┌──▶ │    Coder    │
            │    └──────┬──────┘
            │           │ code
            │           ▼
            │    ┌─────────────┐
            │    │   Tester    │
            │    └──────┬──────┘
            │           │ test_results
            │           ▼
            │    ┌─────────────┐
            │    │  Reviewer   │
            │    └──────┬──────┘
            │           │
            │    approved? ──── yes ──▶  done
            │           │
            └────── no ─┘
              (revision loop)
```

Each node reads and writes a shared `DevCrewState` object; LangGraph handles the routing and the conditional edge back to the Coder on rejection. The Reviewer also appends a full code/tests/results snapshot per iteration, so the API — and the frontend — can render exactly what changed on every pass, not just the final state.

## Tech stack

| Layer | Choice |
|---|---|
| Agent orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) |
| LLM provider | [Groq](https://groq.com) (OpenAI-compatible API, free tier) |
| API | FastAPI |
| Sandboxed testing | pytest, run per-iteration against generated code |
| Frontend | Static HTML/CSS/JS, deployed on Vercel |
| CI/CD | GitHub Actions → auto-deploy on Render |
| Containerization | Docker |

## Try it

### Live demo

```
https://devcrew-nine.vercel.app/
```

A static frontend that calls the live Render API directly from the browser. Submit a task and watch it move through the pipeline; if the Reviewer rejects a submission, expand the revision timeline to see each iteration's code, tests, test output, and reviewer notes — not just the final approved result.

The backend runs on Render's free tier, which sleeps after periods of inactivity — the first request after a cold start can take up to 30 seconds to wake it back up.

### API

The live API is deployed on Render. Interactive docs (Swagger UI):

```
https://devcrew-gmja.onrender.com/docs
```

Or call it directly:

```bash
curl -X POST https://devcrew-gmja.onrender.com/task \
  -H "Content-Type: application/json" \
  -d '{"task": "write a function that checks if a number is prime"}'
```

### Local development

```bash
git clone https://github.com/Jeetkavaiya/devcrew.git
cd devcrew
pip install -r requirements.txt

# .env: set GROQ_API_KEY and DEVCREW_MODEL

uvicorn src.devcrew.api:app --reload
```

Or via Docker:

```bash
docker build -t devcrew .
docker run -p 8000:8000 --env-file .env devcrew
```

To run the frontend against a local backend instead of the live Render deployment, open `frontend/index.html` with a `?api=` override:

```
frontend/index.html?api=http://localhost:8000/task
```

## Evaluation

DevCrew is evaluated against a 15-task benchmark spanning basic algorithms, string manipulation, and data-structure problems, run end-to-end through the real pipeline (not mocked) using `openai/gpt-oss-120b` via Groq.

**Result: 15/15 tasks passed (100%), averaging 1.67 iterations per task.**

### Getting here

An earlier run stalled at 3/15 (TPM rate-limited) and surfaced two real convergence bugs, both fixed before the full run above:

- **Fence-stripping regression** — the Coder's markdown-fence stripper was anchored to match the entire response, so on revision turns (where the model adds surrounding prose like "Here's the corrected version:") the fences shipped straight into the test sandbox unstripped, causing spurious syntax errors.
- **Coder/Tester function-name mismatch** — the Tester independently guessed the function name from the spec text via regex, which frequently didn't match what the Coder actually named the function, causing import errors at test-collection time.

As an early signal before the full re-run, a single smoke-test task ("max of two numbers") was used as a repeatable probe: before the fixes, it failed to converge in 5 iterations, twice in a row; after the fixes, it passed in 1 iteration on `gpt-oss-20b` and 2 iterations on `gpt-oss-120b`. The full 15-task run above confirms that at scale.

### Re-running the eval

```bash
python run_eval.py --resume --output eval_results/eval_20260818_174608.json
```

`--resume` skips already-completed tasks and only runs what's missing — useful if a run gets interrupted mid-way by a transient rate limit.

## Known limitations

- **Groq free-tier quota** caps both requests-per-minute and tokens-per-day, which constrains how much of the pipeline (including its own eval harness) can run in a single session.
- **`gpt-oss-20b`** works for fast syntax/quota smoke-testing but does not reliably converge on real eval tasks — it's a dev fallback, not an eval model.
- **Render free-tier cold starts** mean the first request to the live API after a period of inactivity can take up to ~30 seconds.

## Project structure

```
devcrew/
├── src/devcrew/
│   ├── nodes/           # planner.py, coder.py, tester.py, reviewer.py
│   ├── state.py         # shared DevCrewState schema
│   ├── spec_utils.py    # shared spec-parsing helpers
│   ├── llm.py           # model selection via DEVCREW_MODEL env var
│   └── api.py           # FastAPI app, /task endpoint, CORS
├── frontend/             # static HTML/CSS/JS frontend, deployed on Vercel
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── favicon.svg
├── run_eval.py            # eval harness
├── eval_results/          # eval run outputs (gitignored)
├── tests/                 # unit + live-LLM test suite
├── Dockerfile
└── .github/workflows/     # CI/CD

```