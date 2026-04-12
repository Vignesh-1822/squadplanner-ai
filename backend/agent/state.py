"""State TypedDicts for the LangGraph orchestrator and itinerary subgraph."""

import operator
from typing import Annotated, Optional, TypedDict


class MemberInput(TypedDict):
    member_id: str
    name: str
    origin_city: str
    budget_usd: float
    food_restrictions: list[str]
    preference_vector: dict[str, float]
    is_leader: bool


class FlightResult(TypedDict):
    member_id: str
    origin: str
    destination: str
    price_usd: float
    airline: str
    depart_time: str
    return_time: str
    is_estimated: bool


class ActivityResult(TypedDict):
    place_id: str
    name: str
    category: str
    address: str
    lat: float
    lng: float
    price_level: int
    rating: float
    tags: list[str]


class HotelResult(TypedDict):
    name: str
    address: str
    price_per_night_usd: float
    total_price_usd: float
    rating: float
    is_estimated: bool


class WeatherResult(TypedDict):
    destination: str
    date_range: str
    avg_temp_c: float
    precipitation_mm: float
    summary: str


class DayPlan(TypedDict):
    day_number: int
    date: str
    neighborhood: str
    activities: list[ActivityResult]
    meals: list[str]
    routes: list[dict]
    estimated_day_cost_usd: float


class DecisionLogEntry(TypedDict):
    node: str
    decision: str
    reason: str
    timestamp: str


class TripState(TypedDict):
    trip_id: str
    members: list[MemberInput]
    start_date: str
    end_date: str
    trip_duration_days: int
    preference_conflicts: list[str]
    group_preference_vector: dict[str, float]
    active_tool_categories: list[str]
    candidate_destinations: list[dict]
    selected_destination: Optional[str]
    selected_destination_coords: Optional[dict]
    flights: Annotated[list[FlightResult], operator.add]
    activities: Annotated[list[ActivityResult], operator.add]
    weather: Optional[WeatherResult]
    budget_status: Optional[str]
    budget_ceiling_hotel_usd: Optional[float]
    hotel: Optional[HotelResult]
    days: list[DayPlan]
    fairness_scores: dict[str, float]
    compatibility_scores: dict[str, float]
    fairness_passed: bool
    trip_pitch: Optional[str]
    decision_log: Annotated[list[DecisionLogEntry], operator.add]
    destination_retry_count: int
    hotel_retry_count: int
    error: Optional[str]


class ItineraryState(TypedDict):
    trip_id: str
    destination: str
    destination_coords: dict
    start_date: str
    end_date: str
    trip_duration_days: int
    members: list[MemberInput]
    activities: list[ActivityResult]
    hotel: HotelResult
    flights: list[FlightResult]
    weather: Optional[WeatherResult]
    clustered_activities: list[dict]
    days: list[DayPlan]
    feasibility_swap_count: int
    validation_rebuild_count: int
    validation_errors: list[str]
    decision_log: Annotated[list[DecisionLogEntry], operator.add]
    error: Optional[str]
