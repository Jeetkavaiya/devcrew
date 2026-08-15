import os

import pytest

from devcrew.graph import build_graph

# Requires a live GROQ_API_KEY since this exercises the real chain,
# not a mocked one. Skipped automatically in environments without it.
requires_api_key = pytest.mark.skipif(
    "GROQ_API_KEY" not in os.environ,
    reason="GROQ_API_KEY not set",
)

HARDCODED_REQUESTS = [
    "Write a Python function that returns the nth Fibonacci number.",
    (
        "Write a Python function that takes a list of transactions "
        "(each a dict with 'category' and 'amount') and returns the "
        "top 3 spending categories by total amount."
    ),
    (
        "Write a Python function that checks whether a string is a "
        "valid palindrome, ignoring case and non-alphanumeric characters."
    ),
]


@requires_api_key
@pytest.mark.parametrize("task", HARDCODED_REQUESTS)
def test_planner_produces_spec_and_coder_produces_code(task):
    graph = build_graph()

    result = graph.invoke(
        {
            "task": task,
            "spec": "",
            "code": "",
            "tests": "",
            "test_results": "",
            "review_feedback": [],
            "iteration_count": 0,
            "approved": False,
        }
    )

    assert result["spec"].strip() != ""
    assert result["code"].strip() != ""
    assert "def " in result["code"]
