from __future__ import annotations

import os

import pytest

from devcrew.graph import build_graph
from devcrew.sandbox import run_pytest_on_files

HAS_GROQ_KEY = bool(os.environ.get("GROQ_API_KEY"))

skip_reason = "GROQ_API_KEY not set; skipping live-chain tests"

HARDCODED_REQUESTS = [
    "Write a Python function that takes a list of numbers and returns the "
    "median.",
    "Write a Python function that takes a list of transactions (dicts with "
    "'category' and 'amount' keys) and returns the top 3 spending "
    "categories by total amount.",
    "Write a Python function that checks whether a given string is a "
    "valid palindrome, ignoring case and non-alphanumeric characters.",
    "Write a Python function that takes a list of integers and returns "
    "all unique pairs that sum to a given target value.",
    "Write a Python function that flattens an arbitrarily nested list of "
    "integers into a single flat list.",
]


@pytest.mark.skipif(not HAS_GROQ_KEY, reason=skip_reason)
@pytest.mark.parametrize("task", HARDCODED_REQUESTS)
def test_planner_coder_tester_chain(task):
    """End-to-end: Planner -> Coder -> Tester produces a spec, code, and
    test results, with the sandbox actually executing something.

    This test intentionally does NOT assert that test_results["passed"] is
    True for every request. The point of Day 2 is that the pipeline runs
    live end to end and produces real sandboxed execution results — a
    Coder implementation failing its independently-written tests is a
    valid, informative outcome at this stage (that's exactly the signal
    the Reviewer loop in Day 3 exists to act on). We assert the pipeline
    *ran* and *produced a real result*, not that every attempt succeeded.
    """
    graph = build_graph()

    initial_state = {
        "task": task,
        "spec": "",
        "code": "",
        "tests": "",
        "test_results": {},
        "review_feedback": [],
        "iteration_count": 0,
        "approved": False,
    }

    result = graph.invoke(initial_state)

    assert result["spec"], "Planner did not produce a spec"
    assert result["code"], "Coder did not produce code"
    assert result["tests"], "Tester did not produce a test file"

    test_results = result["test_results"]
    assert test_results, "Tester did not produce test_results"
    assert isinstance(test_results, str)
    assert "status:" in test_results

    assert "status: ERROR" not in test_results, (
        f"Sandbox failed to execute at all:\n{test_results}"
    )

def test_sandbox_runs_passing_tests():
    code = "def add(a, b):\n    return a + b\n"
    test_code = (
        "from solution import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )
    result = run_pytest_on_files(code, test_code)
    assert result.passed is True
    assert result.returncode == 0
    assert not result.timed_out
    assert not result.errored


def test_sandbox_reports_failing_tests_without_erroring():
    code = "def add(a, b):\n    return a - b  # bug\n"
    test_code = (
        "from solution import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )
    result = run_pytest_on_files(code, test_code)
    assert result.passed is False
    assert result.returncode != 0
    # A failing test is not the same as a sandbox error.
    assert not result.errored
    assert not result.timed_out


def test_sandbox_enforces_timeout():
    code = "def noop():\n    pass\n"
    test_code = (
        "import time\n\n"
        "def test_hangs():\n"
        "    time.sleep(30)\n"
    )
    result = run_pytest_on_files(code, test_code, timeout_seconds=2)
    assert result.timed_out is True
    assert result.errored is True
    assert result.passed is False


def test_sandbox_isolation_no_leftover_files(tmp_path):
    code = "def add(a, b):\n    return a + b\n"
    test_code = (
        "from solution import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )
    result = run_pytest_on_files(code, test_code)
    assert result.passed is True
    assert set(result.files_written) == {"solution.py", "test_solution.py"}