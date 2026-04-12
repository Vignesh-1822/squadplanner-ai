"""dynamic_tool_selection node — decide which tools/subgraphs to invoke."""

from agent.state import TripState


def dynamic_tool_selection(state: TripState) -> dict:
    """Route to SerpAPI, Places, routes, weather, etc."""
    return {}
