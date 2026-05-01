"""Orchestrator StateGraph wiring trip planning nodes."""

import asyncio
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from agent.nodes.budget_analyzer import budget_analysis
from agent.nodes.destination_selector import select_destination
from agent.nodes.fairness_scorer import compute_fairness
from agent.nodes.hotel_searcher import search_hotel
from agent.nodes.input_parser import parse_input
from agent.nodes.output_assembler import assemble_output
from agent.nodes.preference_constraints import extract_preference_constraints
from agent.nodes.tool_selector import dynamic_tool_selection
from agent.state import ActivityResult, DecisionLogEntry, FlightResult, TripState
from agent.subgraphs.itinerary import run_itinerary_subgraph
from db.checkpointer import get_checkpointer
from tools.google_places import fetch_activities_by_category
from tools.open_meteo import fetch_weather
from tools.serpapi import search_flights


def _decision(node: str, decision: str, reason: str) -> DecisionLogEntry:
    return DecisionLogEntry(
        node=node,
        decision=decision,
        reason=reason,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _estimated_flight(member: dict, destination: str, start_date: str, end_date: str) -> FlightResult:
    return FlightResult(
        member_id=member["member_id"],
        origin=member["origin_city"],
        destination=destination,
        price_usd=300.0,
        airline="Estimated",
        depart_time=f"{start_date}T12:00:00",
        return_time=f"{end_date}T12:00:00",
        is_estimated=True,
    )


def _constraint_avoid_terms(preference_constraints: dict | None) -> set[str]:
    if not preference_constraints:
        return set()

    terms = {
        str(term).lower()
        for term in preference_constraints.get("activity_filters", {}).get("avoid_tags", [])
        if str(term).strip()
    }
    for constraint in preference_constraints.get("hard_constraints", []):
        if not isinstance(constraint, dict) or constraint.get("type") != "avoid":
            continue
        terms.add(str(constraint.get("target", "")).lower())
        raw_terms = constraint.get("terms", [])
        if isinstance(raw_terms, str):
            raw_terms = [raw_terms]
        terms.update(str(term).lower() for term in raw_terms if str(term).strip())
    return {term for term in terms if term}


def _activity_violates_constraints(activity: dict, avoid_terms: set[str]) -> bool:
    if not avoid_terms:
        return False

    haystack = " ".join(
        [
            str(activity.get("name", "")),
            str(activity.get("category", "")),
            " ".join(str(tag) for tag in activity.get("tags", [])),
        ]
    ).lower()
    return any(term in haystack for term in avoid_terms)


def _filter_activities_by_constraints(
    activities: list[ActivityResult],
    preference_constraints: dict | None,
) -> tuple[list[ActivityResult], int]:
    avoid_terms = _constraint_avoid_terms(preference_constraints)
    if not avoid_terms:
        return activities, 0

    filtered = [
        activity for activity in activities if not _activity_violates_constraints(activity, avoid_terms)
    ]
    return filtered, len(activities) - len(filtered)


async def parallel_data_fetch(state: TripState) -> dict:
    """Fetch flights, activities, and weather concurrently with safe fallbacks."""
    selected_destination = state["selected_destination"] or ""
    selected_coords = state["selected_destination_coords"] or {"lat": 0.0, "lng": 0.0}

    flight_tasks = [
        search_flights(
            origin=member["origin_city"],
            destination=selected_destination,
            depart_date=state["start_date"],
            return_date=state["end_date"],
            adults=1,
        )
        for member in state["members"]
    ]

    places_task = fetch_activities_by_category(
        destination=selected_destination,
        coords=selected_coords,
        categories=state.get("active_tool_categories", []),
    )

    weather_task = fetch_weather(
        lat=float(selected_coords.get("lat", 0.0)),
        lng=float(selected_coords.get("lng", 0.0)),
        start_date=state["start_date"],
        end_date=state["end_date"],
        destination_name=selected_destination,
    )

    results = await asyncio.gather(
        *flight_tasks,
        places_task,
        weather_task,
        return_exceptions=True,
    )

    n_members = len(state["members"])
    flight_results: list[FlightResult] = []
    estimated_count = 0
    for index, member in enumerate(state["members"]):
        result = results[index]
        if isinstance(result, Exception):
            estimated_count += 1
            flight_results.append(
                _estimated_flight(member, selected_destination, state["start_date"], state["end_date"])
            )
            continue

        flight = dict(result)
        flight["member_id"] = member["member_id"]
        flight_results.append(FlightResult(**flight))

    activities_result = results[n_members]
    weather_result = results[n_members + 1]

    raw_activities = [] if isinstance(activities_result, Exception) or not activities_result else activities_result
    activities, removed_activities = _filter_activities_by_constraints(
        raw_activities,
        state.get("preference_constraints"),
    )
    weather = None if isinstance(weather_result, Exception) else weather_result

    return {
        "flights": flight_results,
        "activities": activities,
        "weather": weather,
        "decision_log": [
            _decision(
                "parallel_data_fetch",
                f"Fetched {len(flight_results)} flights, {len(activities)} activities",
                (
                    f"Weather: {weather['summary'] if weather else 'unavailable'}; "
                    f"estimated flights: {estimated_count}; "
                    f"removed by preference constraints: {removed_activities}"
                ),
            )
        ],
    }


async def city_selection_hitl(state: TripState) -> dict:
    """Pause the graph until the trip leader confirms a destination."""
    resume_value = interrupt(
        {
            "type": "city_selection",
            "candidate_destinations": state["candidate_destinations"],
        }
    )
    resume_data: dict[str, Any] = resume_value if isinstance(resume_value, dict) else {}
    return {
        "selected_destination": resume_data.get("selected_destination"),
        "selected_destination_coords": resume_data.get("selected_destination_coords"),
    }


async def run_itinerary_node(state: TripState) -> dict:
    """Call the itinerary subgraph and merge itinerary results back into TripState."""
    result = await run_itinerary_subgraph(state)
    validation_errors = result.get("validation_errors", [])
    return {
        "days": result.get("days", []),
        "constraint_satisfaction": result.get("constraint_satisfaction", {}),
        "decision_log": result.get("decision_log", [])
        + [
            _decision(
                "run_itinerary_node",
                f"Itinerary complete: {len(result.get('days', []))} days",
                f"Validation errors: {validation_errors}",
            )
        ],
    }


def route_after_budget(state: TripState) -> str:
    status = state.get("budget_status", "ok")
    if status == "severe":
        if state.get("destination_retry_count", 0) >= 3:
            return "ok"
        return "severe"
    if status == "moderate":
        return "moderate"
    return "ok"


def route_after_fairness(state: TripState) -> str:
    if not state.get("fairness_passed", True) and state.get("hotel_retry_count", 0) < 2:
        return "retry_hotel"
    return "done"


def build_graph() -> StateGraph:
    """Build the main trip orchestrator graph."""
    graph = StateGraph(TripState)

    graph.add_node("parse_input", parse_input)
    graph.add_node("extract_preference_constraints", extract_preference_constraints)
    graph.add_node("select_destination", select_destination)
    graph.add_node("city_selection_hitl", city_selection_hitl)
    graph.add_node("dynamic_tool_selection", dynamic_tool_selection)
    graph.add_node("parallel_data_fetch", parallel_data_fetch)
    graph.add_node("budget_analysis", budget_analysis)
    graph.add_node("search_hotel", search_hotel)
    graph.add_node("run_itinerary_node", run_itinerary_node)
    graph.add_node("compute_fairness", compute_fairness)
    graph.add_node("assemble_output", assemble_output)

    graph.set_entry_point("parse_input")
    graph.add_edge("parse_input", "extract_preference_constraints")
    graph.add_edge("extract_preference_constraints", "select_destination")
    graph.add_edge("select_destination", "city_selection_hitl")
    graph.add_edge("city_selection_hitl", "dynamic_tool_selection")
    graph.add_edge("dynamic_tool_selection", "parallel_data_fetch")
    graph.add_edge("parallel_data_fetch", "budget_analysis")
    graph.add_conditional_edges(
        "budget_analysis",
        route_after_budget,
        {
            "severe": "select_destination",
            "moderate": "search_hotel",
            "ok": "search_hotel",
        },
    )
    graph.add_edge("search_hotel", "run_itinerary_node")
    graph.add_edge("run_itinerary_node", "compute_fairness")
    graph.add_conditional_edges(
        "compute_fairness",
        route_after_fairness,
        {
            "retry_hotel": "search_hotel",
            "done": "assemble_output",
        },
    )
    graph.add_edge("assemble_output", END)

    return graph


async def get_compiled_graph():
    """Return the compiled graph with MongoDB checkpointing for HITL support."""
    checkpointer = await get_checkpointer()
    return build_graph().compile(checkpointer=checkpointer)


orchestrator_graph = None


async def initialize_graph() -> None:
    """Initialize the module-level compiled orchestrator graph."""
    global orchestrator_graph
    orchestrator_graph = await get_compiled_graph()
