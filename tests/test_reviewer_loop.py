import os
from unittest.mock import patch

import pytest

from devcrew.graph import build_graph, get_max_iterations, route_after_review
from devcrew.nodes.reviewer import reviewer_node

GROQ_KEY_MISSING = not os.environ.get("GROQ_API_KEY")

# Fast unit tests: routing logic only, no LLM calls, always run

def test_route_approved_goes_to_end():
    state = {"approved": True, "iteration_count": 1}
    assert route_after_review(state) == "end"


def test_route_rejected_under_cap_goes_to_revise():
    state = {"approved": False, "iteration_count": 1}
    assert route_after_review(state) == "revise"


def test_route_rejected_at_cap_goes_to_end():
    state = {"approved": False, "iteration_count": get_max_iterations()}
    assert route_after_review(state) == "end"


def test_route_rejected_over_cap_goes_to_end():
    state = {"approved": False, "iteration_count": get_max_iterations() + 1}
    assert route_after_review(state) == "end"


def test_get_max_iterations_default(monkeypatch):
    monkeypatch.delenv("DEVCREW_MAX_ITERATIONS", raising=False)
    assert get_max_iterations() == 5


def test_get_max_iterations_reads_env(monkeypatch):
    monkeypatch.setenv("DEVCREW_MAX_ITERATIONS", "3")
    assert get_max_iterations() == 3


def _base_state(test_results: str) -> dict:
    return {
        "spec": "spec text",
        "code": "code text",
        "tests": "test text",
        "test_results": test_results,
        "review_feedback": [],
        "iteration_count": 0,
    }


def test_reviewer_backstop_overrides_approval_on_failed_tests():
    """Even if the LLM says APPROVED: yes, a non-passing test_results
    string must force approved back to False. This is the hard
    code-level guard, independent of prompt behavior.
    """
    state = _base_state("status: FAILED\nreturncode: 1\n")
    with patch(
        "devcrew.nodes.reviewer.complete",
        return_value="APPROVED: yes\n\nNOTES: looks fine to me",
    ):
        result = reviewer_node(state)

    assert result["approved"] is False
    assert "Overridden" in result["review_feedback"][-1]["notes"]


def test_reviewer_backstop_allows_approval_on_passed_tests():
    """A genuine passing test result should not be touched by the
    backstop when the model also approves.
    """
    state = _base_state("status: PASSED\nreturncode: 0\n")
    with patch(
        "devcrew.nodes.reviewer.complete",
        return_value="APPROVED: yes\n\nNOTES: clean pass, matches spec",
    ):
        result = reviewer_node(state)

    assert result["approved"] is True
    assert "Overridden" not in result["review_feedback"][-1]["notes"]


def test_reviewer_backstop_does_not_touch_genuine_rejection():
    """A model rejection on failing tests should pass through normally,
    not get relabeled as an override.
    """
    state = _base_state("status: FAILED\nreturncode: 1\n")
    with patch(
        "devcrew.nodes.reviewer.complete",
        return_value="APPROVED: no\n\nNOTES: test suite failed, fix the bug",
    ):
        result = reviewer_node(state)

    assert result["approved"] is False
    assert "Overridden" not in result["review_feedback"][-1]["notes"]


# Live tests: full graph execution against real Groq calls
@pytest.mark.live_llm
@pytest.mark.skipif(GROQ_KEY_MISSING, reason="GROQ_API_KEY not set")
def test_full_loop_reaches_approval_or_cap():
    """Run the full graph on a task and confirm the loop terminates
    correctly: either approved becomes True, or the iteration cap is
    hit and the run still ends instead of looping forever.
    """
    graph = build_graph()
    result = graph.invoke(
        {
            "task": "Write a function that returns the second largest "
            "unique number in a list of integers. Return None if there "
            "are fewer than two unique numbers.",
            "review_feedback": [],
            "iteration_count": 0,
        }
    )

    assert result["iteration_count"] >= 1
    assert result["iteration_count"] <= get_max_iterations()
    assert isinstance(result["approved"], bool)
    assert len(result["review_feedback"]) == result["iteration_count"]

    if not result["approved"]:
        assert result["iteration_count"] >= get_max_iterations()


@pytest.mark.live_llm
@pytest.mark.skipif(GROQ_KEY_MISSING, reason="GROQ_API_KEY not set")
def test_loop_can_take_multiple_iterations():
    """Feed the graph a task that is easy to get subtly wrong on the
    first pass (tight edge-case requirements), to exercise the
    Coder<->Reviewer revision cycle rather than a same-run approval.
    This doesn't force a specific iteration count since model output is
    non-deterministic, but confirms the loop mechanism runs more than a
    single pass at least some of the time across the crew's actual
    behavior, and that state accumulates correctly across iterations.
    """
    graph = build_graph()
    result = graph.invoke(
        {
            "task": "Write a function that takes a list of transactions, "
            "each a dict with 'amount' (float) and 'category' (str), and "
            "returns a dict mapping category to total amount. Must handle "
            "an empty list, negative amounts (refunds), missing keys in a "
            "transaction dict, and category names that differ only by "
            "case (treat them as the same category, using the first-seen "
            "casing).",
            "review_feedback": [],
            "iteration_count": 0,
        }
    )

    assert result["iteration_count"] >= 1
    for i, entry in enumerate(result["review_feedback"], start=1):
        assert entry["iteration"] == i
        assert isinstance(entry["approved"], bool)
        assert isinstance(entry["notes"], str)