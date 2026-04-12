"""Orchestrator StateGraph wiring trip planning nodes."""

from langgraph.graph import END, StateGraph

from agent.state import TripState


def build_graph():
    """Build and compile the main trip orchestrator graph."""
    g = StateGraph(TripState)

    def _stub(state: TripState):
        return state

    g.add_node("stub", _stub)
    g.set_entry_point("stub")
    g.add_edge("stub", END)
    # Replace stub wiring with parse_input → … → assemble_output.
    return g.compile()


graph = build_graph()
