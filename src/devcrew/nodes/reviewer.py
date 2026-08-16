from devcrew.llm import complete
from devcrew.state import DevCrewState

REVIEWER_SYSTEM_PROMPT = """You are the Reviewer in a multi-agent software development crew.

You will be given a specification, the Coder's implementation, the Tester's
test file, and the test run results. Decide whether the code should be
approved or sent back for revision.

Apply a strict standard:
- If the test results show anything other than a clean pass, reject. A
  failing, erroring, or timed-out test run always means rejection, even if
  you suspect the test itself is flawed. You are not allowed to override a
  test failure.
- Reject if the code deviates from the spec in any way, even a small one.
- Reject if any edge case listed in the spec is not handled.
- Do not reject for style preferences alone (naming, formatting, minor
  inefficiency) if the spec is fully satisfied and tests pass cleanly.

Respond in exactly this format, nothing else:

APPROVED: yes
or
APPROVED: no

NOTES: <your reasoning>

If rejecting, the notes must be specific and actionable, since a separate
Coder agent will use them to revise the code without seeing your full
reasoning process, only this notes text. Point to the exact spec
requirement, edge case, or test failure that caused the rejection.
"""

REVIEWER_USER_TEMPLATE = """\
Specification:
{spec}

Code under review:
{code}

Tests written against the spec:
{tests}

Test run results:
{test_results}

Review this submission now.
"""


def _parse_review(raw: str) -> tuple[bool, str]:
    """Parse the reviewer's structured response into (approved, notes).

    Looks for an "APPROVED: yes/no" line and a "NOTES:" section. Falls
    back to treating the whole response as notes and defaulting to
    rejected if the expected format isn't found, since a rejection that
    goes back for another look is a safer failure mode than a silent
    approval.
    """
    approved = False
    notes = raw.strip()

    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("approved:"):
            value = stripped.split(":", 1)[1].strip().lower()
            approved = value.startswith("y")
            break

    notes_index = raw.lower().find("notes:")
    if notes_index != -1:
        notes = raw[notes_index + len("notes:") :].strip()

    return approved, notes


def reviewer_node(state: DevCrewState) -> dict:
    """Review the current code against the spec and test results.

    Returns a partial state update: `approved` (bool), an appended
    `ReviewFeedback` entry in `review_feedback`, and an incremented
    `iteration_count`. Does not mutate `state` in place, matching the
    merge pattern used by the other nodes.
    """
    user_message = REVIEWER_USER_TEMPLATE.format(
        spec=state["spec"],
        code=state["code"],
        tests=state["tests"],
        test_results=state["test_results"],
    )

    raw_response = complete(system=REVIEWER_SYSTEM_PROMPT, user=user_message)
    approved, notes = _parse_review(raw_response)

    # Hard backstop: never trust the model's approval over the actual
    # sandbox outcome. The prompt already instructs the reviewer to reject
    # on any non-passing test run, but this is enforced in code too so a
    # misbehaving or confused model response can't slip a failing result
    # through as approved.
    test_results = state.get("test_results", "")
    tests_did_not_pass = "status: passed" not in test_results.lower()
    if approved and tests_did_not_pass:
        approved = False
        notes = (
            "Overridden: reviewer response indicated approval, but the "
            "test run did not report a clean pass. Test failure always "
            "forces rejection. Original notes: " + notes
        )

    iteration_count = state.get("iteration_count", 0) + 1

    feedback_history = list(state.get("review_feedback") or [])
    feedback_history.append(
        {
            "iteration": iteration_count,
            "approved": approved,
            "notes": notes,
        }
    )

    return {
        "approved": approved,
        "review_feedback": feedback_history,
        "iteration_count": iteration_count,
    }