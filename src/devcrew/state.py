from typing import TypedDict


class ReviewFeedback(TypedDict):
    """A single round of reviewer feedback attached to one iteration."""

    iteration: int
    approved: bool
    notes: str


class IterationSnapshot(TypedDict):
    """A full snapshot of one pass through Coder -> Tester -> Reviewer.

    Unlike `code` / `tests` / `test_results` on DevCrewState, which are
    overwritten on every revision loop, entries here are appended and kept
    around for the life of the run. This exists so consumers (e.g. the API
    response, a frontend trace view) can render what changed at each
    iteration rather than only the final approved result.
    """

    iteration: int
    code: str
    tests: str
    test_results: str
    approved: bool
    notes: str


class DevCrewState(TypedDict):
    """Shared state object passed between every node in the LangGraph.

    Each node reads what it needs from this dict and returns a partial
    update. LangGraph merges the update back into the running state, so
    nodes should never mutate fields they don't own.
    """

    # Set once at the start of a run, never modified after
    task: str

    # Written by Planner, read by Coder and Tester
    spec: str

    # Written by Coder, overwritten on each revision loop
    code: str

    # Written by Tester: the pytest-style test source, independent of Coder
    tests: str

    # Written by Tester: raw pass/fail/error output from the sandbox run
    test_results: str

    # Written by Reviewer: the full history of feedback across iterations
    review_feedback: list[ReviewFeedback]

    # Written by Reviewer: a full code/tests/results snapshot per iteration,
    # for rendering the complete revision trace (not just final state)
    iterations: list[IterationSnapshot]

    # Incremented each time the graph loops back to Coder
    iteration_count: int

    # Set by Reviewer once code passes review; drives the conditional edge
    approved: bool