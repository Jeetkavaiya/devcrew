from devcrew.llm import complete
from devcrew.state import DevCrewState

SYSTEM_PROMPT = """You are the Planner in a multi-agent software development crew.

Your job is to turn a natural-language coding request into a concrete,
unambiguous specification that a separate Coder agent will implement and a
separate Tester agent will write tests against, without seeing each other's
work. Because of that, the spec must be self-contained.

Write a spec that includes, in this exact order:
1. A line in exactly this format: `Function name: <name>`
2. Function signature (name, parameters with types, return type)
3. A plain-language description of the behavior
4. Edge cases that must be handled (empty input, invalid input, ties, etc.)
5. Any constraints on time/space complexity if relevant

The name on line 1 must exactly match the function name used in the
signature — this is the single source of truth other agents will use to
name and import the function, so it cannot drift from the signature.

Do not write any implementation code. Output only the spec as plain text.
"""


def planner_node(state: DevCrewState) -> dict:
    """Produce a spec from the task description and hand it to the Coder."""
    spec = complete(system=SYSTEM_PROMPT, user=state["task"])
    return {"spec": spec}
