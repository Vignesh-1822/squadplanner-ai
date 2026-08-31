"""Agentic, tool-grounded refinement planner.

Free-text refinement requests are interpreted by Claude (Haiku) running a small
tool-calling loop. The model can look up real places (Google Places) and browse real
candidate activities before committing to a structured plan, so every concrete venue it
proposes is grounded in real data rather than hallucinated.

A second, independent model call (the critic) reviews the planner's proposed plan against
the group's hard constraints before it is applied. If the critic flags a problem, the
planner gets one bounded chance to revise and resubmit. The critic fails open (approves)
on any error so it can never block a refinement from completing.

The planner "proposes" (which edits, which places); the critic "reviews" (does the plan
hold up against hard constraints); deterministic code "disposes" (fetches real places,
builds the LangGraph state patch, picks the graph re-entry node). If the agent loop fails
for any reason, callers fall back to the deterministic regex parser.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from agent.nodes.parse_refinement import (
    UnsupportedRefinement,
    _budget_patch,
    _patched_constraints,
)
from config import get_llm
from tools.google_places import fetch_activities_by_category, find_place_by_text

logger = logging.getLogger(__name__)

MAX_AGENT_TURNS = 6
MAX_CRITIC_REVISIONS = 1
RERUN_NODES = ("search_hotel", "budget_analysis", "compute_fairness")


class AgentPlanningError(RuntimeError):
    """Raised when the agentic loop cannot produce a usable plan (callers fall back)."""


# --- Tool schemas the model can call -------------------------------------------------


class FindPlace(BaseModel):
    """Look up ONE specific real place by name or short description near the destination.

    Use this for concrete venues the user names (e.g. "The Bean", "Willis Tower") or a
    short descriptor ("rooftop bar near downtown"). Returns the real place if found.
    """

    query: str = Field(description="Place name or short descriptor to search for.")


class FetchActivities(BaseModel):
    """Fetch a batch of real candidate activities for a category to choose from."""

    category: Literal["outdoor", "food", "nightlife", "urban", "shopping"] = Field(
        description="Activity category to pull real candidate places for."
    )


class SubmitRefinementPlan(BaseModel):
    """Submit the final plan once every place you want to add has been grounded via tools."""

    in_scope: bool = Field(
        description=(
            "False if the request requires a brand-new trip (changing destination, dates, "
            "or travelers). True for itinerary/budget/pace/meal/pitch edits."
        )
    )
    out_of_scope_reason: Optional[str] = Field(
        default=None, description="If in_scope is false, a short user-facing explanation."
    )
    summary: str = Field(description="Short human-readable summary of the changes you are making.")
    target_day: Optional[int] = Field(
        default=None, description="Day number to focus changes on, if the user specified one."
    )
    rerun_from: Literal["search_hotel", "budget_analysis", "compute_fairness"] = Field(
        default="search_hotel",
        description=(
            "Where to re-run the planning graph: 'budget_analysis' for cheaper-hotel/trip, "
            "'compute_fairness' for pitch-only wording changes, otherwise 'search_hotel'."
        ),
    )
    add_places: list[str] = Field(
        default_factory=list,
        description="Exact names of real places to add (must have been confirmed via FindPlace).",
    )
    remove_terms: list[str] = Field(
        default_factory=list,
        description="Names or terms of activities to remove/avoid.",
    )
    preferred_categories: list[str] = Field(
        default_factory=list,
        description="Categories to lean into: outdoor, food, nightlife, urban, shopping.",
    )
    pace: Optional[Literal["relaxed", "packed"]] = Field(
        default=None, description="Set if the user asked for a slower or busier pace."
    )
    cuisine: Optional[str] = Field(default=None, description="Cuisine to ensure in meals, if requested.")
    cost_sensitivity: Optional[Literal["lower_cost"]] = Field(
        default=None, description="Set 'lower_cost' if the user asked to make it cheaper."
    )
    pitch_instruction: Optional[str] = Field(
        default=None, description="Set if the user only wants the written pitch/wording changed."
    )


class SubmitCriticVerdict(BaseModel):
    """Approve a proposed refinement plan, or flag exactly what must change."""

    approved: bool = Field(
        description="True if the plan satisfies the user's request and respects the group's hard constraints."
    )
    reason: str = Field(
        description="One sentence: why it's approved, or exactly what must change if not."
    )


# --- Context construction ------------------------------------------------------------


def _normalize_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _name_present(name: str, activities: list[dict]) -> bool:
    target = _normalize_name(name)
    if not target:
        return False
    for activity in activities:
        existing = _normalize_name(activity.get("name", ""))
        if existing and (existing == target or target in existing or existing in target):
            return True
    return False


def _itinerary_summary(state: dict) -> str:
    lines: list[str] = []
    for day in state.get("days", []):
        stops = day.get("route_stops") or []
        if stops:
            labels = ", ".join(str(stop.get("label")) for stop in stops if stop.get("label"))
        else:
            labels = ", ".join(
                str(activity.get("name"))
                for activity in day.get("activities", [])
                if activity.get("name")
            )
        lines.append(
            f"Day {day.get('day_number')} ({day.get('neighborhood', 'TBD')}): "
            f"{labels or 'no stops'} | meals: {', '.join(day.get('meals', [])) or 'n/a'}"
        )
    return "\n".join(lines) or "No itinerary days yet."


def _pool_summary(state: dict, limit: int = 40) -> str:
    seen: list[str] = []
    for activity in state.get("activities", []):
        name = activity.get("name")
        category = activity.get("category", "activity")
        if name:
            seen.append(f"{name} ({category})")
        if len(seen) >= limit:
            break
    return ", ".join(seen) or "No activities fetched yet."


def _build_messages(message: str, state: dict):
    from langchain_core.messages import HumanMessage, SystemMessage

    system = (
        "You are the refinement agent for a group-trip planner. The user wants to tweak an "
        "already-generated itinerary using free-text. Your job is to understand ANY phrasing, "
        "ground every concrete place in real data using the tools, then submit a structured plan.\n\n"
        "Rules:\n"
        "- Use FindPlace to confirm any specific venue the user names before adding it. If a "
        "lookup returns nothing, try an alternate/official name (e.g. 'The Bean' -> 'Cloud Gate').\n"
        "- Use FetchActivities to browse real options when the user asks for a category/vibe.\n"
        "- Only put a place in add_places after FindPlace (or FetchActivities) confirms it is real.\n"
        "- Make the SMALLEST change that satisfies the request; preserve unaffected days.\n"
        "- If the request needs a new trip (different destination, dates, or travelers), submit "
        "with in_scope=false and a short out_of_scope_reason.\n"
        "- When done, you MUST call SubmitRefinementPlan exactly once.\n"
    )
    human = (
        f"User request: {message}\n\n"
        f"Destination: {state.get('selected_destination')}\n"
        f"Trip dates: {state.get('start_date')} to {state.get('end_date')}\n"
        f"Current itinerary:\n{_itinerary_summary(state)}\n\n"
        f"Already-fetched real activities you can reuse:\n{_pool_summary(state)}\n\n"
        f"Group preference constraints: {json.dumps(state.get('preference_constraints', {}), default=str)}\n"
        "Decide what to change, ground the places, then submit the plan."
    )
    return [SystemMessage(content=system), HumanMessage(content=human)]


# --- The critic pass ------------------------------------------------------------------


async def _critique_plan(plan: dict, message: str, state: dict) -> tuple[bool, str]:
    """Second-opinion pass: an independent model call checks the planner's proposed plan
    against the group's hard constraints before it is applied.

    Fails open (approves) on any error - tool-binding failure, malformed response, timeout -
    so a critic bug can never block a refinement from completing.
    """
    try:
        llm = get_llm().bind_tools([SubmitCriticVerdict])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not bind critic tool (%s); approving by default", exc)
        return True, "Critic unavailable; approved by default."

    prompt = (
        "Review this trip-refinement plan before it is applied. Approve it unless it clearly "
        "contradicts the user's request or violates one of the group's hard constraints. "
        "You MUST call SubmitCriticVerdict exactly once.\n\n"
        f"User request: {message}\n"
        f"Group hard constraints: {json.dumps(state.get('preference_constraints', {}).get('hard_constraints', []), default=str)}\n"
        f"Proposed plan: {json.dumps(plan, default=str)}"
    )

    try:
        ai_message = await llm.ainvoke(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Critic invocation failed (%s); approving by default", exc)
        return True, "Critic unavailable; approved by default."

    for call in getattr(ai_message, "tool_calls", None) or []:
        if call.get("name") == "SubmitCriticVerdict":
            args = call.get("args", {}) or {}
            return bool(args.get("approved", True)), str(args.get("reason", ""))

    return True, "Critic did not return a verdict; approved by default."


# --- The agentic loop ----------------------------------------------------------------


async def plan_refinement_agentic(message: str, state: dict) -> tuple[dict, list[dict]]:
    """Run the Haiku tool-calling loop, then have an independent critic review the plan.

    Returns (plan, resolved_activities). Raises UnsupportedRefinement when the agent judges
    the request out of scope, and AgentPlanningError on any loop failure so the caller can
    fall back to the regex parser.
    """
    from langchain_core.messages import HumanMessage, ToolMessage

    destination = state.get("selected_destination") or ""
    coords = state.get("selected_destination_coords") or {"lat": 0.0, "lng": 0.0}

    try:
        llm = get_llm().bind_tools([FindPlace, FetchActivities, SubmitRefinementPlan])
    except Exception as exc:  # noqa: BLE001
        raise AgentPlanningError(f"Could not bind tools: {exc}") from exc

    messages = _build_messages(message, state)
    resolved: list[dict] = []
    critic_revisions = 0

    for _turn in range(MAX_AGENT_TURNS):
        try:
            ai_message = await llm.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001
            raise AgentPlanningError(f"LLM invocation failed: {exc}") from exc

        messages.append(ai_message)
        tool_calls = getattr(ai_message, "tool_calls", None) or []
        if not tool_calls:
            raise AgentPlanningError("Agent produced no tool call.")

        plan: dict | None = None
        for call in tool_calls:
            name = call.get("name")
            args = call.get("args", {}) or {}
            call_id = call.get("id")

            if name == "SubmitRefinementPlan":
                plan = args
                messages.append(ToolMessage(content="Plan received.", tool_call_id=call_id))
                continue

            if name == "FindPlace":
                place = await find_place_by_text(
                    query=str(args.get("query", "")), destination=destination, coords=coords
                )
                if place:
                    resolved.append(dict(place))
                    messages.append(
                        ToolMessage(
                            content=json.dumps(
                                {
                                    "found": {
                                        "name": place.get("name"),
                                        "address": place.get("address"),
                                        "category": place.get("category"),
                                    }
                                }
                            ),
                            tool_call_id=call_id,
                        )
                    )
                else:
                    messages.append(
                        ToolMessage(
                            content=json.dumps(
                                {"found": None, "note": "No match; try an alternate/official name."}
                            ),
                            tool_call_id=call_id,
                        )
                    )
                continue

            if name == "FetchActivities":
                category = str(args.get("category", ""))
                fetched = await fetch_activities_by_category(
                    destination=destination, coords=coords, categories=[category]
                )
                new_items = _dedupe(state.get("activities", []) + resolved, fetched)
                resolved.extend(dict(item) for item in new_items)
                messages.append(
                    ToolMessage(
                        content=json.dumps(
                            {"category": category, "options": [item.get("name") for item in fetched][:10]}
                        ),
                        tool_call_id=call_id,
                    )
                )
                continue

            messages.append(ToolMessage(content="Unknown tool.", tool_call_id=call_id))

        if plan is not None:
            finalized = await _finalize_plan(plan, message, state, resolved, destination, coords)
            approved, critic_reason = await _critique_plan(finalized, message, state)
            finalized["critic_verdict"] = {"approved": approved, "reason": critic_reason}

            if approved or critic_revisions >= MAX_CRITIC_REVISIONS:
                return finalized, resolved

            critic_revisions += 1
            messages.append(
                HumanMessage(
                    content=(
                        f"A review pass flagged this plan: {critic_reason} "
                        "Please revise and call SubmitRefinementPlan again."
                    )
                )
            )
            continue

    raise AgentPlanningError("Agent did not submit a plan within the turn budget.")


def _dedupe(existing: list[dict], candidates: list[dict]) -> list[dict]:
    seen = {_normalize_name(item.get("name", "")) for item in existing}
    result: list[dict] = []
    for candidate in candidates:
        key = _normalize_name(candidate.get("name", ""))
        if key and key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


async def _finalize_plan(
    plan: dict,
    message: str,
    state: dict,
    resolved: list[dict],
    destination: str,
    coords: dict,
) -> dict:
    if not plan.get("in_scope", True):
        raise UnsupportedRefinement(
            str(plan.get("out_of_scope_reason") or "This change needs a brand-new trip."),
            code="unsupported_agentic_scope",
        )

    # Safety net: guarantee every requested add is grounded even if the model forgot a lookup.
    have = list(state.get("activities", [])) + resolved
    for name in [str(item) for item in plan.get("add_places", []) if item]:
        if _name_present(name, have):
            continue
        place = await find_place_by_text(query=name, destination=destination, coords=coords)
        if place:
            resolved.append(dict(place))
            have.append(dict(place))

    return plan


# --- State patch construction --------------------------------------------------------


def build_agentic_state_patch(
    state: dict,
    plan: dict,
    message: str,
    resolved: list[dict],
) -> tuple[dict, str]:
    """Translate an agentic plan + grounded places into a LangGraph state patch."""
    target_day = plan.get("target_day")
    directives: dict[str, Any] = {"summary": plan.get("summary") or message, "target_day": target_day}

    add_places = [str(item) for item in plan.get("add_places", []) if item]
    remove_terms = [str(item) for item in plan.get("remove_terms", []) if item]
    preferred = [str(item) for item in plan.get("preferred_categories", []) if item]

    if add_places:
        directives["add_place"] = add_places
    if remove_terms:
        directives["avoid_terms"] = remove_terms
    if preferred:
        directives["preferred_categories"] = preferred
    if plan.get("pace"):
        directives["pace"] = plan["pace"]
    if plan.get("cuisine"):
        directives["cuisine"] = plan["cuisine"]
    if plan.get("cost_sensitivity"):
        directives["cost_sensitivity"] = plan["cost_sensitivity"]
    if plan.get("pitch_instruction"):
        directives["pitch_instruction"] = plan["pitch_instruction"]

    current_refinement = {
        "message": message,
        "intent": "agentic_refinement",
        "target": "itinerary",
        "target_day": target_day,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    history_entry = {**current_refinement, "summary": directives["summary"]}
    history = list(state.get("refinement_history", [])) + [history_entry]

    patch: dict[str, Any] = {
        "current_refinement": current_refinement,
        "refinement_directives": directives,
        "refinement_history": history,
        "constraint_satisfaction": {"passed": None, "satisfied": [], "unmet": [], "warnings": []},
        "error": None,
    }

    # Fold natural-language preferences into the structured constraints used by validation.
    patch["preference_constraints"] = _patched_constraints(
        state.get("preference_constraints", {}),
        {"directives": directives, "message": message},
    )

    if plan.get("cost_sensitivity") == "lower_cost":
        patch.update(_budget_patch(state))

    if resolved:
        patch["activities"] = resolved  # additive reducer appends to the existing pool
        categories = list(state.get("active_tool_categories", []))
        for activity in resolved:
            category = str(activity.get("category", "")).strip()
            if category and category not in categories:
                categories.append(category)
        patch["active_tool_categories"] = categories

    rerun_from = plan.get("rerun_from") or "search_hotel"
    if rerun_from not in RERUN_NODES:
        rerun_from = "search_hotel"
    return patch, rerun_from
