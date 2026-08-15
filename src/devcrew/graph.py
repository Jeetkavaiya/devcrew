from langgraph.graph import END, StateGraph

from devcrew.nodes.coder import coder_node
from devcrew.nodes.planner import planner_node
from devcrew.nodes.tester import tester_node 
from devcrew.state import DevCrewState


def build_graph():
    """Build the DevCrew graph.
    """
    graph = StateGraph(DevCrewState)

    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("tester", tester_node) 

    graph.set_entry_point("planner")
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "tester")
    graph.add_edge("tester", END)

    return graph.compile()
