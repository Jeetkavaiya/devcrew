from langgraph.graph import END, StateGraph

from devcrew.nodes.coder import coder_node
from devcrew.nodes.planner import planner_node
from devcrew.state import DevCrewState


def build_graph():
    """Build the DevCrew graph.

    Day 1 scope: Planner -> Coder -> END, a straight line with no loop.
    Tester, Reviewer, and the conditional revision cycle are added on
    Day 2 and Day 3 respectively.
    """
    graph = StateGraph(DevCrewState)

    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", END)

    return graph.compile()
