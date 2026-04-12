"""assemble_output node — LLM-assisted final response assembly."""

from agent.state import TripState


def assemble_output(state: TripState) -> dict:
    """Produce user-facing itinerary JSON / narrative."""
    return {}
