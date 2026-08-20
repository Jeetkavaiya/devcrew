from __future__ import annotations

from devcrew.llm import complete
from devcrew.sandbox import run_pytest_on_files
from devcrew.spec_utils import extract_function_name
from devcrew.state import DevCrewState

TESTER_SYSTEM_PROMPT = """\
You are the Tester agent on an automated software development crew.

You will be given a SPECIFICATION for a Python function. Write a pytest \
test suite that verifies an implementation of that spec.

Rules:
- Write tests against the SPEC only. You have not seen and must not assume \
anything about a particular implementation's internals.
- Import the function under test with: `from solution import <function_name>`
- Cover the normal case, at least one edge case (e.g. empty input, \
boundary values), and at least one invalid-input case if the spec implies \
one is possible.
- Use plain `assert` statements, standard pytest style (`def test_...():`).
- Output ONLY the raw Python test file contents. No markdown fences, no \
prose, no explanation before or after the code.
"""

TESTER_USER_TEMPLATE = """\
Specification:
{spec}

Write the pytest test file now. The function will be importable as:
from solution import {function_name}
"""


def _strip_code_fences(text: str) -> str:
    """Defensive cleanup in case the LLM wraps output in ```python fences
    despite being told not to. Mirrors the kind of guard you'd want on any
    LLM-authored file before it hits disk/subprocess.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


def tester_node(state: DevCrewState) -> dict:
    """Write tests from state["spec"], execute against state["code"] in the
    sandbox, and return updates for state["tests"] and state["test_results"].

    Returns a partial-state dict (LangGraph merge pattern), matching how
    planner_node / coder_node are described as working — this does not
    mutate `state` in place.
    """
    spec = state["spec"]
    code = state["code"]

    function_name = extract_function_name(spec)

    raw_test_code = complete(
        system=TESTER_SYSTEM_PROMPT,
        user=TESTER_USER_TEMPLATE.format(spec=spec, function_name=function_name),
        max_tokens=2000,
    )
    test_code = _strip_code_fences(raw_test_code)

    sandbox_result = run_pytest_on_files(
        code=code,
        test_code=test_code,
        code_filename="solution.py",
        test_filename="test_solution.py",
    )

    test_results = _format_test_results(sandbox_result)

    return {
        "tests": test_code,
        "test_results": test_results,
    }


def _format_test_results(sandbox_result) -> str:
    """Render a SandboxResult as the single formatted string state.py's
    `test_results: str` field expects.

    state.py's own comment describes this field as "raw pass/fail/error
    output from the sandbox run" (str, not a structured type), so this
    stays a plain human/LLM-readable report rather than JSON — the
    Reviewer node (Day 3) will most likely feed this straight into a
    prompt, where a readable block is more useful than a serialized dict.

    Format is deliberately stable/parseable-by-eye: a PASSED/FAILED header
    line, then stdout/stderr, so both a human skimming logs and an LLM
    reading it as review context get the pass/fail signal immediately
    without hunting for it.
    """
    if sandbox_result.timed_out:
        status = "TIMED OUT"
    elif sandbox_result.errored:
        status = "ERROR"
    elif sandbox_result.passed:
        status = "PASSED"
    else:
        status = "FAILED"

    lines = [
        f"status: {status}",
        f"returncode: {sandbox_result.returncode}",
        f"duration_seconds: {sandbox_result.duration_seconds:.3f}",
    ]
    if sandbox_result.error_message:
        lines.append(f"error_message: {sandbox_result.error_message}")
    lines.append("")
    lines.append("--- stdout ---")
    lines.append(sandbox_result.stdout or "(empty)")
    lines.append("")
    lines.append("--- stderr ---")
    lines.append(sandbox_result.stderr or "(empty)")

    return "\n".join(lines)