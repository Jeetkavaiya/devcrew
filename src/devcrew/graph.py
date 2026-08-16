import os

from langgraph.graph import END, StateGraph
from devcrew.nodes.coder import coder_node
from devcrew.nodes.planner import planner_node
from devcrew.nodes.reviewer import reviewer_node
from devcrew.nodes.tester import tester_node
from devcrew.state import DevCrewState


def get_max_iterations() -> int:
    """Return the iteration cap for the revision loop, from env with a
    fallback. Read as a function rather than a module-level constant so
    tests can monkeypatch the env var without reimporting this module.
    """
    return int(os.environ.get("DEVCREW_MAX_ITERATIONS", "5"))


def route_after_review(state: DevCrewState) -> str:
    """Decide where to go after the Reviewer runs.

    Approved code always ends the run. Rejected code loops back to the
    Coder for another attempt, unless the iteration cap has been reached,
    in which case the run ends anyway rather than looping forever. This
    is a plain function of state so it can be unit tested directly with a
    fake state dict, no LLM or graph execution needed.
    """
    if state["approved"]:
        return "end"
    if state["iteration_count"] >= get_max_iterations():
        return "end"
    return "revise"


def build_graph():
    """Build the DevCrew graph.
    """
    graph = StateGraph(DevCrewState)

    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("tester", tester_node)
    graph.add_node("reviewer", reviewer_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "tester")
    graph.add_edge("tester", "reviewer")
    graph.add_conditional_edges(
        "reviewer",
        route_after_review,
        {"end": END, "revise": "coder"},
    )

    return graph.compile()