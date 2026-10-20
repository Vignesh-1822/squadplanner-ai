"""Golden cases split into two deliberately different tiers.

Offline cases replay tools *and* LLM output. They catch code regressions only:
constraint logic, retry routing, date maths, scoring and wiring. They cannot
measure itinerary quality because the model output is frozen.

Live cases use real tools and models. Only this tier can detect prompt or model
quality regressions, and it is manual because SerpAPI quota is limited.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent


def initial_state(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "trip_id": case_id,
        "members": payload["members"],
        "group_notes": payload.get("group_notes", ""),
        "start_date": payload["start_date"],
        "end_date": payload["end_date"],
        "trip_duration_days": 0,
        "preference_conflicts": [],
        "preference_constraints": {},
        "constraint_satisfaction": {},
        "group_preference_vector": {},
        "destination_preference_vector": {},
        "active_tool_categories": [],
        "candidate_destinations": [],
        "selected_destination": None,
        "selected_destination_coords": None,
        "flights": [],
        "activities": [],
        "weather": None,
        "budget_status": None,
        "budget_ceiling_hotel_usd": None,
        "hotel": None,
        "days": [],
        "fairness_scores": {},
        "compatibility_scores": {},
        "fairness_passed": False,
        "trip_pitch": None,
        "current_refinement": {},
        "refinement_directives": {},
        "refinement_history": [],
        "decision_log": [],
        "destination_retry_count": 0,
        "hotel_retry_count": 0,
        "error": None,
    }


def load_cases(tier: str = "offline") -> list[dict[str, Any]]:
    cases = []
    for path in sorted((_ROOT / tier).glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if tier == "live" and "relative_start_days" in case:
            start = date.today() + timedelta(days=int(case["relative_start_days"]))
            end = start + timedelta(days=int(case["duration_days"]))
            case["payload"]["start_date"] = start.isoformat()
            case["payload"]["end_date"] = end.isoformat()
        case["source_path"] = str(path)
        case["initial_state"] = initial_state(case["id"], case["payload"])
        cases.append(case)
    return cases
