"""TripState and ItineraryState TypedDicts for LangGraph."""

from typing import Any, NotRequired, TypedDict


class ItineraryState(TypedDict, total=False):
    """State carried by the itinerary subgraph."""

    slots: list[dict[str, Any]]
    day_plans: list[dict[str, Any]]
    messages: list[dict[str, Any]]


class TripState(TypedDict, total=False):
    """Top-level orchestrator graph state."""

    trip_id: str
    raw_input: str
    parsed: dict[str, Any]
    destination: str | None
    itinerary: ItineraryState
    budget_notes: str
    fairness: dict[str, Any]
    output: dict[str, Any]
    pending_hitl: NotRequired[dict[str, Any]]
