"""Full itinerary agent subgraph."""

from langgraph.graph import END, StateGraph

from agent.state import ItineraryState


def build_itinerary_subgraph():
    """Compile the itinerary-only StateGraph."""
    g = StateGraph(ItineraryState)

    def _stub(state: ItineraryState):
        return state

    g.add_node("stub", _stub)
    g.set_entry_point("stub")
    g.add_edge("stub", END)
    return g.compile()
