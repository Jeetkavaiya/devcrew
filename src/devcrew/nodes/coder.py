from devcrew.llm import complete
from devcrew.state import DevCrewState

SYSTEM_PROMPT = """You are the Coder in a multi-agent software development crew.

Implement the given spec as a single Python function. A separate Tester
agent will write tests against the spec independently, and a separate
Reviewer agent will check your code against real execution results, so
write code that actually satisfies the spec rather than code that merely
looks plausible.

Rules:
- Output only a Python code block, nothing else.
- Include type hints on the function signature.
- Handle every edge case listed in the spec explicitly.
- If revision feedback is provided, treat it as the primary thing to fix.
"""


def coder_node(state: DevCrewState) -> dict:
    """Produce or revise code based on the spec and any prior feedback."""
    user_message = f"Spec:\n{state['spec']}"

    feedback_history = state.get("review_feedback") or []
    if feedback_history:
        latest = feedback_history[-1]
        user_message += f"\n\nPrevious code:\n{state['code']}"
        user_message += f"\n\nReviewer feedback to address:\n{latest['notes']}"

    code = complete(system=SYSTEM_PROMPT, user=user_message)
    return {"code": code}
