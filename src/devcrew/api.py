from fastapi import FastAPI
from pydantic import BaseModel

from devcrew.graph import build_graph
from devcrew.state import ReviewFeedback

app = FastAPI(title="DevCrew API")

_graph = build_graph()


class TaskRequest(BaseModel):
    task: str


class TaskResponse(BaseModel):
    task: str
    spec: str
    code: str
    tests: str
    test_results: str
    approved: bool
    iteration_count: int
    review_feedback: list[ReviewFeedback]


def _initial_state(task: str) -> dict:
    """Build a fresh DevCrewState for a new run, matching the shape used
    across the test suite (test_full_chain.py, test_reviewer_loop.py).
    """
    return {
        "task": task,
        "spec": "",
        "code": "",
        "tests": "",
        "test_results": "",
        "review_feedback": [],
        "iteration_count": 0,
        "approved": False,
    }


@app.post("/task", response_model=TaskResponse)
def run_task(request: TaskRequest) -> TaskResponse:
    """Run a coding request through the full Planner -> Coder -> Tester ->
    Reviewer graph and return the final result plus the full iteration
    trace. This blocks until the graph finishes (approval or iteration
    cap) — see handoff notes on why this is sync rather than a background
    job for this project's scope.
    """
    result = _graph.invoke(_initial_state(request.task))
    return TaskResponse(
        task=request.task,
        spec=result["spec"],
        code=result["code"],
        tests=result["tests"],
        test_results=result["test_results"],
        approved=result["approved"],
        iteration_count=result["iteration_count"],
        review_feedback=result["review_feedback"],
    )


@app.get("/health")
def health() -> dict:
    """Basic liveness check — no LLM calls, no token cost."""
    return {"status": "ok"}