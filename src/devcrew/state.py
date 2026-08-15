from typing import TypedDict


class ReviewFeedback(TypedDict):
    """A single round of reviewer feedback attached to one iteration."""

    iteration: int
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

    # Incremented each time the graph loops back to Coder
    iteration_count: int

    # Set by Reviewer once code passes review; drives the conditional edge
    approved: bool
